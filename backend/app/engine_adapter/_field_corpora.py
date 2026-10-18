"""Per-field ontology corpora from a target schema's data dictionary.

The lab's design for mapping a field's values to ontology terms
(``shbrief/MetaHarmonizerSchemaRegistry``, scripts/README.md, "Ontology corpus &
term artifacts"; the engine's ``knowledge_db/combined_corpus_builder``): a
field's target corpus is the union of the corpus layers its dictionary entry
declares —

1. ``dynamic.enum`` roots, expanded to their descendants (or direct children,
   per ``dynamic.enum.property``);
2. enum ``allowedvalues`` bound to their positional ``static.enum`` ids;
3. standalone ``static.enum`` terms —

and a field whose terms span several ontologies is mapped once per ontology,
the candidates merged by score (``run_ontology_partitioned`` /
``merge_match_results``), because ``OntoMapEngine`` maps one ontology per run
(upstream issue #94).

Each dynamic root, and each ontology's fixed terms, is one *unit*: built and
indexed once by ``scripts/build_kb.py`` and shared by every field and schema
naming it. A field is mapped by running the engine (its default pipeline) on
each of its units and merging the candidates with ``merge_match_results``:
``run_ontology_partitioned`` with a field's same-ontology layers run apart, so
that a layer shared between fields and schemas is indexed once. Exact matches
and embedding scores are per term, so this equals one run per ontology except
where the engine looks at the rest of the corpus (plural stripping, the
synonym stage's low-confidence check), which only fields with a branch and
fixed terms of one ontology can see (cMD's disease fields and treatment). A
root that is one of the engine's own corpora (``_CORPUS_REGISTRY``, e.g.
UBERON:0001062) uses that corpus instead.

Left out, with the reason recorded: numeric fields (a dictionary entry such as
``age_at_death`` naming an ontology root is a data error), ontologies the
engine cannot fetch at the vendored commit (HANCESTRO, SNOMED, MRO, FMA,
NCBITaxon; upstream #93), enum labels without ontology ids (upstream PR #92),
and the whole NCBI Taxonomy. Such fields keep the dictionary fallback.

Only this module and ``_ontology`` touch the engine's corpus machinery.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import _schema_registry

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)

# Engine category for the units' tables and indexes. The engine names them
# ``{source}_{rag|synonym|corpus}_field_{content hash}`` and
# ``st_sap_bert_{source}_field_{content hash}.index``, so equal units share
# one index whatever field or schema names them.
UNIT_CATEGORY = "field"
# The engine options of a unit run, at build and at run time alike: the
# engine's default pipeline, as for its own corpora and in the lab's
# run_ontology_partitioned. Its synonym stage (2.5) adds 2-4 points of top-1
# on the lab's curation maps, so units keep it and ship its index.
UNIT_ENGINE_KWARGS: dict[str, Any] = {"s2_method": "sap-bert", "s2_strategy": "st"}
# Not an exact label, so a build run reaches stage 2 and builds the index
# (the same probe as scripts/build_kb.py).
PROBE = "kb build probe do not match"
MANIFEST = "units.json"
# NCI EVSREST and EBI OLS4 fail transiently (HTTP 500) and the engine aborts a
# corpus on one failed page, so a unit's fetch is retried.
FETCH_ATTEMPTS = 3
FETCH_BACKOFF_SECONDS = 60

_NUMERIC_CLASSES = {"numeric", "integer", "double"}
# Roots the KB does not expand.
_UNBUILT_ROOTS = {"NCBITaxon:1": "the whole NCBI Taxonomy is millions of terms"}


@dataclass(frozen=True)
class Unit:
    """One indexed corpus: a dynamic root's branch, or one ontology's fixed terms."""

    key: str
    ontology: str  # the engine's lower-case source name: ncit, mondo, uberon, ...
    root: str = ""  # dynamic root (OBO id); empty for fixed terms
    prop: str = "descendant"  # descendant | children
    terms: tuple[tuple[str, str], ...] = ()  # fixed terms: (OBO id, allowed-value label or "")
    official: tuple[str, str] | None = None  # (category, source) of the engine corpus with this root


@dataclass(frozen=True)
class FieldCorpus:
    field: str
    units: tuple[Unit, ...]
    left_out: tuple[str, ...] = ()  # corpus layers the engine cannot use, with the reason


def data_dir() -> Path:
    """Where the engine reads its corpora: ``$METAHARMONIZER_DATA_DIR``, else
    the dashboard-owned ``backend/data``."""
    env = os.environ.get("METAHARMONIZER_DATA_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[2] / "data"


def _engine_ready() -> None:
    """Point the engine at the dashboard's data directory before its first
    import, as the adapter does: the engine fixes its paths on import."""
    from .metaharmonizer_impl import _ensure_upstream_data_dir

    _ensure_upstream_data_dir()


def units_dir() -> Path:
    return data_dir() / "corpus" / "fields"


def unit_csv(unit: Unit) -> Path:
    return units_dir() / f"{unit.key}_corpus.csv"


def read_unit(path: Path | str) -> "pd.DataFrame":
    """A unit's corpus as the engine gets it, at build and at run time alike
    (the engine names the unit's tables and indexes by a hash of this frame).
    Labels stay verbatim, as in the engine's in-memory
    ``run_ontology_partitioned``: no "NA" or "None" read as missing."""
    import pandas as pd

    return pd.read_csv(path, dtype=str, keep_default_na=False)


def ontology_of(code: str) -> str | None:
    """The engine's source name for an OBO id, or None if it cannot fetch it."""
    _engine_ready()
    from metaharmonizer.knowledge_db.db_clients.ols_db import PREFIX_TO_ONTOLOGY

    prefix = code.split(":", 1)[0] if ":" in code else code.split("_", 1)[0]
    if prefix.upper() == "NCIT":
        return "ncit"
    return PREFIX_TO_ONTOLOGY.get(prefix) or PREFIX_TO_ONTOLOGY.get(prefix.upper())


def _official(root: str, ontology: str, prop: str) -> tuple[str, str] | None:
    """The engine corpus with this root, if the KB build installs it."""
    if prop != "descendant":
        return None
    _engine_ready()
    from metaharmonizer.engine.ontology_mapping_engine import _CORPUS_REGISTRY
    from metaharmonizer.knowledge_db.combined_corpus_builder import normalize_obo_id

    from .kb_assets import KB_ONTOLOGY_TUPLES

    for (category, source), registry_root in _CORPUS_REGISTRY.items():
        if (
            source == ontology
            and normalize_obo_id(registry_root) == root
            and (category, source) in KB_ONTOLOGY_TUPLES
        ):
            return category, source
    return None


def _safe(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _root_unit(root: str, ontology: str, prop: str) -> Unit:
    local = root.split(":", 1)[-1]
    return Unit(
        key=f"{ontology}_{_safe(local)}_{prop}",
        ontology=ontology,
        root=root,
        prop=prop,
        official=_official(root, ontology, prop),
    )


def _terms_unit(ontology: str, terms: list[tuple[str, str]]) -> Unit:
    digest = hashlib.sha1("|".join(f"{i}={label}" for i, label in sorted(terms)).encode()).hexdigest()
    return Unit(key=f"{ontology}_terms_{digest[:10]}", ontology=ontology, terms=tuple(terms))


def field_corpus(row: dict[str, Any]) -> FieldCorpus | None:
    """The units of one dictionary entry, or None if it names no corpus."""
    _engine_ready()
    from metaharmonizer.knowledge_db.combined_corpus_builder import (
        _split_allowedvalues_enum,
        _split_enum_field,
        field_has_corpus_layer,
        normalize_obo_id,
    )

    name = (row.get("col.name") or "").strip()
    corpus_type = row.get("corpus.type") or ""
    if (
        not name
        or (row.get("col.class") or "").strip().lower() in _NUMERIC_CLASSES
        or "regexp" in corpus_type
        or not field_has_corpus_layer(row)
    ):
        return None

    units: list[Unit] = []
    left_out: list[str] = []
    prop = (row.get("dynamic.enum.property") or "").strip()
    prop = prop if prop in ("descendant", "children") else "descendant"
    for raw_root in _split_enum_field(row.get("dynamic.enum")):
        root = normalize_obo_id(raw_root)
        ontology = ontology_of(root)
        if root in _UNBUILT_ROOTS:
            left_out.append(f"{root}: {_UNBUILT_ROOTS[root]}")
        elif ontology is None:
            left_out.append(f"{root}: the engine cannot fetch this ontology")
        else:
            units.append(_root_unit(root, ontology, prop))

    labels = _split_allowedvalues_enum(row.get("allowedvalues"))
    static = [normalize_obo_id(t) for t in _split_enum_field(row.get("static.enum"))]
    if static:
        # The engine binds allowed values to static ids by position when the
        # counts agree (CombinedCorpusBuilder.build_field_corpus).
        pairs = list(zip(static, labels)) if len(labels) == len(static) else [(s, "") for s in static]
        if labels and len(labels) != len(static):
            left_out.append("allowed values that do not line up with the static ids")
        by_ontology: dict[str, list[tuple[str, str]]] = {}
        for term_id, label in pairs:
            ontology = ontology_of(term_id)
            if ontology is None:
                left_out.append(f"{term_id}: the engine cannot fetch this ontology")
            else:
                by_ontology.setdefault(ontology, []).append((term_id, label))
        units.extend(_terms_unit(ontology, terms) for ontology, terms in by_ontology.items())
    elif labels:
        left_out.append("allowed values without ontology ids")

    if not units:
        if left_out:
            logger.info("field %s has no corpus the engine can use: %s", name, "; ".join(left_out))
        return None
    return FieldCorpus(field=name, units=tuple(units), left_out=tuple(left_out))


def _dictionary_rows(path: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as handle:
        text = handle.read()
    first = text.split("\n", 1)[0]
    delimiter = "," if first.count(",") > first.count(" ") else " "
    return list(csv.DictReader(io.StringIO(text), delimiter=delimiter))


@lru_cache(maxsize=8)
def field_corpora(schema_key: str | None) -> dict[str, FieldCorpus]:
    """``{field name (lower case): FieldCorpus}`` for target schema ``schema_key``,
    from its data dictionary; empty for a schema without one (such as GDC)."""
    schema = _schema_registry._discover().get(schema_key or "")
    path = schema and schema.get("dictionary_path")
    if not path:
        return {}
    found: dict[str, FieldCorpus] = {}
    for row in _dictionary_rows(path):
        corpus = field_corpus(row)
        if corpus:
            found[corpus.field.lower()] = corpus
    return found


def installed(unit: Unit) -> bool:
    """True when the KB holds the unit: its engine corpus, or the corpus CSV,
    engine tables and indexes the KB build wrote for it (a unit whose build
    found no terms has none). An unbuilt unit must not reach the engine: it
    would fetch and embed the corpus on the request."""
    if unit.official is not None:
        _engine_ready()
        from .kb_assets import engine_corpus_installed

        return engine_corpus_installed(*unit.official)
    entry = _manifest_units().get(unit.key) or {}
    corpus_hash = entry.get("corpus_hash")
    path = unit_csv(unit)
    if not entry.get("rows") or not corpus_hash or not path.is_file():
        return False
    if path.stat().st_size != entry.get("bytes"):
        return False
    return not _missing_indexes(unit, corpus_hash)


def _index_names(unit: Unit, corpus_hash: str) -> list[str]:
    """The FAISS files a unit's engine run reads, as ``kb_assets`` checks for
    the engine's own corpora: the exact sap-bert index and its id sidecar, and
    the synonym index of stage 2.5."""
    stem = f"sap_bert_{unit.ontology}_{UNIT_CATEGORY}_{corpus_hash}.index"
    names = [f"st_{stem}", f"st_{stem}.ids.npy"]
    if not UNIT_ENGINE_KWARGS.get("skip_stage25"):
        names.append(f"synonym_{stem}")
    return names


def _missing_indexes(unit: Unit, corpus_hash: str) -> list[str]:
    _engine_ready()
    from metaharmonizer import _paths

    faiss_dir = Path(_paths.FAISS_INDEX_DIR)
    return [
        name
        for name in _index_names(unit, corpus_hash)
        if not ((faiss_dir / name).is_file() and (faiss_dir / name).stat().st_size > 0)
    ]


@lru_cache(maxsize=4)
def _manifest_at(path: str, stamp: tuple[int, int]) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _manifest_units() -> dict[str, dict]:
    path = units_dir() / MANIFEST
    try:
        stat = path.stat()
    except OSError:
        return {}
    return _manifest_at(str(path), (stat.st_mtime_ns, stat.st_size)).get("units") or {}


def read_manifest() -> dict[str, Any]:
    try:
        return json.loads((units_dir() / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_manifest(manifest: dict[str, Any]) -> None:
    path = units_dir() / MANIFEST
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def build_unit_records(unit: Unit) -> list[dict]:
    """The unit's corpus records, built with the engine's CombinedCorpusBuilder
    (NCI EVSREST for NCIt, EBI OLS4 otherwise); obsolete and unlabeled terms
    left out."""
    _engine_ready()
    from metaharmonizer.knowledge_db.combined_corpus_builder import CombinedCorpusBuilder

    builder = CombinedCorpusBuilder()
    if unit.root:
        records = builder.build(dynamic_roots=[unit.root], prop=unit.prop)
    else:
        labels = [label for _id, label in unit.terms]
        row = {
            "dynamic.enum": "NA",
            "static.enum": "|".join(term_id for term_id, _label in unit.terms),
            "allowedvalues": "|".join(labels) if all(labels) else "NA",
        }
        records = builder.build_field_corpus(row)
    kept = []
    for record in records:
        label = str(record.get("label") or "").strip()
        obo_id = str(record.get("obo_id") or "")
        if (
            not label
            or label.lower().startswith("obsolete")
            or not obo_id
            or ontology_of(obo_id) != unit.ontology
        ):
            continue
        kept.append(record)
    return kept


def _fetch_unit_records(unit: Unit) -> list[dict]:
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            return build_unit_records(unit)
        except Exception as exc:  # noqa: BLE001 — retried, then raised
            if attempt == FETCH_ATTEMPTS:
                raise
            logger.warning("unit %s: fetch failed (%s); retry %d", unit.key, exc, attempt)
            time.sleep(FETCH_BACKOFF_SECONDS * attempt)
    return []


def _missing_concepts(engine: Any, unit: Unit) -> set[str]:
    """Corpus codes the engine's concept table for the unit lacks."""
    import sqlite3

    from metaharmonizer._paths import VECTOR_DB_PATH

    codes = set(engine.other_params["corpus_df"]["clean_code"].dropna())
    table = f"{unit.ontology}_rag_{UNIT_CATEGORY}{engine._table_suffix}"
    try:
        with sqlite3.connect(VECTOR_DB_PATH) as conn:
            stored = {row[0] for row in conn.execute(f'SELECT DISTINCT code FROM "{table}"')}
    except sqlite3.OperationalError:
        stored = set()
    return codes - stored


def _engine_corpus_hash(corpus: "pd.DataFrame") -> str:
    """The suffix the engine gives a caller corpus's tables and indexes:
    ``compute_corpus_hash`` over the corpus as ``OntoMapEngine._normalize_df``
    leaves it (label and code, ``NCIT:`` dropped, each pair once)."""
    import pandas as pd
    from metaharmonizer.utils.corpus_hash import compute_corpus_hash

    def clean_code(code: str) -> str:
        prefix, sep, local = code.partition(":")
        if not sep:
            return code
        return local if prefix == "NCIT" else f"{prefix}_{local}"

    frame = pd.DataFrame(
        {
            "official_label": corpus["label"].astype(str),
            "clean_code": corpus["obo_id"].astype(str).map(clean_code),
        }
    ).drop_duplicates()
    return compute_corpus_hash(frame)


def _fill_concept_tables(unit: Unit, corpus: "pd.DataFrame", records: list[dict]) -> str:
    """Write the unit's engine concept tables (synonyms, context) from the
    records its corpus was built from, with the engine's offline path
    (``ConceptTableBuilder.build_from_json``), so that constructing the engine
    does not fetch every concept a second time. Returns the tables' suffix."""
    import tempfile

    from metaharmonizer.knowledge_db.concept_table_builder import ConceptTableBuilder

    suffix = f"_{_engine_corpus_hash(corpus)}"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "corpus.json"
        path.write_text(json.dumps({"terms": records}), encoding="utf-8")
        ConceptTableBuilder(UNIT_CATEGORY, unit.ontology, table_suffix=suffix).build_from_json(str(path))
    return suffix


def schema_units(schema_keys: list[str]) -> list[Unit]:
    """The distinct units the fields of these target schemas use."""
    found: dict[str, Unit] = {}
    for key in schema_keys:
        for corpus in field_corpora(key).values():
            for unit in corpus.units:
                found.setdefault(unit.key, unit)
    return [found[key] for key in sorted(found)]


def build_units(units: list[Unit], *, rebuild: bool = False) -> dict[str, dict]:
    """Build each unit the engine has no corpus for: its corpus (network: NCI
    EVSREST / EBI OLS4), then its engine tables and indexes by one engine run
    with a probe that is not a label (CPU: sap-bert); the CSV is written last,
    so a unit is installed only once complete. Writes the manifest after each
    unit and returns its entries. Not for a production server."""
    _engine_ready()
    from metaharmonizer.engine.ontology_mapping_engine import OntoMapEngine
    from metaharmonizer.knowledge_db.combined_corpus_builder import CombinedCorpusBuilder

    units_dir().mkdir(parents=True, exist_ok=True)
    manifest = read_manifest()
    entries: dict[str, dict] = manifest.setdefault("units", {})
    for unit in units:
        if unit.official is not None:
            continue
        path = unit_csv(unit)
        if not rebuild and installed(unit):
            continue
        tmp: Path | None = None
        records: list[dict] = []
        if not rebuild and path.is_file():
            # A fetched corpus whose engine run did not finish: run it again.
            corpus = read_unit(path)
        else:
            records = _fetch_unit_records(unit)
            if not records:
                path.unlink(missing_ok=True)
                entries[unit.key] = {"ontology": unit.ontology, "root": unit.root, "rows": 0}
                _write_manifest(manifest)
                logger.warning("unit %s has no terms (an obsolete or empty root); left out", unit.key)
                continue
            tmp = path.with_suffix(".csv.tmp")
            CombinedCorpusBuilder.to_dataframe(records).to_csv(tmp, index=False)
            corpus = read_unit(tmp)
        try:
            filled = _fill_concept_tables(unit, corpus, records) if records else None
            corpus_hash = _index_unit(OntoMapEngine, unit, corpus)
            if filled and f"_{corpus_hash}" != filled:
                logger.warning(
                    "unit %s: concept tables filled as %s, the engine used _%s", unit.key, filled, corpus_hash
                )
        except BaseException:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
            raise
        if tmp is not None:
            os.replace(tmp, path)
        entries[unit.key] = {
            "ontology": unit.ontology,
            "root": unit.root,
            "prop": unit.prop,
            "terms": [term_id for term_id, _label in unit.terms],
            "rows": int(len(corpus)),
            "bytes": path.stat().st_size,
            "corpus_hash": corpus_hash,
            "indexes": _index_names(unit, corpus_hash),
        }
        _write_manifest(manifest)
        logger.info("built unit %s: %d terms (hash %s)", unit.key, len(corpus), corpus_hash)
    return entries


def _index_unit(OntoMapEngine: Any, unit: Unit, corpus: "pd.DataFrame") -> str:
    """Build a unit's engine tables and indexes, by one run with a probe that
    is not a label; returns its corpus hash."""
    engine = None
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        # The engine fetches the concept data of corpus codes its tables lack
        # on construction; a code left out (a failed fetch) would be fetched
        # again on every run, on a user's request.
        engine = OntoMapEngine(
            corpus_category=UNIT_CATEGORY,
            query_ls=[PROBE],
            corpus_df=corpus,
            ontology_source=unit.ontology,
            **UNIT_ENGINE_KWARGS,
        )
        missing = _missing_concepts(engine, unit)
        if not missing:
            break
        if attempt == FETCH_ATTEMPTS:
            raise RuntimeError(
                f"unit {unit.key}: no concept data for {len(missing)} code(s), "
                f"e.g. {', '.join(sorted(missing)[:5])}"
            )
        logger.warning("unit %s: %d concept(s) not fetched; retry %d", unit.key, len(missing), attempt)
        time.sleep(FETCH_BACKOFF_SECONDS * attempt)
    engine.run()
    corpus_hash = engine._corpus_hash
    missing_indexes = _missing_indexes(unit, corpus_hash)
    if missing_indexes:
        raise RuntimeError(f"unit {unit.key}: the engine run wrote no {', '.join(missing_indexes)}")
    return corpus_hash
