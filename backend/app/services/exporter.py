"""
MetaHarmonizer Dashboard — Exporter Service

Generates harmonized output files in multiple formats:
- CSV (harmonized metadata)
- cBioPortal clinical data format
- JSON mapping report (audit trail)
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import audit as audit_repo
from app.repositories import mappings as mappings_repo
from app.repositories import ontology as ontology_repo
from app.repositories import studies as studies_repo


# cBioPortal auto-populates these; they must not appear in a clinical data file.
BANNED_ATTRS: set[str] = {"MUTATION_COUNT", "FRACTION_GENOME_ALTERED"}

# Checklist: columns to strip before import (verbatim from the Study-checklist;
# extensible). Matched against the normalized attribute id and raw column name.
BANNED_SOURCE_COLUMNS: set[str] = {
    "PART_A_CONSENT",
    "PART_C_CONSENT",
    "MSI_COMMENTS",
    "IMPACT_CVR_TMB",
    "IMPACT_TMB",
    "COLLABORATION_ID",
    "PATIENTCURRENTAGE",
    "RELIGION",
}

# Smart (curly) quotes the checklist forbids in field values.
_SMART_QUOTES = str.maketrans({
    "\u201c": '"', "\u201d": '"',  # “ ”
    "\u2018": "'", "\u2019": "'",  # ‘ ’
})


def _norm_attr(name: str) -> str:
    """Normalize a column/attribute name for blocklist comparison."""
    return re.sub(r"[^A-Za-z0-9]+", "_", str(name).strip()).strip("_").upper()


def _is_banned(target_id: str, raw_column: str) -> bool:
    """True if the column is checklist-banned (by target id or raw name)."""
    if target_id in BANNED_ATTRS:
        return True
    return (
        _norm_attr(target_id) in BANNED_SOURCE_COLUMNS
        or _norm_attr(raw_column) in BANNED_SOURCE_COLUMNS
    )


def _strip_smart_quotes(text: str) -> str:
    """Replace curly quotes with straight ones (checklist: no smart quotes)."""
    return text.translate(_SMART_QUOTES)


# Cell values beginning with these can be executed as a formula by Excel /
# Google Sheets / LibreOffice when a CSV is opened — the classic "CSV injection".
_CSV_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _guard_formula_injection(value: Any) -> Any:
    """Neutralize spreadsheet formula-injection in a cell value.

    Prefixes a single quote to any string whose first character a spreadsheet
    could treat as a formula, so it renders as literal text. Plain numbers
    (e.g. ``-5``, ``+3.1``) are left untouched, and non-strings pass through.
    """
    if not isinstance(value, str) or not value:
        return value
    if value[0] not in _CSV_FORMULA_TRIGGERS:
        return value
    try:
        float(value)  # keep legitimate numbers like "-5" / "+3.1" intact
        return value
    except ValueError:
        return "'" + value


# Patient-level clinical attributes (cBioPortal convention). When a study is
# exported as a folder, these go to data_clinical_patient.txt and everything
# else (that isn't an ID) goes to data_clinical_sample.txt. Survival columns
# (``*_STATUS`` / ``*_MONTHS``) are always patient-level.
PATIENT_LEVEL_ATTRS: set[str] = {
    "SEX",
    "GENDER",
    "AGE",
    "AGE_AT_DIAGNOSIS",
    "RACE",
    "ETHNICITY",
    "ANCESTRY",
    "VITAL_STATUS",
    "OS_STATUS",
    "OS_MONTHS",
    "DFS_STATUS",
    "DFS_MONTHS",
    "PFS_STATUS",
    "PFS_MONTHS",
    "DSS_STATUS",
    "DSS_MONTHS",
}


def _is_patient_level(target_id: str) -> bool:
    """True if a cBioPortal attribute belongs in the patient clinical file."""
    if target_id in PATIENT_LEVEL_ATTRS:
        return True
    # Survival pairs use a free PREFIX (e.g. ``OS_STATUS`` / ``RFS_MONTHS``).
    return target_id.endswith("_STATUS") or target_id.endswith("_MONTHS")


# cBioPortal IDs allow only letters, numbers, points, underscores and hyphens.
_ID_INVALID = re.compile(r"[^A-Za-z0-9._-]")

# Survival *_STATUS values must be prefixed 0: (no event) or 1: (event).
_SURVIVAL_PREFIX: dict[str, str] = {
    "LIVING": "0:LIVING",
    "ALIVE": "0:LIVING",
    "DECEASED": "1:DECEASED",
    "DEAD": "1:DECEASED",
    "DISEASEFREE": "0:DiseaseFree",
    "DISEASE FREE": "0:DiseaseFree",
    "RECURRED": "1:Recurred/Progressed",
    "PROGRESSED": "1:Recurred/Progressed",
    "RECURRED/PROGRESSED": "1:Recurred/Progressed",
}

# BOOLEAN attribute values must be exactly TRUE or FALSE (validateData.py).
# Keys are the lower-cased values _infer_dtype types as BOOLEAN.
_BOOLEAN_TEXT: dict[str, str] = {
    "true": "TRUE", "yes": "TRUE", "1": "TRUE",
    "false": "FALSE", "no": "FALSE", "0": "FALSE",
}

# Predefined attributes validateData.py requires to be STRING, whatever their
# values look like (a coded 1/2 SEX column included).
_STRING_ATTRS: set[str] = {
    "CANCER_TYPE", "CANCER_TYPE_DETAILED", "DFS_STATUS", "GENDER", "HISTOLOGY",
    "KNOWN_MOLECULAR_CLASSIFIER", "METASTATIC_SITE", "OS_STATUS", "OTHER_SAMPLE_ID",
    "PATIENT_DISPLAY_NAME", "PRIMARY_SITE", "SAMPLE_CLASS", "SAMPLE_DISPLAY_NAME",
    "SAMPLE_TYPE", "SEX", "TUMOR_SITE", "TUMOR_TISSUE_SITE", "TUMOR_TYPE",
}


# Helpers


def _sanitize_id(value: Any) -> str:
    """Coerce a value into a cBioPortal-legal ID (letters, numbers, . _ -)."""
    text = "" if pd.isna(value) else str(value)
    return _ID_INVALID.sub("_", text)


def _normalize_survival(value: Any) -> str:
    """Prefix a survival-status value with 0:/1: if it isn't already."""
    text = "" if pd.isna(value) else str(value).strip()
    if not text or text[:2] in ("0:", "1:"):
        return text
    return _SURVIVAL_PREFIX.get(text.upper(), text)

def _find_id_column(df: pd.DataFrame, candidates: list[str]) -> str:
    """
    Find the best existing column in `df` that matches one of the candidate
    names (case-insensitive).  If none found, return the first column that
    contains mostly unique non-null values (heuristic for an ID column).
    As a last resort, synthesize a column name — the exporter will fill it
    with row indices.
    """
    lower_cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_cols:
            return lower_cols[cand.lower()]

    # Heuristic: find a column with high cardinality (likely an ID)
    for c in df.columns:
        non_null = df[c].dropna()
        if len(non_null) > 0 and non_null.nunique() / len(non_null) > 0.9:
            return c

    # Fallback: use first column
    return df.columns[0] if len(df.columns) > 0 else "_GENERATED_ID"


# Column selection (shared by every export)


def mapping_target(mapping: dict[str, Any]) -> str | None:
    """The schema field a mapping fills in an export, if any.

    An accepted mapping fills the curator's field (else the suggestion) and a
    pending one its suggestion. A rejected or unmapped column fills nothing,
    even if it still carries a ``curator_field`` from an earlier edit.
    """
    status = mapping.get("status")
    if status == "accepted":
        return mapping.get("curator_field") or mapping.get("matched_field") or None
    if status == "pending":
        return mapping.get("matched_field") or None
    return None


def _select_sources(
    mappings: list[dict[str, Any]],
    columns: Sequence[str],
    key: Callable[[str], str] | None = None,
) -> dict[str, tuple[str, str]]:
    """Choose one source column per schema field: ``{field key: (column, field)}``.

    A mapping a curator reviewed beats one the engine accepted on its own, which
    beats a pending suggestion; then higher confidence wins, then the column
    that comes first in the upload, so the choice never depends on the order
    mappings are stored in. ``key`` folds field names that must not repeat in an
    export (cBioPortal attribute ids).
    """
    position = {column: i for i, column in enumerate(columns)}
    best: dict[str, tuple[tuple[bool, bool, float, int], str, str]] = {}
    for m in mappings:
        raw, target = m.get("raw_column"), mapping_target(m)
        if raw not in position or not target:
            continue
        rank = (
            m["status"] == "accepted",
            bool(m.get("reviewed_at")),  # stamped by every curator decision
            float(m.get("confidence_score") or 0.0),
            -position[raw],
        )
        field_key = key(target) if key else target
        if field_key not in best or rank > best[field_key][0]:
            best[field_key] = (rank, raw, target)
    return {field_key: (raw, target) for field_key, (_rank, raw, target) in best.items()}


# Harmonized CSV

ColumnAction = Literal["renamed", "matched", "kept", "dropped"]
MappingStatus = Literal["accepted", "pending", "rejected", "unmapped"]
DropReason = Literal["no_target", "duplicate_target", "name_conflict"]


@dataclass(frozen=True)
class ColumnPlan:
    """How one source column appears in the harmonized CSV."""

    source: str
    target: str | None  # export column name; None when the column is dropped
    action: ColumnAction
    mapping_status: MappingStatus
    drop_reason: DropReason | None = None
    # For a dropped column, the source column that took its export name.
    conflicts_with: str | None = None


@dataclass(frozen=True)
class HarmonizedTable:
    """The harmonized CSV as text cells, plus the provenance of every change."""

    frame: pd.DataFrame  # exported cells (str), in export column order
    plan: list[ColumnPlan]  # one entry per source column, in source order
    rewritten: pd.DataFrame  # True where a cell was rewritten to its ontology term
    escaped: pd.DataFrame  # True where a cell was escaped against formula injection

    def to_csv(self) -> str:
        return self.frame.to_csv(index=False)


def _text_view(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Text cells for a typed frame, as a plain CSV round-trip would write them.

    Fallback for callers that only have the type-inferred frame; the export
    endpoints pass the file's original text instead.
    """
    text = pd.read_csv(io.StringIO(raw_df.to_csv(index=False)), dtype=str, keep_default_na=False)
    text.columns = raw_df.columns
    text.index = raw_df.index
    return text


def harmonize_table(
    raw_text: pd.DataFrame,
    raw_df: pd.DataFrame,
    mappings: list[dict[str, Any]],
    value_rewrites: dict[str, dict[str, str]],
) -> HarmonizedTable:
    """Build the harmonized table: rename raw columns to their accepted/curated
    mappings, drop unmapped columns, rewrite accepted cell values to their
    confirmed ontology terms (U5), and escape formula-like strings.

    ``raw_text`` holds the upload's original cell text and ``raw_df`` the same
    file read with type inference. Output cells keep the original text unless
    they are rewritten or escaped, so numbers and missing-value markers are not
    reformatted. A value's ontology row is found by its inferred or its
    original spelling (see :func:`_term`).
    """
    # One source column per schema field (see _select_sources): a CSV or
    # cBioPortal file can't carry duplicate column names, and the losers are
    # near-duplicate suggestions anyway.
    winners = _select_sources(mappings, list(raw_df.columns))
    rename_map: dict[str, str] = {raw: target for raw, target in winners.values()}
    source_of_target = {target: raw for raw, target in winners.values()}
    proposed = {
        m["raw_column"]: target
        for m in mappings
        if m["raw_column"] in raw_df.columns and (target := mapping_target(m))
    }
    mapped_targets = set(rename_map.values())
    status_by_raw = {m["raw_column"]: m["status"] for m in mappings}
    rejected_raw = {
        m["raw_column"]
        for m in mappings
        if m.get("status") == "rejected"
        and m.get("raw_column") in raw_df.columns
        and m.get("raw_column") not in mapped_targets
    }

    plan: list[ColumnPlan] = []
    columns: dict[str, pd.Series] = {}
    rewritten: dict[str, pd.Series] = {}
    escaped: dict[str, pd.Series] = {}
    # Preserve original column order for a stable, diff-friendly output.
    for raw in raw_df.columns:
        status = status_by_raw.get(raw, "unmapped")
        if status not in ("accepted", "pending", "rejected"):
            status = "unmapped"
        if raw in rename_map:
            target = rename_map[raw]
            action: ColumnAction = "matched" if target == raw else "renamed"
        elif raw in rejected_raw:
            target, action = raw, "kept"
        else:
            if raw in proposed:
                reason: DropReason = "duplicate_target"
                winner = source_of_target.get(proposed[raw])
            elif status == "rejected":
                reason, winner = "name_conflict", source_of_target.get(raw)
            else:
                reason, winner = "no_target", None
            plan.append(ColumnPlan(raw, None, "dropped", status, reason, winner))
            continue
        plan.append(ColumnPlan(raw, target, action, status))

        text = raw_text[raw]
        hit = pd.Series(False, index=text.index)
        # Rewrites belong to a field mapping: a kept (rejected) column is
        # exported as uploaded, even if terms for a field of the same name exist.
        lookup = value_rewrites.get(target) if action != "kept" else None
        if lookup:
            # Value-level rewrite (U5): replace accepted raw values with their
            # confirmed ontology term. Unmatched values pass through.
            terms = _terms(lookup, raw_df[raw], text)
            hit = terms.notna()
            text = text.where(~hit, terms)
        # Neutralize spreadsheet formula-injection in this human-facing CSV.
        # (The cBioPortal TSVs are machine-read by the importer, so they are
        # not escaped.)
        guarded = text.map(_guard_formula_injection)
        columns[target] = guarded
        rewritten[target] = hit
        escaped[target] = guarded != text

    index = raw_text.index
    return HarmonizedTable(
        frame=pd.DataFrame(columns, index=index, dtype=object),
        plan=plan,
        rewritten=pd.DataFrame(rewritten, index=index, dtype=bool),
        escaped=pd.DataFrame(escaped, index=index, dtype=bool),
    )


async def build_harmonized_table(
    db: AsyncSession,
    study_id: str,
    raw_df: pd.DataFrame,
    raw_text: pd.DataFrame | None = None,
) -> HarmonizedTable:
    """Load a study's mappings and confirmed rewrites, then build its table."""
    mappings = await mappings_repo.get_mappings(db, study_id)
    value_rewrites = await _build_value_rewrites(db, study_id)
    if raw_text is None:
        raw_text = _text_view(raw_df)
    return harmonize_table(raw_text, raw_df, mappings, value_rewrites)


async def export_harmonized_csv(
    db: AsyncSession,
    study_id: str,
    raw_df: pd.DataFrame,
    raw_text: pd.DataFrame | None = None,
) -> str:
    """Return the harmonized CSV text (see :func:`harmonize_table`)."""
    return (await build_harmonized_table(db, study_id, raw_df, raw_text)).to_csv()


class FieldRewrites(dict[str, str]):
    """One field's ``raw_value -> confirmed term`` lookup. ``reviewed`` holds
    the raw values whose term comes from a curator's decision."""

    def __init__(self) -> None:
        super().__init__()
        self.reviewed: set[str] = set()


def _term(lookup: Mapping[str, str], typed: str, text: str) -> str | None:
    """A cell's confirmed ontology term, if it has one.

    ``typed`` is the cell as the type-inferred frame spells it (``1.0``), which
    is how the pipeline keys an ontology row; ``text`` is the uploaded text
    (``1``), which is how a re-map after a schema edit keys it. A curator's
    decision wins over the engine's; otherwise the pipeline's spelling does.
    """
    keys = (typed,) if text == typed else (typed, text)
    reviewed = getattr(lookup, "reviewed", ())
    for key in sorted(keys, key=lambda k: k not in reviewed):
        if key in lookup:
            return lookup[key]
    return None


def _terms(lookup: Mapping[str, str], values: pd.Series, text: pd.Series) -> pd.Series:
    """:func:`_term` for a column: each cell's term, ``None`` where it has none.

    ``values`` is the type-inferred column and ``text`` its uploaded text. A
    missing cell never has a term. Each distinct pair of spellings is looked
    up once, so a large upload costs a few lookups per value, not per cell.
    """
    typed_codes, typed_uniques = pd.factorize(values.astype(str), use_na_sentinel=False)
    text_codes, text_uniques = pd.factorize(text, use_na_sentinel=False)
    n = len(text_uniques)  # pair code = typed code * n + text code
    pairs, codes = np.unique(typed_codes.astype(np.int64) * n + text_codes, return_inverse=True)
    found = np.array(
        [_term(lookup, typed_uniques[p // n], text_uniques[p % n]) for p in pairs], dtype=object
    )[codes.ravel()]
    found[values.isna().to_numpy()] = None
    return pd.Series(found, index=text.index, dtype=object)


async def _build_value_rewrites(
    db: AsyncSession, study_id: str
) -> dict[str, FieldRewrites]:
    """Map each harmonized field to its accepted ``raw_value -> term`` rewrites."""
    rewrites: dict[str, FieldRewrites] = {}
    for o in await ontology_repo.get_ontology_mappings(db, study_id):
        if o["status"] != "accepted":
            continue
        term = o.get("curator_term") or o.get("ontology_term")
        if not term:
            continue
        lookup = rewrites.setdefault(o["field_name"], FieldRewrites())
        raw, reviewed = str(o["raw_value"]), bool(o.get("reviewed_at"))
        if raw in lookup.reviewed and not reviewed:
            continue  # a curator's term beats an engine row for the same value
        lookup[raw] = str(term)
        if reviewed:
            lookup.reviewed.add(raw)
    return rewrites


# cBioPortal Format

_HIGH_PRIORITY_ATTRS: set[str] = {
    "PATIENT_ID", "SAMPLE_ID", "CANCER_TYPE", "CANCER_TYPE_DETAILED",
    "GENDER", "SEX", "AGE", "OS_STATUS", "OS_MONTHS", "TUMOR_SITE",
}


def _infer_dtype(series: pd.Series) -> str:
    """Infer a cBioPortal data type (NUMBER / BOOLEAN / STRING) for a column."""
    non_null = series.dropna()
    # TRUE/FALSE columns are read as booleans, which also pass as numbers.
    if len(non_null) and pd.api.types.infer_dtype(non_null, skipna=True) == "boolean":
        return "BOOLEAN"
    try:
        pd.to_numeric(non_null)
        return "NUMBER"
    except (ValueError, TypeError):
        pass
    try:
        unique_vals = set(non_null.astype(str).str.lower().unique())
    except (AttributeError, TypeError):
        unique_vals = set()
    if unique_vals and unique_vals <= {"true", "false", "yes", "no", "0", "1"}:
        return "BOOLEAN"
    return "STRING"


def _cbio_id(field: str) -> str:
    """cBioPortal attribute id for a schema field (``body site`` → ``BODY_SITE``)."""
    return field.upper().replace(" ", "_")


def _clinical_column_specs(
    mappings: list[dict[str, Any]], raw_df: pd.DataFrame
) -> list[dict[str, Any]]:
    """Build cBioPortal column specs, in upload order, for the columns chosen to
    fill a schema field — the same choice as the Harmonized CSV.

    Excludes PATIENT_ID / SAMPLE_ID (injected per-file by the caller) and
    checklist-banned columns, which can't fill an attribute.
    """
    allowed = [
        m
        for m in mappings
        if not (target := mapping_target(m))
        or not _is_banned(_cbio_id(target), str(m.get("raw_column", "")))
    ]
    winners = _select_sources(allowed, list(raw_df.columns), key=_cbio_id)
    position = {column: i for i, column in enumerate(raw_df.columns)}
    cols: list[dict[str, Any]] = []
    for target_id, (raw, target) in sorted(winners.items(), key=lambda w: position[w[1][0]]):
        if target_id in {"PATIENT_ID", "SAMPLE_ID"}:
            continue
        cols.append(
            {
                "raw": raw,
                "target": target_id,
                "display": target.replace("_", " ").title(),
                "description": target.replace("_", " ").capitalize(),
                "dtype": "STRING" if target_id in _STRING_ATTRS else _infer_dtype(raw_df[raw]),
                "priority": 10 if target_id in _HIGH_PRIORITY_ATTRS else 1,
            }
        )
    return cols


def _id_spec(
    target_id: str, raw_src: str, display: str, description: str
) -> dict[str, Any]:
    return {
        "raw": raw_src,
        "target": target_id,
        "display": display,
        "description": description,
        "dtype": "STRING",
        "priority": 10,
    }


def _id_raw_source(
    mappings: list[dict[str, Any]],
    raw_df: pd.DataFrame,
    target_id: str,
    fallback_candidates: list[str],
) -> str:
    """The column feeding an ID attribute: the column chosen for that field
    (the same choice as every export), else a name/uniqueness heuristic."""
    winner = _select_sources(mappings, list(raw_df.columns), key=_cbio_id).get(target_id)
    return winner[0] if winner else _find_id_column(raw_df, fallback_candidates)


def _write_clinical_tsv(
    cols: list[dict[str, Any]],
    raw_df: pd.DataFrame,
    value_rewrites: dict[str, dict[str, str]] | None = None,
    raw_text: pd.DataFrame | None = None,
) -> str:
    """Write a cBioPortal 5-row-header clinical TSV for the given column specs.

    ``value_rewrites`` maps a target attribute id (e.g. ``SEX``) to a
    ``raw_value -> confirmed term`` lookup so the exported cells carry the
    curator-resolved values (U5), not the raw ones.

    ``raw_text`` is the upload's original cell text (indexed like the full
    file), so a cell that isn't rewritten keeps its uploaded text: sample
    ``0012`` stays ``0012``, as in the Harmonized CSV. Missing values are
    written empty.
    """
    rewrites = value_rewrites or {}
    targets = {c["target"] for c in cols}
    survival_status_with_months = {
        c["target"]
        for c in cols
        if c["target"].endswith("_STATUS") and f"{c['target'][:-7]}_MONTHS" in targets
    }
    text_df = (raw_text if raw_text is not None else _text_view(raw_df)).loc[raw_df.index]
    sources = {c["raw"] for c in cols if c["raw"] in raw_df.columns}
    typed_cells = {src: raw_df[src].tolist() for src in sources}
    text_cells = {src: text_df[src].tolist() for src in sources}

    rows: list[list[str]] = []
    for i in range(len(raw_df)):
        out_row: list[str] = []
        for c in cols:
            src, target_id = c["raw"], c["target"]
            value = typed_cells[src][i] if src in sources else None
            text = "" if value is None or pd.isna(value) else str(text_cells[src][i])
            if target_id in ("PATIENT_ID", "SAMPLE_ID"):
                out_row.append(_sanitize_id(text))
            elif target_id in survival_status_with_months:
                out_row.append(_tsv_cell(_normalize_survival(text)))
            elif not text:
                out_row.append("")
            else:
                # Apply the curator-confirmed value rewrite (U5).
                lookup = rewrites.get(target_id)
                term = _term(lookup, str(value), text) if lookup else None
                out_row.append(_tsv_cell(term if term is not None else text))
        rows.append(out_row)

    # cBioPortal accepts only TRUE / FALSE in a BOOLEAN attribute: write yes/no
    # and true/false that way, and declare a column holding anything else (for
    # example, after a value rewrite) as STRING. Likewise a NUMBER column whose
    # values were rewritten to terms.
    dtypes = [c["dtype"] for c in cols]
    for j, dtype in enumerate(dtypes):
        if dtype == "NUMBER":
            if not all(_is_number(r[j]) for r in rows if r[j].strip()):
                dtypes[j] = "STRING"
            continue
        if dtype != "BOOLEAN":
            continue
        values = {r[j].strip().lower() for r in rows if r[j].strip()}
        if values.issubset(_BOOLEAN_TEXT):
            for r in rows:
                if r[j].strip():
                    r[j] = _BOOLEAN_TEXT[r[j].strip().lower()]
        else:
            dtypes[j] = "STRING"

    # Plain tab-separated lines: cBioPortal reads quotation marks as part of a
    # value, so cells are never quoted (_tsv_cell keeps them on one line).
    # Per spec, only the FIRST field of each metadata row carries the '#'.
    header_rows = [
        [c["display"] for c in cols],
        [c["description"] for c in cols],
        dtypes,
        [str(c["priority"]) for c in cols],
    ]
    lines = ["#" + "\t".join(row) for row in header_rows]
    lines.append("\t".join(c["target"] for c in cols))  # attribute IDs (no '#')
    lines.extend("\t".join(row) for row in rows)
    return "".join(line + "\n" for line in lines)


_TSV_BREAKS = re.compile(r"[\t\r\n]+")


def _is_number(text: str) -> bool:
    """Whether validateData.py reads ``text`` as a NUMBER value."""
    try:
        float(text)
    except ValueError:
        return False
    return True


def _tsv_cell(text: str) -> str:
    """A clinical-file value on one line: tabs and line breaks become a space,
    curly quotes straight ones (checklist: no smart quotes)."""
    return _strip_smart_quotes(_TSV_BREAKS.sub(" ", text))


def _rewrites_by_target(
    field_rewrites: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    """Re-key field-name rewrites to cBioPortal target ids (UPPER_CASE)."""
    return {_cbio_id(field): lookup for field, lookup in field_rewrites.items()}


async def export_cbioportal(
    db: AsyncSession,
    study_id: str,
    raw_df: pd.DataFrame,
    raw_text: pd.DataFrame | None = None,
) -> str:
    """
    Produce a single cBioPortal-format clinical data file (all attributes in
    one sample-level file), per the official spec:
    https://docs.cbioportal.org/file-formats/#clinical-data

    Header rows: display names, descriptions, data types, priority, then the
    UPPER_CASE attribute IDs. PATIENT_ID and SAMPLE_ID are always present.
    Curator-confirmed value rewrites (U5) are applied to the cells; other cells
    keep the uploaded text (``raw_text``) when given.
    """
    mappings = await mappings_repo.get_mappings(db, study_id)
    specs = _clinical_column_specs(mappings, raw_df)

    patient_src = _id_raw_source(
        mappings, raw_df, "PATIENT_ID",
        ["subject_id", "patient_id", "participant_id", "case_id"],
    )
    sample_src = _id_raw_source(
        mappings, raw_df, "SAMPLE_ID",
        ["sample_id", "run_id", "sampleid", "accession"],
    )

    if not specs and raw_df.columns.empty:
        return "# No mappings available for export\n"

    cols = [
        _id_spec("PATIENT_ID", patient_src, "Patient Identifier", "Unique patient identifier"),
        _id_spec("SAMPLE_ID", sample_src, "Sample Identifier", "Unique sample identifier"),
        *specs,
    ]
    rewrites = _rewrites_by_target(await _build_value_rewrites(db, study_id))
    return _write_clinical_tsv(cols, raw_df, rewrites, raw_text)


# cBioPortal study folder (validateData.py-ready)

def _meta_study(cancer_study_identifier: str, name: str, description: str) -> str:
    # No ``add_global_case_list`` — the checklist says not to use it; we ship an
    # explicit case_lists/cases_all.txt instead (and the two would collide).
    return (
        f"type_of_cancer: mixed\n"
        f"cancer_study_identifier: {cancer_study_identifier}\n"
        f"name: {name}\n"
        f"description: {description}\n"
    )


def _meta_clinical(cancer_study_identifier: str, datatype: str, data_filename: str) -> str:
    return (
        f"cancer_study_identifier: {cancer_study_identifier}\n"
        f"genetic_alteration_type: CLINICAL\n"
        f"datatype: {datatype}\n"
        f"data_filename: {data_filename}\n"
    )


def _case_list_all(cancer_study_identifier: str, sample_ids: list[str]) -> str:
    """The ``cases_all.txt`` case list (every sample in the study).

    cBioPortal expects a tab-separated list of sample IDs under
    ``case_lists/cases_all.txt`` with the ``<study>_all`` stable id.
    """
    ids = "\t".join(sample_ids)
    return (
        f"cancer_study_identifier: {cancer_study_identifier}\n"
        f"stable_id: {cancer_study_identifier}_all\n"
        f"case_list_category: all_cases_in_study\n"
        f"case_list_name: All samples\n"
        f"case_list_description: All samples ({len(sample_ids)} samples)\n"
        f"case_list_ids: {ids}\n"
    )


# Permissive OSS license shipped in the study folder (checklist: "make sure the
# LICENSE is added to the study folder"). The harmonized clinical data is the
# curators' to license; we ship a CC0 public-domain dedication as a safe default
# for public datahub studies. Curators can replace it.
_LICENSE_TEXT = (
    "CC0 1.0 Universal (CC0 1.0) Public Domain Dedication\n"
    "\n"
    "This clinical study folder was harmonized with MetaHarmonizer. The data\n"
    "curators are the source of, and hold any rights to, the underlying data.\n"
    "To the extent possible under law, the curators have waived all copyright\n"
    "and related or neighboring rights to this dataset. Replace this file with\n"
    "the license that applies to your data before distribution.\n"
    "\n"
    "See https://creativecommons.org/publicdomain/zero/1.0/ for the full text.\n"
)


def _id_values(raw_df: pd.DataFrame, raw_text: pd.DataFrame, column: str) -> list[str]:
    """A column's cells as cBioPortal IDs, from the uploaded text ("" if missing)."""
    if column not in raw_df.columns:
        return []
    return [
        "" if pd.isna(value) else _sanitize_id(text)
        for value, text in zip(raw_df[column], raw_text[column])
    ]


def _sample_ids_for_case_list(raw_ids: list[str]) -> list[str]:
    """Non-empty sample IDs, de-duplicated in first-seen order."""
    return list(dict.fromkeys(sid for sid in raw_ids if sid))


async def export_cbioportal_study(
    db: AsyncSession,
    study_id: str,
    raw_df: pd.DataFrame,
    cancer_study_identifier: str | None = None,
    raw_text: pd.DataFrame | None = None,
) -> bytes:
    """
    Produce a cBioPortal study folder as a zip, ready for ``validateData.py``:

        meta_study.txt
        meta_clinical_patient.txt
        data_clinical_patient.txt
        meta_clinical_sample.txt
        data_clinical_sample.txt
        case_lists/cases_all.txt
        LICENSE

    The clinical attributes are split per the curation checklist ("the clinical
    file should be split to patient and sample level attribute files"):
    patient-level attributes (sex, survival, age, ancestry, ...) go to the
    patient file with one row per unique patient; everything else goes to the
    sample file with one row per sample. PATIENT_ID appears in both so samples
    link to patients.
    """
    study = await studies_repo.get_study(db, study_id) or {}
    identifier = cancer_study_identifier or _sanitize_id(
        study.get("name") or study_id
    ).lower()
    name = study.get("name") or study_id
    description = study.get("description") or f"Harmonized clinical data for {name}."

    mappings = await mappings_repo.get_mappings(db, study_id)
    specs = _clinical_column_specs(mappings, raw_df)

    patient_src = _id_raw_source(
        mappings, raw_df, "PATIENT_ID",
        ["subject_id", "patient_id", "participant_id", "case_id"],
    )
    sample_src = _id_raw_source(
        mappings, raw_df, "SAMPLE_ID",
        ["sample_id", "run_id", "sampleid", "accession"],
    )

    patient_id_spec = _id_spec(
        "PATIENT_ID", patient_src, "Patient Identifier", "Unique patient identifier"
    )
    sample_id_spec = _id_spec(
        "SAMPLE_ID", sample_src, "Sample Identifier", "Unique sample identifier"
    )

    patient_attr_specs = [s for s in specs if _is_patient_level(s["target"])]
    sample_attr_specs = [s for s in specs if not _is_patient_level(s["target"])]

    # Patient file: one row per unique patient (cBioPortal requires unique
    # PATIENT_ID rows), by the ID as exported. Sample file: one row per sample,
    # PATIENT_ID links back.
    patient_cols = [patient_id_spec, *patient_attr_specs]
    sample_cols = [patient_id_spec, sample_id_spec, *sample_attr_specs]

    text_df = raw_text if raw_text is not None else _text_view(raw_df)
    patient_ids = _id_values(raw_df, text_df, patient_src)
    patient_df = (
        raw_df[~pd.Series(patient_ids, index=raw_df.index).duplicated().to_numpy()]
        if patient_ids
        else raw_df
    )

    rewrites = _rewrites_by_target(await _build_value_rewrites(db, study_id))
    data_clinical_patient = _write_clinical_tsv(patient_cols, patient_df, rewrites, text_df)
    data_clinical_sample = _write_clinical_tsv(sample_cols, raw_df, rewrites, text_df)
    sample_ids = _sample_ids_for_case_list(_id_values(raw_df, text_df, sample_src))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("meta_study.txt", _meta_study(identifier, name, description))
        zf.writestr(
            "meta_clinical_patient.txt",
            _meta_clinical(identifier, "PATIENT_ATTRIBUTES", "data_clinical_patient.txt"),
        )
        zf.writestr("data_clinical_patient.txt", data_clinical_patient)
        zf.writestr(
            "meta_clinical_sample.txt",
            _meta_clinical(identifier, "SAMPLE_ATTRIBUTES", "data_clinical_sample.txt"),
        )
        zf.writestr("data_clinical_sample.txt", data_clinical_sample)
        if sample_ids:
            zf.writestr("case_lists/cases_all.txt", _case_list_all(identifier, sample_ids))
        zf.writestr("LICENSE", _LICENSE_TEXT)
    return buf.getvalue()


# Labeled dataset export (G9 — curator-confirmed mappings for retraining)

LABELED_FIELDNAMES = [
    "record_type",
    "raw_column",
    "raw_sample_values",
    "accepted_target",
    "ontology_id",
    "confidence",
    "stage",
    "method",
    "schema_version",
    "ontology_version",
]


def _distinct_sample_values(raw_df: pd.DataFrame, column: str, limit: int = 5) -> str:
    """Up to ``limit`` distinct non-null values from a raw column, ';'-joined."""
    if column not in raw_df.columns:
        return ""
    seen: list[str] = []
    for v in raw_df[column]:
        if pd.isna(v):
            continue
        s = str(v).strip()
        if s and s not in seen:
            seen.append(s)
        if len(seen) >= limit:
            break
    return ";".join(seen)


async def _labeled_rows(
    db: AsyncSession, study_id: str, raw_df: pd.DataFrame
) -> list[dict[str, Any]]:
    """Curator-confirmed mappings as labeled training rows (G9).

    Two record types in one dataset:
    - ``schema_mapping``: an accepted raw column -> target field, with a few
      distinct sample values as the input signal.
    - ``ontology_mapping``: an accepted value -> ontology term/id.

    Only **accepted** (human-confirmed) decisions are emitted — this is a
    labeled dataset, not the raw engine output.
    """
    study = await studies_repo.get_study(db, study_id) or {}
    schema_version = study.get("schema_version_id")
    schema_version = "" if schema_version is None else str(schema_version)

    rows: list[dict[str, Any]] = []

    for m in await mappings_repo.get_mappings(db, study_id):
        if m["status"] != "accepted":
            continue
        target = m.get("curator_field") or m.get("matched_field")
        if not target:
            continue
        rows.append(
            {
                "record_type": "schema_mapping",
                "raw_column": m["raw_column"],
                "raw_sample_values": _distinct_sample_values(raw_df, m["raw_column"]),
                "accepted_target": target,
                "ontology_id": "",
                "confidence": m.get("confidence_score") or "",
                "stage": m.get("stage") or "",
                "method": m.get("method") or "",
                "schema_version": schema_version,
                "ontology_version": "",
            }
        )

    for o in await ontology_repo.get_ontology_mappings(db, study_id):
        if o["status"] != "accepted":
            continue
        term = o.get("curator_term") or o.get("ontology_term")
        if not term:
            continue
        rows.append(
            {
                "record_type": "ontology_mapping",
                "raw_column": o["field_name"],
                "raw_sample_values": str(o["raw_value"]),
                "accepted_target": term,
                "ontology_id": o.get("ontology_id") or "",
                "confidence": o.get("confidence_score") or "",
                "stage": "",
                "method": "",
                "schema_version": schema_version,
                "ontology_version": "",
            }
        )

    return rows


async def export_labeled_dataset(
    db: AsyncSession, study_id: str, raw_df: pd.DataFrame, fmt: str = "csv"
) -> str:
    """Curator-confirmed mappings as a labeled dataset (G9), CSV or JSONL.

    Row shape: (record_type, raw_column, raw_sample_values, accepted_target,
    ontology_id, confidence, stage, method, schema_version, ontology_version).
    """
    rows = await _labeled_rows(db, study_id, raw_df)

    if fmt == "jsonl":
        return "\n".join(json.dumps(r, default=str) for r in rows) + ("\n" if rows else "")

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=LABELED_FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue()


# Global labeled dataset (G9/U16 — nightly corpus of every confirmed mapping)

GLOBAL_LABELED_FIELDNAMES = ["study_id", *LABELED_FIELDNAMES]


async def _load_study_raw_df(study: dict[str, Any]) -> pd.DataFrame:
    """Best-effort load of a study's uploaded file; empty frame if it's gone
    (sample-value context is then omitted, but the confirmed labels still ship)."""
    from app.core.storage import get_storage

    key = study.get("file_path")
    storage = get_storage()
    if not key or not storage.exists(key):
        return pd.DataFrame()
    sep = "\t" if Path(key).suffix.lower() in (".tsv", ".txt") else ","
    try:
        with storage.local(key) as local_csv:
            return pd.read_csv(local_csv, sep=sep, low_memory=False)
    except Exception:  # noqa: BLE001 — a broken file must not abort the nightly dump
        return pd.DataFrame()


async def export_all_labeled(db: AsyncSession, fmt: str = "csv") -> str:
    """Every study's curator-confirmed mappings as one labeled dataset (G9/U16).

    Same row shape as the per-study export, prefixed with ``study_id``. Only
    accepted decisions are emitted. Per-study failures are skipped so one bad
    study can't abort the whole corpus."""
    studies = await studies_repo.list_studies(db, owner_id=None)
    all_rows: list[dict[str, Any]] = []
    for study in studies:
        sid = study.get("id")
        if not sid:
            continue
        try:
            raw_df = await _load_study_raw_df(study)
            rows = await _labeled_rows(db, sid, raw_df)
        except Exception:  # noqa: BLE001
            continue
        for r in rows:
            all_rows.append({"study_id": sid, **r})

    if fmt == "jsonl":
        return "\n".join(json.dumps(r, default=str) for r in all_rows) + (
            "\n" if all_rows else ""
        )

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=GLOBAL_LABELED_FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    for r in all_rows:
        writer.writerow(r)
    return buf.getvalue()


# LinkML export gate (G9 — controlled-vocabulary check before export)


def _parse_clinical_columns(tsv_text: str) -> dict[str, list[str]]:
    """Parse a cBioPortal clinical TSV back into ``{attr_id: [values]}``.

    The 5th line (index 4) is the UPPER_CASE attribute id row; data follows.
    """
    lines = tsv_text.split("\n")
    if len(lines) <= 5:
        return {}
    header = lines[4].split("\t")
    columns: dict[str, list[str]] = {h: [] for h in header}
    for line in lines[5:]:
        if not line:
            continue
        cells = line.split("\t")
        for i, h in enumerate(header):
            columns[h].append(cells[i] if i < len(cells) else "")
    return columns


async def linkml_check(
    db: AsyncSession,
    study_id: str,
    raw_df: pd.DataFrame,
    raw_text: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Run the LinkML controlled-vocabulary gate on the harmonized output.

    Validates the exact cBioPortal sample-file values (after curator value
    rewrites + survival prefixing) against the checklist vocabularies. Returns
    ``{"ok": bool, "violations": [...]}``.
    """
    from app.services import linkml_gate

    tsv = await export_cbioportal(db, study_id, raw_df, raw_text)
    columns = _parse_clinical_columns(tsv)
    violations = linkml_gate.validate_clinical_columns(columns)
    return {"ok": not violations, "violations": violations}


# JSON Mapping Report

async def export_mapping_report(db: AsyncSession, study_id: str) -> str:
    """
    Produce a JSON audit report of all mapping decisions.
    """
    study = await studies_repo.get_study(db, study_id)
    mappings = await mappings_repo.get_mappings(db, study_id)
    onto = await ontology_repo.get_ontology_mappings(db, study_id)
    audit = await audit_repo.get_audit_log(db, study_id)

    report = {
        "study": study,
        "schema_mappings": mappings,
        "ontology_mappings": onto,
        "audit_log": audit,
        "summary": {
            "total_columns": len(mappings),
            "accepted": sum(1 for m in mappings if m["status"] == "accepted"),
            "rejected": sum(1 for m in mappings if m["status"] == "rejected"),
            "pending": sum(1 for m in mappings if m["status"] == "pending"),
        },
    }
    return json.dumps(report, indent=2, default=str)
