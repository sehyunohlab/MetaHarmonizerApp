"""Real-engine ontology value mapping (F-11, app side).

Routes value→ontology mapping through the upstream ``OntoMapEngine`` for the
engine's first-class categories, falling back to the curated dictionary
otherwise. Opt-in via ``ONTOLOGY_ENGINE=1``. The engine also registers
``("phenotype", "efo")``, but no field in the supported target schemas is a
phenotype term field, so nothing routes there yet. Only this module may touch
the ontology engine.
"""

from __future__ import annotations

import logging
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from .kb_assets import (
    REQUIRED_ONTOLOGY_TUPLES,
    installed_kb_issues,
    runtime_engine_required,
    runtime_ontology_required,
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _auto_accept_threshold() -> float:
    """Confidence at/above which a mapping is auto-accepted (env-tunable per the
    spec's auto-accept / flag-for-review bands; ``AUTO_ACCEPT_THRESHOLD``)."""
    try:
        from app.core.settings import settings

        return float(settings.auto_accept_threshold)
    except Exception:  # noqa: BLE001 — never fail mapping over a config read
        return 0.9

# Dashboard field name (lower) → engine ontology (category, source) for a field
# its target schema's data dictionary names no corpus for (see
# ``_field_corpora``), limited to the engine's own corpora. Body sites use the
# engine's UBERON anatomy: its NCIt body-site corpus (root NCIT:C32221 Body
# Part) holds organ parts but not the organs themselves (no Lung, Liver,
# Kidney or Breast), so common values matched the wrong term.
# Excluded on purpose: GDC ``treatment_or_therapy`` (yes/no/unknown) and
# ``morphology`` (ICD-O codes such as 8000/0) are not term vocabularies.
FIELD_ONTOLOGY: dict[str, tuple[str, str]] = {
    "disease": ("disease", "ncit"),
    "target_condition": ("disease", "ncit"),
    "cancer_type": ("disease", "ncit"),
    "primary_diagnosis": ("disease", "ncit"),
    "primary_disease": ("disease", "ncit"),
    "disease_type": ("disease", "ncit"),
    "body_site": ("bodysite", "uberon"),
    "primary_site": ("bodysite", "uberon"),
    "tissue_or_organ_of_origin": ("bodysite", "uberon"),
    "site_of_resection_or_biopsy": ("bodysite", "uberon"),
    "biospecimen_anatomic_site": ("bodysite", "uberon"),
    "treatment": ("treatment", "ncit"),
    "treatment_name": ("treatment", "ncit"),
    "treatment_type": ("treatment", "ncit"),
    "therapeutic_agents": ("treatment", "ncit"),
}


def is_ontology_field(field: str | None, target_schema: str | None = None) -> bool:
    """True when the engine maps a field's values: an engine corpus routes it,
    or the target schema's data dictionary declares a corpus for it that the
    KB holds (see ``_field_corpora``)."""
    if not field:
        return False
    name = field.strip().lower()
    if name in FIELD_ONTOLOGY:
        return True
    if not (runtime_engine_required() and engine_enabled()):
        return False
    try:
        from . import _field_corpora, _schema_registry

        key = target_schema if _schema_registry.is_valid(target_schema) else _schema_registry.default_key()
        corpus = _field_corpora.field_corpora(key).get(name)
        return bool(corpus) and any(_field_corpora.installed(unit) for unit in corpus.units)
    except Exception:  # noqa: BLE001 — an unreadable dictionary means no corpus
        logger.warning("could not read the field corpora of %s", target_schema, exc_info=True)
        return False


def engine_enabled() -> bool:
    """True when the operator has opted into the real ontology engine path."""
    return os.getenv("ONTOLOGY_ENGINE", "0").strip().lower() in {"1", "true", "yes", "on"}


def runtime_asset_issues() -> list[str]:
    """Return missing production KB assets without constructing the engine."""
    if not runtime_engine_required():
        return []
    try:
        ontology_required = runtime_ontology_required()
        return installed_kb_issues(
            require_engine_db=ontology_required,
            require_ontology_model=ontology_required,
            require_schema_model=True,
            tuples=REQUIRED_ONTOLOGY_TUPLES if ontology_required else (),
        )
    except Exception as exc:  # noqa: BLE001 - readiness must return a diagnosis
        return [f"could not inspect ontology assets: {type(exc).__name__}: {exc}"]


def runtime_asset_error() -> str | None:
    issues = runtime_asset_issues()
    if not issues:
        return None
    logger.error("ontology KB readiness failed: %s", issues)
    return (
        "The ontology knowledge-base bundle is not ready. "
        "Ask the operator to run `docker compose --profile kb run --rm kb-import` "
        f"and retry ({len(issues)} required asset(s) missing)."
    )


def _to_score(value: Any) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(f) or math.isinf(f):
        return 0.0
    return max(0.0, min(1.0, f))


def _data_dir() -> Path:
    """Where the engine reads its corpora — mirrors ``_ensure_upstream_data_dir``
    (``$METAHARMONIZER_DATA_DIR`` else the dashboard-owned ``backend/data``)."""
    env = os.environ.get("METAHARMONIZER_DATA_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "data"


@lru_cache(maxsize=8)
def _corpus_label_to_id(category: str, source: str) -> dict[str, str]:
    """Load the ``label -> obo_id`` map for a corpus.

    ``OntoMapEngine.run()`` returns only the matched *label* (``match1``), never
    the ontology code — but every ``match1`` is a row from this corpus, so we can
    recover the code by exact label. Returns ``{}`` (graceful degrade to a
    code-less row) if the corpus can't be read.
    """
    path = _data_dir() / "corpus" / "retrieved_ontologies" / f"{source}_{category}_corpus.csv"
    try:
        df = pd.read_csv(path, usecols=["label", "obo_id"])
    except Exception as exc:  # noqa: BLE001 — missing/renamed corpus -> no codes, not a crash
        logger.warning("ontology code lookup unavailable (%s): %s", path, exc)
        return {}
    mapping: dict[str, str] = {}
    for label, obo in zip(df["label"], df["obo_id"]):
        if not isinstance(label, str):
            continue
        key = label.strip().lower()
        code = "" if obo is None else str(obo).strip()
        if key and code and key not in mapping:  # first-wins for stable output
            mapping[key] = code
    return mapping


def _normalize_engine_rows(
    field_name: str,
    result: "pd.DataFrame",
    category: str | None = None,
    source: str | None = None,
) -> list[dict[str, Any]]:
    """Map an ``OntoMapEngine.run()`` frame to our ontology DTO rows, one per
    query.

    Defensive about column names so an upstream rename degrades to a
    lower-confidence row rather than crashing. When the engine supplies a label
    but no code (its normal behaviour — the output frame has no id column) and
    ``category``/``source`` are known, the code is recovered from the corpus.
    The engine repeats a query's row when several queries normalize to the
    same text (``BLADDER CANCER`` and ``BLADDER_CANCER``); the best-scoring
    row is kept.
    """
    rows: dict[str, dict[str, Any]] = {}
    records = result.to_dict(orient="records") if result is not None else []
    label_to_id: dict[str, str] | None = None
    for raw in records:
        query = raw.get("query")
        if query is None:
            continue
        term = raw.get("match1")
        term_missing = term is None or (isinstance(term, float) and math.isnan(term))
        ont_id = (
            raw.get("match1_id")
            or raw.get("match1_obo_id")
            or raw.get("obo_id")
            or None
        )
        # Engine frames carry no code column; recover it from the corpus the
        # match came from. Only load the map when a row actually needs it.
        if ont_id is None and not term_missing and category and source:
            if label_to_id is None:
                label_to_id = _corpus_label_to_id(category, source)
            ont_id = label_to_id.get(str(term).strip().lower())
        score = _to_score(raw.get("match1_score"))
        kept = rows.get(str(query))
        if kept is not None and kept["confidence_score"] >= round(score, 4):
            continue
        rows[str(query)] = {
            "field_name": field_name,
            "raw_value": str(query),
            "ontology_term": None if term_missing else str(term),
            "ontology_id": None if ont_id is None else str(ont_id),
            "confidence_score": round(score, 4),
            "status": "accepted" if score >= _auto_accept_threshold() else "pending",
        }
    return list(rows.values())


def map_values_via_engine(
    pkg: Any,
    raw_df: "pd.DataFrame",
    schema_mappings: list[dict[str, Any]],
    target_schema: str | None = None,
) -> tuple[list[dict[str, Any]], set[str]]:
    """Map supported fields' values through ``OntoMapEngine``.

    A field whose dictionary entry in the target schema names a corpus is
    mapped against that corpus's units (see ``_field_corpora``); any other
    field in :data:`FIELD_ONTOLOGY` against the engine's corpus for it.

    Returns ``(rows, handled_fields)`` — the ontology rows and the set of field
    names the engine covered, so the caller can fall back to the dictionary for
    the rest. A per-field failure is logged and left to the fallback.
    """
    OntoMapEngine = getattr(pkg, "OntoMapEngine", None)
    if OntoMapEngine is None:
        return [], set()
    issues = runtime_asset_issues()
    if issues:
        logger.error("ontology engine skipped because the offline KB is incomplete: %s", issues)
        return [], set()

    from . import _field_corpora, _schema_registry

    try:
        corpora = {
            name: corpus
            for name, corpus in _field_corpora.field_corpora(
                target_schema if _schema_registry.is_valid(target_schema) else _schema_registry.default_key()
            ).items()
            if any(_field_corpora.installed(unit) for unit in corpus.units)
        }
    except Exception:  # noqa: BLE001 — an unreadable dictionary means no field corpora
        logger.warning("could not read the field corpora of %s", target_schema, exc_info=True)
        corpora = {}

    # Collect unique values per supported field.
    per_field: dict[str, list[str]] = {}
    for m in schema_mappings:
        target = (m.get("curator_field") or m.get("matched_field") or "").strip().lower()
        if target not in corpora and target not in FIELD_ONTOLOGY:
            continue
        raw_col = m.get("raw_column")
        if not raw_col or raw_col not in raw_df.columns:
            continue
        values = [str(v) for v in raw_df[raw_col].dropna().unique() if str(v).strip()]
        if values:
            per_field.setdefault(target, []).extend(values)

    rows: list[dict[str, Any]] = []
    handled: set[str] = set()
    for field_name, values in per_field.items():
        uniq = sorted(set(values))
        try:
            if field_name in corpora:
                rows.extend(_map_with_units(OntoMapEngine, field_name, corpora[field_name], uniq))
            else:
                category, source = _engine_corpus(field_name)
                engine = OntoMapEngine(
                    corpus_category=category,
                    query_ls=uniq,
                    ontology_source=source,
                    s2_method="sap-bert",
                    s2_strategy="st",
                )
                rows.extend(_normalize_engine_rows(field_name, engine.run(), category, source))
        except Exception as exc:  # noqa: BLE001 — fall back on any engine error
            logger.warning("ontology engine failed for field %s: %s; falling back", field_name, exc)
            continue
        handled.add(field_name)
    return rows, handled


def _engine_corpus(field_name: str) -> tuple[str, str]:
    """The engine corpus for a field without a dictionary corpus."""
    return FIELD_ONTOLOGY[field_name]


@lru_cache(maxsize=32)
def _unit_frame(path: str, stamp: tuple[int, int]) -> "pd.DataFrame":
    from . import _field_corpora

    return _field_corpora.read_unit(path)


def _label_codes(frame: "pd.DataFrame") -> dict[str, str]:
    codes: dict[str, str] = {}
    for label, obo in zip(frame["label"], frame["obo_id"]):
        if isinstance(label, str) and isinstance(obo, str) and obo.strip():
            codes.setdefault(label.strip().lower(), obo.strip())
    return codes


def _map_with_units(
    OntoMapEngine: Any, field_name: str, corpus: Any, values: list[str]
) -> list[dict[str, Any]]:
    """Map a field's values against each installed unit of its corpus and merge
    the candidates (the engine's ``merge_match_results``). A term's code comes
    from the unit whose run scored it highest."""
    from metaharmonizer.knowledge_db.combined_corpus_builder import merge_match_results

    from . import _field_corpora

    frames: list[pd.DataFrame] = []
    best: dict[tuple[str, str], tuple[float, str]] = {}
    for unit in corpus.units:
        if not _field_corpora.installed(unit):
            continue
        if unit.official is not None:
            category, source = unit.official
            engine = OntoMapEngine(
                corpus_category=category,
                query_ls=values,
                ontology_source=source,
                s2_method="sap-bert",
                s2_strategy="st",
            )
            codes = _corpus_label_to_id(category, source)
        else:
            path = _field_corpora.unit_csv(unit)
            stat = path.stat()
            frame = _unit_frame(str(path), (stat.st_mtime_ns, stat.st_size))
            engine = OntoMapEngine(
                corpus_category=_field_corpora.UNIT_CATEGORY,
                query_ls=values,
                corpus_df=frame,
                ontology_source=unit.ontology,
                **_field_corpora.UNIT_ENGINE_KWARGS,
            )
            codes = _label_codes(frame)
        result = engine.run()
        frames.append(result)
        for raw in result.to_dict(orient="records"):
            for i in range(1, 6):
                label = raw.get(f"match{i}")
                code = codes.get(label.strip().lower()) if isinstance(label, str) else None
                if not code:
                    continue
                key, score = (str(raw.get("query")), label.strip()), _to_score(raw.get(f"match{i}_score"))
                if key not in best or score > best[key][0]:
                    best[key] = (score, code)

    rows: list[dict[str, Any]] = []
    for raw in merge_match_results(frames, top_k=5).to_dict(orient="records"):
        term = raw.get("match1")
        term = term.strip() if isinstance(term, str) and term.strip() else None
        score = _to_score(raw.get("match1_score")) if term else 0.0
        rows.append(
            {
                "field_name": field_name,
                "raw_value": str(raw.get("query")),
                "ontology_term": term,
                "ontology_id": best.get((str(raw.get("query")), term), (0.0, None))[1] if term else None,
                "confidence_score": round(score, 4),
                "status": "accepted" if score >= _auto_accept_threshold() else "pending",
            }
        )
    return rows
