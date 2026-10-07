"""Unit tests for the cBioPortal study-folder export (G9 / U21).

Covers the patient/sample clinical split required by the curation checklist
("the clinical file should be split to patient and sample level attribute
files"), the 5-row cBioPortal header, survival-status prefixing, and missing-
value handling. Needs pandas (the exporter imports it), so it skips in the
lightweight test venv.
"""

from __future__ import annotations

import asyncio
import io
import zipfile

import pytest

pytest.importorskip("pandas")
import pandas as pd  # noqa: E402

from app.services import exporter  # noqa: E402


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_is_patient_level_classification():
    assert exporter._is_patient_level("SEX")
    assert exporter._is_patient_level("OS_STATUS")
    assert exporter._is_patient_level("OS_MONTHS")
    assert exporter._is_patient_level("RFS_STATUS")  # custom survival prefix
    assert exporter._is_patient_level("AGE")
    # Sample-level attributes
    assert not exporter._is_patient_level("SAMPLE_TYPE")
    assert not exporter._is_patient_level("CANCER_TYPE")
    assert not exporter._is_patient_level("ONCOTREE_CODE")


def test_infer_dtype():
    assert exporter._infer_dtype(pd.Series(["1", "2", "3"])) == "NUMBER"
    assert exporter._infer_dtype(pd.Series(["yes", "no", "yes"])) == "BOOLEAN"
    assert exporter._infer_dtype(pd.Series(["lung", "liver"])) == "STRING"


def test_clinical_column_specs_excludes_ids_and_banned_and_dedupes():
    raw_df = pd.DataFrame(
        {
            "subject": ["p1", "p2"],
            "samp": ["s1", "s2"],
            "gender": ["male", "female"],
            "tissue": ["lung", "liver"],
            "tissue2": ["lung", "liver"],
            "mut": ["1", "2"],
        }
    )
    mappings = [
        {"raw_column": "subject", "matched_field": "PATIENT_ID", "status": "accepted"},
        {"raw_column": "samp", "matched_field": "SAMPLE_ID", "status": "accepted"},
        {"raw_column": "gender", "matched_field": "SEX", "status": "accepted"},
        {"raw_column": "tissue", "matched_field": "BODY_SITE", "status": "accepted"},
        # Duplicate target BODY_SITE — must be dropped.
        {"raw_column": "tissue2", "matched_field": "BODY_SITE", "status": "accepted"},
        # Banned auto-populated attribute.
        {"raw_column": "mut", "matched_field": "MUTATION_COUNT", "status": "accepted"},
        # Rejected mapping — ignored.
        {"raw_column": "tissue", "matched_field": "WHATEVER", "status": "rejected"},
    ]
    specs = exporter._clinical_column_specs(mappings, raw_df)
    targets = [s["target"] for s in specs]
    assert "PATIENT_ID" not in targets
    assert "SAMPLE_ID" not in targets
    assert "MUTATION_COUNT" not in targets
    assert targets.count("BODY_SITE") == 1
    assert "SEX" in targets


def test_write_clinical_tsv_header_and_values():
    cols = [
        exporter._id_spec("PATIENT_ID", "subject", "Patient Identifier", "Unique patient identifier"),
        exporter._id_spec("SAMPLE_ID", "samp", "Sample Identifier", "Unique sample identifier"),
        {"raw": "os_s", "target": "OS_STATUS", "display": "Os Status", "description": "Os status", "dtype": "STRING", "priority": 10},
        {"raw": "os_m", "target": "OS_MONTHS", "display": "Os Months", "description": "Os months", "dtype": "NUMBER", "priority": 10},
    ]
    raw_df = pd.DataFrame(
        {
            "subject": ["p 1", "p2"],  # space -> sanitized to underscore
            "samp": ["s1", "s2"],
            "os_s": ["LIVING", "DECEASED"],
            "os_m": ["10.5", None],
        }
    )
    tsv = exporter._write_clinical_tsv(cols, raw_df)
    lines = tsv.rstrip("\n").split("\n")
    # 5 header rows + 2 data rows
    assert len(lines) == 7
    assert lines[0].startswith("#")  # display names
    assert lines[4].split("\t") == ["PATIENT_ID", "SAMPLE_ID", "OS_STATUS", "OS_MONTHS"]
    row1 = lines[5].split("\t")
    assert row1[0] == "p_1"  # sanitized ID
    assert row1[2] == "0:LIVING"  # survival prefixed (OS_MONTHS exists)
    row2 = lines[6].split("\t")
    assert row2[2] == "1:DECEASED"
    assert row2[3] == ""  # NaN -> empty, not "nan"


def _boolean_spec(raw: str, target: str) -> dict:
    return {"raw": raw, "target": target, "display": target.title(),
            "description": target.lower(), "dtype": "BOOLEAN", "priority": 1}


def test_boolean_attributes_are_written_as_true_or_false():
    # cBioPortal's validateData.py accepts only TRUE / FALSE in a BOOLEAN column.
    raw_df = pd.DataFrame({"samp": list("abcde"), "ffpe": ["Yes", "no", None, "TRUE", "false"]})
    cols = [
        exporter._id_spec("SAMPLE_ID", "samp", "Sample Identifier", "Unique sample identifier"),
        _boolean_spec("ffpe", "FFPE"),
    ]

    lines = exporter._write_clinical_tsv(cols, raw_df).splitlines()

    assert lines[2] == "#STRING\tBOOLEAN"
    assert [line.split("\t")[1] for line in lines[5:]] == ["TRUE", "FALSE", "", "TRUE", "FALSE"]


def test_a_boolean_column_rewritten_to_other_terms_is_declared_string():
    raw_df = pd.DataFrame({"samp": ["a", "b"], "pregnant": ["yes", "no"]})
    cols = [
        exporter._id_spec("SAMPLE_ID", "samp", "Sample Identifier", "Unique sample identifier"),
        _boolean_spec("pregnant", "PREGNANT"),
    ]
    rewrites = {"PREGNANT": {"yes": "Pregnant", "no": "Not pregnant"}}

    lines = exporter._write_clinical_tsv(cols, raw_df, rewrites).splitlines()

    assert lines[2] == "#STRING\tSTRING"
    assert [line.split("\t")[1] for line in lines[5:]] == ["Pregnant", "Not pregnant"]


def test_banned_checklist_columns_stripped():
    raw_df = pd.DataFrame(
        {
            "subject": ["p1"],
            "religion": ["x"],
            "msi": ["y"],
            "gender": ["male"],
        }
    )
    mappings = [
        {"raw_column": "subject", "matched_field": "PATIENT_ID", "status": "accepted"},
        # Checklist-banned by target id.
        {"raw_column": "religion", "matched_field": "Religion", "status": "accepted"},
        {"raw_column": "msi", "matched_field": "MSI comments", "status": "accepted"},
        {"raw_column": "gender", "matched_field": "SEX", "status": "accepted"},
    ]
    targets = [s["target"] for s in exporter._clinical_column_specs(mappings, raw_df)]
    assert "RELIGION" not in targets
    assert "MSI_COMMENTS" not in targets
    assert "SEX" in targets


def test_banned_by_raw_column_name():
    # Banned even if the mapper picked a non-banned target, matched on raw name.
    raw_df = pd.DataFrame({"Part-A consent": ["yes"], "gender": ["male"]})
    mappings = [
        {"raw_column": "Part-A consent", "matched_field": "CONSENT", "status": "accepted"},
        {"raw_column": "gender", "matched_field": "SEX", "status": "accepted"},
    ]
    targets = [s["target"] for s in exporter._clinical_column_specs(mappings, raw_df)]
    assert "CONSENT" not in targets
    assert "SEX" in targets


def test_smart_quotes_stripped_and_lf_endings():
    cols = [
        exporter._id_spec("PATIENT_ID", "subject", "Patient Identifier", "Unique patient identifier"),
        exporter._id_spec("SAMPLE_ID", "samp", "Sample Identifier", "Unique sample identifier"),
        {"raw": "note", "target": "NOTE", "display": "Note", "description": "Note", "dtype": "STRING", "priority": 1},
    ]
    raw_df = pd.DataFrame(
        {
            "subject": ["p1"],
            "samp": ["s1"],
            "note": ["he said \u201chello\u201d and \u2018bye\u2019"],
        }
    )
    tsv = exporter._write_clinical_tsv(cols, raw_df)
    # LF only — no CR.
    assert "\r" not in tsv
    data_row = tsv.rstrip("\n").split("\n")[5]
    assert "\u201c" not in data_row and "\u201d" not in data_row
    assert '"hello"' in data_row
    assert "'bye'" in data_row


# ---------------------------------------------------------------------------
# Full study-folder export (patient/sample split)
# ---------------------------------------------------------------------------


def _patch_repos(monkeypatch, mappings, study, ontology=None):
    async def _get_mappings(db, study_id):
        return mappings

    async def _get_study(db, study_id):
        return study

    async def _get_ontology(db, study_id):
        return ontology or []

    monkeypatch.setattr(exporter.mappings_repo, "get_mappings", _get_mappings)
    monkeypatch.setattr(exporter.studies_repo, "get_study", _get_study)
    monkeypatch.setattr(exporter.ontology_repo, "get_ontology_mappings", _get_ontology)


def test_study_folder_splits_patient_and_sample(monkeypatch):
    # Two samples for patient p1, one for p2 -> 2 unique patients.
    raw_df = pd.DataFrame(
        {
            "subject": ["p1", "p1", "p2"],
            "samp": ["s1", "s2", "s3"],
            "gender": ["male", "male", "female"],
            "tissue": ["lung", "lung", "liver"],
        }
    )
    mappings = [
        {"raw_column": "subject", "matched_field": "PATIENT_ID", "status": "accepted"},
        {"raw_column": "samp", "matched_field": "SAMPLE_ID", "status": "accepted"},
        {"raw_column": "gender", "matched_field": "SEX", "status": "accepted"},
        {"raw_column": "tissue", "matched_field": "SAMPLE_TYPE", "status": "accepted"},
    ]
    _patch_repos(monkeypatch, mappings, {"name": "My Study"})

    zip_bytes = asyncio.run(exporter.export_cbioportal_study(None, "study1", raw_df))
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = set(zf.namelist())
    assert {
        "meta_study.txt",
        "meta_clinical_patient.txt",
        "data_clinical_patient.txt",
        "meta_clinical_sample.txt",
        "data_clinical_sample.txt",
    } <= names

    patient = zf.read("data_clinical_patient.txt").decode().rstrip("\n").split("\n")
    sample = zf.read("data_clinical_sample.txt").decode().rstrip("\n").split("\n")

    # Patient file: PATIENT_ID + SEX (patient-level); one row per unique patient.
    assert patient[4].split("\t") == ["PATIENT_ID", "SEX"]
    assert len(patient) == 5 + 2  # 2 unique patients

    # Sample file: PATIENT_ID + SAMPLE_ID + SAMPLE_TYPE; one row per sample.
    assert sample[4].split("\t") == ["PATIENT_ID", "SAMPLE_ID", "SAMPLE_TYPE"]
    assert len(sample) == 5 + 3  # 3 samples

    # SEX is patient-level only, not duplicated into the sample file.
    assert "SEX" not in sample[4].split("\t")


def test_study_folder_meta_files_reference_data(monkeypatch):
    raw_df = pd.DataFrame({"subject": ["p1"], "samp": ["s1"], "gender": ["male"]})
    mappings = [
        {"raw_column": "subject", "matched_field": "PATIENT_ID", "status": "accepted"},
        {"raw_column": "samp", "matched_field": "SAMPLE_ID", "status": "accepted"},
        {"raw_column": "gender", "matched_field": "SEX", "status": "accepted"},
    ]
    _patch_repos(monkeypatch, mappings, {"name": "Study X"})

    zip_bytes = asyncio.run(exporter.export_cbioportal_study(None, "study1", raw_df))
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))

    meta_patient = zf.read("meta_clinical_patient.txt").decode()
    assert "datatype: PATIENT_ATTRIBUTES" in meta_patient
    assert "data_filename: data_clinical_patient.txt" in meta_patient

    meta_sample = zf.read("meta_clinical_sample.txt").decode()
    assert "datatype: SAMPLE_ATTRIBUTES" in meta_sample
    assert "data_filename: data_clinical_sample.txt" in meta_sample

    meta_study = zf.read("meta_study.txt").decode()
    assert "cancer_study_identifier:" in meta_study


def test_study_folder_includes_case_list_and_license(monkeypatch):
    raw_df = pd.DataFrame(
        {
            "subject": ["p1", "p1", "p2"],
            "samp": ["s1", "s2", "s3"],
            "gender": ["male", "male", "female"],
        }
    )
    mappings = [
        {"raw_column": "subject", "matched_field": "PATIENT_ID", "status": "accepted"},
        {"raw_column": "samp", "matched_field": "SAMPLE_ID", "status": "accepted"},
        {"raw_column": "gender", "matched_field": "SEX", "status": "accepted"},
    ]
    _patch_repos(monkeypatch, mappings, {"name": "Study Y"})

    zip_bytes = asyncio.run(exporter.export_cbioportal_study(None, "study1", raw_df))
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = set(zf.namelist())
    assert "case_lists/cases_all.txt" in names
    assert "LICENSE" in names

    case_list = zf.read("case_lists/cases_all.txt").decode()
    assert "stable_id: study_y_all" in case_list
    assert "case_list_ids: s1\ts2\ts3" in case_list
    # No add_global_case_list (would collide with the explicit list).
    assert "add_global_case_list" not in zf.read("meta_study.txt").decode()


def test_study_folder_applies_value_rewrites(monkeypatch):
    raw_df = pd.DataFrame(
        {
            "subject": ["p1", "p2"],
            "samp": ["s1", "s2"],
            "gender": ["male", "female"],
        }
    )
    mappings = [
        {"raw_column": "subject", "matched_field": "PATIENT_ID", "status": "accepted"},
        {"raw_column": "samp", "matched_field": "SAMPLE_ID", "status": "accepted"},
        {"raw_column": "gender", "matched_field": "SEX", "status": "accepted"},
    ]
    # Curator confirmed male->Male, female->Female for the SEX field.
    ontology = [
        {"field_name": "SEX", "raw_value": "male", "ontology_term": "Male",
         "ontology_id": None, "status": "accepted", "curator_term": None, "confidence_score": 1.0},
        {"field_name": "SEX", "raw_value": "female", "ontology_term": "Female",
         "ontology_id": None, "status": "accepted", "curator_term": None, "confidence_score": 1.0},
    ]
    _patch_repos(monkeypatch, mappings, {"name": "Study Z"}, ontology)

    zip_bytes = asyncio.run(exporter.export_cbioportal_study(None, "study1", raw_df))
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    patient = zf.read("data_clinical_patient.txt").decode().rstrip("\n").split("\n")
    # SEX is patient-level; rows 5 (header ids) then data — values rewritten.
    assert patient[4].split("\t") == ["PATIENT_ID", "SEX"]
    sexes = {patient[5].split("\t")[1], patient[6].split("\t")[1]}
    assert sexes == {"Male", "Female"}


# ---------------------------------------------------------------------------
# Labeled dataset export (G9 data loop)
# ---------------------------------------------------------------------------


def test_labeled_dataset_csv_has_accepted_rows(monkeypatch):
    raw_df = pd.DataFrame({"gender": ["male", "female"], "tissue": ["lung", "liver"]})
    mappings = [
        {"raw_column": "gender", "matched_field": "SEX", "curator_field": None,
         "status": "accepted", "confidence_score": 0.99, "stage": "stage1", "method": "std_exact"},
        # Rejected — must NOT appear in the labeled set.
        {"raw_column": "tissue", "matched_field": "BODY_SITE", "curator_field": None,
         "status": "rejected", "confidence_score": 0.4, "stage": "stage3", "method": "semantic"},
    ]
    ontology = [
        {"field_name": "BODY_SITE", "raw_value": "stool", "ontology_term": "feces",
         "ontology_id": "UBERON:0001988", "status": "accepted", "curator_term": None,
         "confidence_score": 1.0},
    ]
    _patch_repos(monkeypatch, mappings, {"name": "S", "schema_version_id": 2}, ontology)

    csv_text = asyncio.run(exporter.export_labeled_dataset(None, "study1", raw_df, "csv"))
    lines = csv_text.rstrip("\n").split("\n")
    header = lines[0].split(",")
    assert header == exporter.LABELED_FIELDNAMES
    # 1 accepted schema mapping + 1 accepted ontology mapping = 2 data rows.
    assert len(lines) == 1 + 2
    body = csv_text
    assert "schema_mapping,gender" in body
    assert "SEX" in body
    assert "ontology_mapping,BODY_SITE" in body
    assert "UBERON:0001988" in body
    assert "feces" in body
    # schema_version stamped.
    assert ",2," in body
    # rejected mapping excluded.
    assert "rejected" not in body


def test_labeled_dataset_jsonl(monkeypatch):
    import json

    raw_df = pd.DataFrame({"gender": ["male", "female"]})
    mappings = [
        {"raw_column": "gender", "matched_field": "SEX", "curator_field": None,
         "status": "accepted", "confidence_score": 0.99, "stage": "stage1", "method": "std_exact"},
    ]
    _patch_repos(monkeypatch, mappings, {"name": "S", "schema_version_id": 1})

    jsonl = asyncio.run(exporter.export_labeled_dataset(None, "study1", raw_df, "jsonl"))
    records = [json.loads(ln) for ln in jsonl.rstrip("\n").split("\n")]
    assert len(records) == 1
    assert records[0]["record_type"] == "schema_mapping"
    assert records[0]["accepted_target"] == "SEX"
    assert records[0]["raw_sample_values"] == "male;female"


# ---------------------------------------------------------------------------
# LinkML gate via the exporter (parses the generated TSV)
# ---------------------------------------------------------------------------


def test_linkml_check_passes_on_clean_export(monkeypatch):
    raw_df = pd.DataFrame(
        {
            "subject": ["p1", "p2"],
            "samp": ["s1", "s2"],
            "gender": ["male", "female"],
        }
    )
    mappings = [
        {"raw_column": "subject", "matched_field": "PATIENT_ID", "status": "accepted"},
        {"raw_column": "samp", "matched_field": "SAMPLE_ID", "status": "accepted"},
        {"raw_column": "gender", "matched_field": "SEX", "status": "accepted"},
    ]
    # Curator resolved the SEX values to the controlled vocabulary.
    ontology = [
        {"field_name": "SEX", "raw_value": "male", "ontology_term": "Male",
         "ontology_id": None, "status": "accepted", "curator_term": None, "confidence_score": 1.0},
        {"field_name": "SEX", "raw_value": "female", "ontology_term": "Female",
         "ontology_id": None, "status": "accepted", "curator_term": None, "confidence_score": 1.0},
    ]
    _patch_repos(monkeypatch, mappings, {"name": "S"}, ontology)

    result = asyncio.run(exporter.linkml_check(None, "study1", raw_df))
    assert result["ok"] is True
    assert result["violations"] == []


def test_linkml_check_flags_unresolved_values(monkeypatch):
    raw_df = pd.DataFrame(
        {
            "subject": ["p1", "p2"],
            "samp": ["s1", "s2"],
            "gender": ["male", "female"],  # not resolved to Male/Female
        }
    )
    mappings = [
        {"raw_column": "subject", "matched_field": "PATIENT_ID", "status": "accepted"},
        {"raw_column": "samp", "matched_field": "SAMPLE_ID", "status": "accepted"},
        {"raw_column": "gender", "matched_field": "SEX", "status": "accepted"},
    ]
    _patch_repos(monkeypatch, mappings, {"name": "S"})

    result = asyncio.run(exporter.linkml_check(None, "study1", raw_df))
    assert result["ok"] is False
    bad = {v["value"] for v in result["violations"]}
    assert bad == {"male", "female"}

