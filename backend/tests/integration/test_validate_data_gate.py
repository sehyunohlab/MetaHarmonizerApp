"""Integration gate: run cBioPortal's real ``validateData.py`` on our export.

This is the G9 "final gate" — the source of truth for whether a generated
study folder is cBioPortal-ingestible. It does NOT vendor the validator (that
lives in ``cBioPortal/datahub-study-curation-tools`` /
``cBioPortal/cbioportal``); instead it invokes whatever validator the host
points at, so CI can wire it to a checked-out copy.

Enable by setting ``CBIO_VALIDATE_DATA`` to the path of ``validateData.py``.
When unset (local dev, lightweight venv), the test skips — it is a CI gate, not
a unit test. Runs the validator in offline mode (``-n``, no portal connection)
on a temp directory we extract our ZIP into.
"""

from __future__ import annotations

import asyncio
import io
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("pandas")
import pandas as pd  # noqa: E402

from app.services import exporter  # noqa: E402


VALIDATOR = os.getenv("CBIO_VALIDATE_DATA")


def _patch_repos(monkeypatch, mappings, study):
    async def _get_mappings(db, study_id):
        return mappings

    async def _get_study(db, study_id):
        return study

    async def _get_ontology(db, study_id):
        return []

    monkeypatch.setattr(exporter.mappings_repo, "get_mappings", _get_mappings)
    monkeypatch.setattr(exporter.studies_repo, "get_study", _get_study)
    monkeypatch.setattr(exporter.ontology_repo, "get_ontology_mappings", _get_ontology)


def _sample_study_zip(monkeypatch) -> bytes:
    # Read like the export endpoints read an upload: type-inferred and as text.
    upload = (
        "subject,samp,gender,os_status,os_months,sample_type,ffpe,smoker,note\n"
        'p1,0012,Male,LIVING,10.5,Primary,yes,TRUE,"two\nlines"\n'
        'p1,0013,Male,LIVING,10.5,Metastasis,No,FALSE,"say ""hi"""\n'
        "p2,0014,Female,DECEASED,22.0,Primary,no,,plain\n"
        "p3,0015,Male,LIVING,5.0,Primary,YES,TRUE,\n"
    )
    raw_df = pd.read_csv(io.StringIO(upload), low_memory=False)
    raw_text = pd.read_csv(io.StringIO(upload), dtype=str, keep_default_na=False)
    mappings = [
        {"raw_column": "subject", "matched_field": "PATIENT_ID", "status": "accepted"},
        # Zero-padded sample IDs must survive (pandas reads them as numbers).
        {"raw_column": "samp", "matched_field": "SAMPLE_ID", "status": "accepted"},
        {"raw_column": "gender", "matched_field": "SEX", "status": "accepted"},
        {"raw_column": "os_status", "matched_field": "OS_STATUS", "status": "accepted"},
        {"raw_column": "os_months", "matched_field": "OS_MONTHS", "status": "accepted"},
        {"raw_column": "sample_type", "matched_field": "SAMPLE_TYPE", "status": "accepted"},
        # yes/no text is typed BOOLEAN, which cBioPortal only accepts as TRUE/FALSE.
        {"raw_column": "ffpe", "matched_field": "FFPE", "status": "accepted"},
        # TRUE/FALSE is read as booleans, which must not be declared NUMBER.
        {"raw_column": "smoker", "matched_field": "SMOKER", "status": "accepted"},
        # A line break or quotes in a value must not break the file.
        {"raw_column": "note", "matched_field": "NOTE", "status": "accepted"},
    ]
    _patch_repos(monkeypatch, mappings, {"name": "Validate Test Study"})
    return asyncio.run(
        exporter.export_cbioportal_study(None, "study1", raw_df, raw_text=raw_text)
    )


@pytest.mark.skipif(
    not VALIDATOR,
    reason="Set CBIO_VALIDATE_DATA to cBioPortal validateData.py to run this gate.",
)
def test_generated_study_passes_validate_data(monkeypatch, tmp_path):
    if not Path(VALIDATOR).exists():
        pytest.skip(f"CBIO_VALIDATE_DATA points to a missing file: {VALIDATOR}")

    zip_bytes = _sample_study_zip(monkeypatch)
    study_dir = tmp_path / "study"
    study_dir.mkdir()
    zipfile.ZipFile(io.BytesIO(zip_bytes)).extractall(study_dir)

    # Offline validation (-n / --no_portal_checks): structural + format checks
    # without a running cBioPortal instance.
    proc = subprocess.run(
        [sys.executable, VALIDATOR, "-s", str(study_dir), "-n", "-v"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = proc.stdout + proc.stderr

    # Exit codes differ across validateData.py versions (0=clean, 2 or 3 =
    # warnings-only, 1=errors), so assert on the validator's own success signal
    # instead. A clinical-only study legitimately emits WARNINGs (e.g. no DFS
    # columns, no genomic data); those are fine. What must not appear is an
    # ERROR-level finding or a "failed" verdict.
    assert "Validation of data succeeded" in output, (
        f"validateData.py did not report success on the generated study folder:\n{output}"
    )
    assert "Validation of data failed" not in output, (
        f"validateData.py reported a failure verdict:\n{output}"
    )
    error_lines = [ln for ln in output.splitlines() if ln.startswith("ERROR:")]
    assert not error_lines, (
        "validateData.py reported ERROR-level findings on the generated study "
        "folder:\n" + "\n".join(error_lines)
    )
