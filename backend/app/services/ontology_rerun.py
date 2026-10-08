"""Re-run value→ontology mapping for a single column after its schema field
changed in review.

Ontology mappings are first computed at harmonize time from the *engine's
proposed* fields. When a curator edits a column to a different field, the value
codes can become stale — this keeps them consistent:

- moved **into** an ontology-bearing field (disease/body_site/treatment) → add codes,
- moved **out** of one → drop the now-stale codes, except for values another
  column still mapped to that field shares (ontology rows are per field).

Best-effort: any failure returns zero counts and leaves existing data untouched,
so a schema edit is never blocked by the ontology re-run.
"""
from __future__ import annotations

import logging

import anyio
import pandas as pd

from app.core.storage import get_storage
from app.engine_adapter import get_engine
from app.repositories import engine_proposals as proposal_repo
from app.repositories import learned_decisions as learned_repo
from app.repositories import mappings as mappings_repo
from app.repositories import ontology as ontology_repo
from app.repositories import studies as studies_repo
from app.services import engine_proposal_cache as proposal_cache
from app.services.exporter import mapping_target
from app.services.harmonizer import supports_ontology_mapping

logger = logging.getLogger(__name__)


def _value_forms(file_key: str, columns: list[str]) -> dict[str, dict[str, str]]:
    """Each column's distinct non-empty values, ``{uploaded text: inferred text}``.

    The pipeline keys a value's ontology row by its type-inferred form
    (``1.0``, ``True``); a re-map keys it by the uploaded text (``1``, ``TRUE``),
    as the curator sees it. Columns missing from the file are left out.
    """
    sep = "\t" if str(file_key).lower().endswith((".tsv", ".txt")) else ","
    wanted = set(columns).__contains__
    with get_storage().local(file_key) as local_csv:
        text = pd.read_csv(local_csv, sep=sep, usecols=wanted, dtype=str)
        typed = pd.read_csv(local_csv, sep=sep, usecols=wanted, low_memory=False)
    forms: dict[str, dict[str, str]] = {}
    for column in text.columns:
        pairs: dict[str, str] = {}
        for raw, value in zip(text[column], typed[column]):
            if pd.isna(raw) or not str(raw).strip():
                continue
            pairs.setdefault(str(raw), str(raw) if pd.isna(value) else str(value))
        forms[column] = pairs
    return forms


async def rerun_column_ontology(
    db,
    *,
    study_id: str,
    file_key: str | None,
    raw_column: str,
    old_field: str | None,
    new_field: str | None,
) -> dict[str, int]:
    """Re-map one column's values after its field changed. Returns
    ``{"added": n, "removed": m}``. Does not commit — the caller owns the txn."""
    if not supports_ontology_mapping(old_field) and not supports_ontology_mapping(new_field):
        return {"added": 0, "removed": 0}
    if not raw_column or not file_key:
        return {"added": 0, "removed": 0}

    # Ontology rows belong to a field, not a column: another column that still
    # fills one of these fields keeps the rows for the values it shares.
    fields = {f for f in (old_field, new_field) if f}
    mappings = await mappings_repo.get_mappings(db, study_id)
    sharing = {
        f: [
            m["raw_column"]
            for m in mappings
            if m.get("raw_column") and m["raw_column"] != raw_column and mapping_target(m) == f
        ]
        for f in fields
    }
    try:
        forms = await anyio.to_thread.run_sync(
            _value_forms, file_key, [raw_column, *{c for cs in sharing.values() for c in cs}]
        )
    except Exception as exc:  # noqa: BLE001 — a missing/renamed column must not break the edit
        logger.warning("ontology re-run: could not read column %r: %s", raw_column, exc)
        return {"added": 0, "removed": 0}
    pairs = forms.get(raw_column, {})
    if not pairs:
        return {"added": 0, "removed": 0}
    values = list(pairs)
    spellings = set(pairs) | set(pairs.values())

    # Fresh engine output for the new field (empty when it isn't ontology-bearing).
    new_rows: list[dict] = []
    if supports_ontology_mapping(new_field):
        raw_df = pd.DataFrame({raw_column: values})
        schema_mappings = [
            {"raw_column": raw_column, "matched_field": new_field, "curator_field": new_field}
        ]
        try:
            engine = get_engine()
            health = engine.health()
            study = await studies_repo.get_study(db, study_id)
            _, ontology_scope = proposal_cache.scopes(
                schema_version_id=study.get("schema_version_id") if study else None,
                ontology_snapshot_id=study.get("ontology_snapshot_id") if study else None,
                target_schema=None,
                engine_version=health.version,
            )
            inputs = {
                learned_repo.ontology_key(str(new_field), value): (
                    str(new_field), value
                )
                for value in values
            }
            cached = await proposal_repo.lookup(
                db,
                scope_key=ontology_scope,
                kind="ontology",
                keys=list(inputs),
            )
            hydrated = proposal_cache.hydrate_ontology(inputs, cached)
            if hydrated is not None:
                new_rows = hydrated
            else:
                new_rows = await anyio.to_thread.run_sync(
                    engine.map_values, raw_df, schema_mappings
                )
                await proposal_repo.upsert_many(
                    db,
                    scope_key=ontology_scope,
                    kind="ontology",
                    proposals=proposal_cache.ontology_proposals(new_rows),
                    engine_version=health.version,
                )
        except Exception as exc:  # noqa: BLE001 — never let the engine break the edit
            logger.warning("ontology re-run: engine map_values failed: %s", exc)
            new_rows = []

    removed = 0
    for field in fields:
        shared = {k for c in sharing[field] for pair in forms.get(c, {}).items() for k in pair}
        removed += await ontology_repo.delete_unreviewed_ontology(
            db, study_id, {field}, spellings - shared
        )

    # Skip values that already have a row for the new field, in either spelling
    # (don't clobber the curator's decisions or duplicate a shared row).
    existing = (
        await ontology_repo.existing_value_keys(db, study_id, {new_field}, spellings)
        if supports_ontology_mapping(new_field)
        else set()
    )
    fresh = [
        r
        for r in new_rows
        if not any(
            (r.get("field_name"), key) in existing
            for key in (r.get("raw_value"), pairs.get(r.get("raw_value")))
        )
    ]
    if fresh:
        await ontology_repo.insert_ontology_mappings(db, study_id, fresh)
    return {"added": len(fresh), "removed": removed}
