"""Build the ontology knowledge DB (SQLite corpus + FAISS indexes) offline.

Builds the app's engine corpora by triggering the engine's own corpus+index
build (``OntoMapEngine.run`` builds on a cache miss, then persists to
``KNOWLEDGE_DB_DIR``); with ``--fields``, the per-field corpora the target
schemas' data dictionaries name instead (``app.engine_adapter._field_corpora``).
Run this ONCE on a capable machine, then distribute the result with
``scripts/package_kb.py`` — never build on a small production VM.

Corpora fetch key-free (NCIt via EVSREST, UBERON / MONDO via OLS4).
``UMLS_API_KEY`` only adds optional synonym enrichment.

Usage::

    python -m scripts.build_kb                       # all engine corpora
    python -m scripts.build_kb --only disease/ncit   # one engine corpus
    python -m scripts.build_kb --fields              # the schemas' per-field corpora
    KNOWLEDGE_DB_DIR=/data/kb python -m scripts.build_kb

This is an offline build tool (not app runtime), so it may import the engine
directly — the engine-adapter boundary only governs ``backend/app``.
"""

from __future__ import annotations

import argparse
import logging
import time

from app.engine_adapter.kb_assets import (
    KB_ONTOLOGY_TUPLES,
    installed_kb_issues,
)

# (category, ontology_source, seed_query) — the seed drives one run so the full
# corpus AND the FAISS index build. It must NOT be an exact ontology label,
# otherwise Stage 1 short-circuits and Stage 2 (which builds the FAISS index) is
# skipped, leaving an index-less KB. A deliberately non-label probe forces Stage 2.
_PROBE = "kb build probe do not match"
LAUNCH_TUPLES = [(category, source, _PROBE) for category, source in KB_ONTOLOGY_TUPLES]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("build_kb")


def _build_one(category: str, source: str, seed: str) -> int:
    from metaharmonizer.engine.ontology_mapping_engine import OntoMapEngine

    t0 = time.perf_counter()
    engine = OntoMapEngine(
        corpus_category=category,
        query_ls=[seed],
        ontology_source=source,
        s2_method="sap-bert",
        s2_strategy="st",
    )
    result = engine.run()
    n = len(result) if result is not None else 0
    _verify_outputs(category, source)
    logger.info(
        "built %s/%s in %.1fs (seed query mapped %d row(s))",
        category, source, time.perf_counter() - t0, n,
    )
    return n


def _verify_outputs(category: str, source: str) -> None:
    """Completeness check: the ST corpus FAISS index plus its ids sidecar must
    exist and be non-empty for this category. Catches a build that died mid-way
    (partial KB), which the export CLI's checksums alone would not detect.

    Only the ST corpus index carries a ``.index.ids.npy`` sidecar; the auxiliary
    synonym index keeps its row ids in the SQLite synonym table, so it is checked
    for non-emptiness only (no sidecar requirement)."""
    from metaharmonizer import _paths

    faiss_dir = _paths.FAISS_INDEX_DIR
    corpus = [
        p for p in faiss_dir.glob(f"st_*_{source}_{category}*.index")
        if p.stat().st_size > 0
    ]
    if not corpus:
        raise RuntimeError(
            f"no non-empty ST corpus FAISS index for {category}/{source} under "
            f"{faiss_dir} — build did not complete."
        )
    for idx in corpus:
        ids = idx.with_suffix(".index.ids.npy")
        if not ids.exists() or ids.stat().st_size == 0:
            raise RuntimeError(f"missing/empty ids sidecar for {idx.name} — partial build.")


def _build_fields() -> int:
    """Build the units of every installed target schema's data dictionary.
    Fail-closed: a unit that cannot be built (after the fetch retries) fails
    the build rather than ship a KB that silently lacks it."""
    from app.engine_adapter import _field_corpora, _schema_registry

    keys = sorted(key for key, schema in _schema_registry._discover().items() if schema.get("dictionary_path"))
    units = [unit for unit in _field_corpora.schema_units(keys) if unit.official is None]
    logger.info("building %d field corpus unit(s) for %s", len(units), ", ".join(keys))
    failures = 0
    for unit in units:
        t0 = time.perf_counter()
        try:
            entry = _field_corpora.build_units([unit]).get(unit.key, {})
        except Exception:  # noqa: BLE001 — report and continue with the next unit
            failures += 1
            logger.exception("FAILED to build unit %s", unit.key)
            continue
        logger.info(
            "built unit %s (%s terms) in %.1fs",
            unit.key, entry.get("rows", "?"), time.perf_counter() - t0,
        )
    unbuilt = [
        unit.key
        for unit in units
        if not _field_corpora.installed(unit)
        and (_field_corpora.read_manifest().get("units", {}).get(unit.key) or {}).get("rows") != 0
    ]
    if failures or unbuilt:
        logger.error("%d unit(s) failed; not installed: %s", failures, ", ".join(unbuilt) or "-")
        return 1
    logger.info("done — %d field corpus unit(s) built", len(units))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the ontology knowledge DB.")
    parser.add_argument(
        "--only",
        help="Build a single 'category/source' tuple (e.g. disease/ncit).",
    )
    parser.add_argument(
        "--fields",
        action="store_true",
        help="Build the per-field corpora the target schemas' data dictionaries name.",
    )
    args = parser.parse_args(argv)
    if args.fields:
        return _build_fields()

    tuples = LAUNCH_TUPLES
    if args.only:
        cat, _, src = args.only.partition("/")
        tuples = [(c, s, q) for (c, s, q) in LAUNCH_TUPLES if c == cat and s == src]
        if not tuples:
            logger.error("unknown tuple %r; known: %s", args.only,
                         ", ".join(f"{c}/{s}" for c, s, _ in LAUNCH_TUPLES))
            return 2

    failures = 0
    for category, source, seed in tuples:
        logger.info("building %s/%s …", category, source)
        try:
            _build_one(category, source, seed)
        except Exception:  # noqa: BLE001 — report and continue with the next tuple
            failures += 1
            logger.exception("FAILED to build %s/%s", category, source)

    if failures:
        logger.error("%d/%d tuple(s) failed", failures, len(tuples))
        return 1
    built_tuples = tuple((category, source) for category, source, _ in tuples)
    issues = installed_kb_issues(
        require_ontology_model=True,
        require_schema_model=False,
        tuples=built_tuples,
    )
    if issues:
        for issue in issues:
            logger.error("incomplete KB: %s", issue)
        return 1
    logger.info("done — %d tuple(s) built", len(tuples))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
