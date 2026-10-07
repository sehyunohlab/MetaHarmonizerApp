"""Every export picks the same source column for a schema field.

The Harmonized CSV, the cBioPortal clinical file and the cBioPortal study
folder (attributes and PATIENT_ID / SAMPLE_ID) share one rule:

- a rejected or unmapped column never fills a schema field;
- when several columns map to one field, a mapping a curator reviewed beats
  one the engine accepted on its own, which beats a pending suggestion; then
  the higher confidence wins, then the column that comes first in the upload,
  never the order the database happens to return mappings in.

A rejected column is kept in the Harmonized CSV exactly as uploaded.
"""

from __future__ import annotations

import asyncio
import io
import random
import zipfile

import pytest

pytest.importorskip("pandas")
import pandas as pd  # noqa: E402

from app.services import exporter  # noqa: E402

ID_CANDIDATES = {
    "PATIENT_ID": ["subject_id", "patient_id", "participant_id", "case_id"],
    "SAMPLE_ID": ["sample_id", "run_id", "sampleid", "accession"],
}


def _m(raw, matched, status="accepted", *, curator=None, confidence=0.9, reviewed=False):
    return {
        "raw_column": raw,
        "matched_field": matched,
        "curator_field": curator,
        "status": status,
        "confidence_score": confidence,
        # Set by every curator action; empty on rows the engine wrote itself.
        "reviewed_at": "2026-10-07T12:00:00+00:00" if reviewed else None,
    }


def _field(target: str) -> str:
    return target.upper().replace(" ", "_")


def csv_sources(df: pd.DataFrame, mappings: list[dict]) -> dict[str, str]:
    """Field → source column in the Harmonized CSV."""
    table = exporter.harmonize_table(df, df, mappings, {})
    return {
        _field(p.target): p.source for p in table.plan if p.action in ("renamed", "matched")
    }


def cbio_sources(df: pd.DataFrame, mappings: list[dict]) -> dict[str, str]:
    """Field → source column in the cBioPortal files (attributes and IDs)."""
    sources = {s["target"]: s["raw"] for s in exporter._clinical_column_specs(mappings, df)}
    for id_field, candidates in ID_CANDIDATES.items():
        sources[id_field] = exporter._id_raw_source(mappings, df, id_field, candidates)
    return sources


@pytest.mark.parametrize(
    "rejected",
    [
        _m("Specimen_Label", "sample_id", "rejected", confidence=0.97),
        # Edited to sample_id, then rejected in a batch: the row keeps its curator_field.
        _m("Specimen_Label", "specimen_label", "rejected", curator="sample_id", confidence=0.97),
    ],
    ids=["rejected-suggestion", "rejected-after-edit"],
)
def test_a_rejected_mapping_never_supplies_the_cbioportal_sample_id(rejected):
    df = pd.DataFrame(
        {
            "Patient": ["P1", "P2"],
            "Specimen_Label": ["tube 1", "tube 2"],
            "Sample_Name": ["S1", "S2"],
        }
    )
    mappings = [  # as get_mappings returns them: highest confidence first
        rejected,
        _m("Patient", "patient_id", confidence=0.95),
        _m("Sample_Name", "sample_name", curator="sample_id", confidence=0.41),
    ]

    assert csv_sources(df, mappings)["SAMPLE_ID"] == "Sample_Name"
    assert cbio_sources(df, mappings)["SAMPLE_ID"] == "Sample_Name"


def test_a_rejected_only_id_mapping_falls_back_to_the_id_heuristic():
    df = pd.DataFrame({"Barcode": ["b1", "b1"], "run_id": ["r1", "r2"], "Patient": ["P1", "P2"]})
    mappings = [
        _m("Barcode", "sample_id", "rejected", confidence=0.99),
        _m("Patient", "patient_id"),
    ]

    assert "SAMPLE_ID" not in csv_sources(df, mappings)
    assert cbio_sources(df, mappings)["SAMPLE_ID"] == "run_id"


def test_the_study_folder_takes_sample_ids_from_the_accepted_column(monkeypatch):
    df = pd.DataFrame(
        {
            "Patient": ["P1", "P2"],
            "Specimen_Label": ["tube 1", "tube 2"],
            "Sample_Name": ["S1", "S2"],
        }
    )
    mappings = [
        _m("Specimen_Label", "sample_id", "rejected", confidence=0.97),
        _m("Patient", "patient_id", confidence=0.95),
        _m("Sample_Name", "sample_name", curator="sample_id", confidence=0.41),
    ]

    async def _mappings(_db, _sid):
        return mappings

    async def _study(_db, _sid):
        return {"name": "Selection"}

    async def _no_terms(_db, _sid):
        return []

    monkeypatch.setattr(exporter.mappings_repo, "get_mappings", _mappings)
    monkeypatch.setattr(exporter.studies_repo, "get_study", _study)
    monkeypatch.setattr(exporter.ontology_repo, "get_ontology_mappings", _no_terms)

    zip_bytes = asyncio.run(exporter.export_cbioportal_study(None, "s", df))
    sample_file = zipfile.ZipFile(io.BytesIO(zip_bytes)).read("data_clinical_sample.txt").decode()
    rows = [line.split("\t") for line in sample_file.splitlines() if not line.startswith("#")]
    header, data = rows[0], rows[1:]
    assert [row[header.index("SAMPLE_ID")] for row in data] == ["S1", "S2"]


def test_a_curator_accepted_column_beats_an_unreviewed_suggestion_in_every_export():
    df = pd.DataFrame({"Gender": ["F", "M"], "Sex_Guess": ["female", "female"]})
    mappings = [
        _m("Sex_Guess", "sex", "pending", confidence=0.99),
        _m("Gender", "sex", confidence=0.71),
    ]

    assert csv_sources(df, mappings)["SEX"] == "Gender"
    assert cbio_sources(df, mappings)["SEX"] == "Gender"


def test_a_mapping_you_reviewed_beats_one_the_engine_accepted_on_its_own():
    df = pd.DataFrame({"Tumor_Site": ["Uterus"], "Primary_Site": ["Endometrium"]})
    mappings = [  # highest confidence first, as the database returns them
        _m("Tumor_Site", "body_site", confidence=0.97),  # auto-accepted by the engine
        _m("Primary_Site", "body_site", confidence=0.6, reviewed=True),  # accepted by the curator
    ]

    assert csv_sources(df, mappings)["BODY_SITE"] == "Primary_Site"
    assert cbio_sources(df, mappings)["BODY_SITE"] == "Primary_Site"


@pytest.mark.parametrize("database_order", ["upload-order", "reversed"])
def test_a_tie_goes_to_the_first_column_in_the_upload(database_order):
    df = pd.DataFrame({"Gender": ["F"], "Sex_Reported": ["Female"]})
    mappings = [_m("Gender", "sex", confidence=0.95), _m("Sex_Reported", "sex", confidence=0.95)]
    if database_order == "reversed":
        mappings.reverse()  # the database returns rows with equal confidence in no fixed order

    assert csv_sources(df, mappings)["SEX"] == "Gender"
    assert cbio_sources(df, mappings)["SEX"] == "Gender"


def test_cbioportal_attributes_follow_the_upload_column_order():
    df = pd.DataFrame({"age": ["1"], "sex": ["F"], "site": ["lung"]})
    mappings = [  # highest confidence first, as the database returns them
        _m("site", "body_site", confidence=0.99),
        _m("sex", "sex", confidence=0.9),
        _m("age", "age", confidence=0.8),
    ]

    specs = exporter._clinical_column_specs(mappings, df)

    assert [s["raw"] for s in specs] == ["age", "sex", "site"]


def test_a_rejected_column_is_kept_exactly_as_uploaded():
    # 'sex' was rejected, but accepted terms for the field 'sex' are still on
    # record (for example, the clean-up after the rejection failed).
    df = pd.DataFrame({"sex": ["F", "M", "=1+1"]})

    table = exporter.harmonize_table(
        df, df, [_m("sex", "sex", "rejected")], {"sex": {"F": "Female", "M": "Male"}}
    )

    assert [p.action for p in table.plan] == ["kept"]
    assert list(table.frame["sex"]) == ["F", "M", "'=1+1"]  # only the spreadsheet escape
    assert not table.rewritten["sex"].any()


def _random_review(rng: random.Random) -> tuple[pd.DataFrame, list[dict]]:
    """A review state the API can produce, in the order get_mappings returns it."""
    columns = rng.sample([f"c{i}" for i in range(8)], k=rng.randint(2, 7))
    targets = ["sex", "age", "body_site", "patient_id", "sample_id"]
    mappings = []
    for column in columns:
        status = rng.choice(["accepted", "accepted", "pending", "pending", "rejected", "unmapped"])
        curator = None
        if status == "accepted" and rng.random() < 0.4:
            curator = rng.choice(targets)  # edited by the curator
        if status == "rejected" and rng.random() < 0.3:
            curator = rng.choice(targets)  # batch reject keeps an earlier edit
        # Edits are curator decisions; other accepts and rejects may be the engine's own.
        reviewed = curator is not None or (status in ("accepted", "rejected") and rng.random() < 0.5)
        confidence = rng.choice([0.5, 0.8, 0.95, 0.95, 1.0, None])
        mappings.append(
            _m(column, rng.choice(targets), status, curator=curator, confidence=confidence, reviewed=reviewed)
        )
    # Highest confidence first, NULLS LAST; rows with equal confidence in no fixed order.
    rng.shuffle(mappings)
    mappings.sort(key=lambda m: -1.0 if m["confidence_score"] is None else -m["confidence_score"] - 1)
    # Repeated values, so the ID heuristic never mistakes a column for an ID.
    return pd.DataFrame({c: ["x", "x"] for c in columns}), mappings


def test_cbioportal_and_the_harmonized_csv_choose_the_same_columns():
    rng = random.Random(20261007)
    disagreements = []
    for case in range(400):
        df, mappings = _random_review(rng)
        csv, cbio = csv_sources(df, mappings), cbio_sources(df, mappings)
        for field in sorted(set(csv) | set(cbio)):
            expected = csv.get(field)
            if expected is None and field in ID_CANDIDATES:
                # No accepted or pending mapping: cBioPortal guesses the ID column.
                expected = exporter._find_id_column(df, ID_CANDIDATES[field])
            if cbio.get(field) != expected:
                disagreements.append((case, field, expected, cbio.get(field)))

    assert not disagreements, (
        f"cBioPortal and the Harmonized CSV disagree in {len({d[0] for d in disagreements})} "
        f"of 400 review states, e.g. (case, field, CSV, cBioPortal): {disagreements[:4]}"
    )


def test_the_choice_does_not_depend_on_the_order_mappings_are_returned_in():
    rng = random.Random(7)
    unstable = []
    for case in range(400):
        df, mappings = _random_review(rng)
        reordered = sorted(
            reversed(mappings),
            key=lambda m: -1.0 if m["confidence_score"] is None else -m["confidence_score"] - 1,
        )  # same confidence order, ties reversed
        if (csv_sources(df, mappings), cbio_sources(df, mappings)) != (
            csv_sources(df, reordered),
            cbio_sources(df, reordered),
        ):
            unstable.append(case)

    assert not unstable, (
        f"{len(unstable)} of 400 review states export a different column when tied "
        f"mappings come back in another order (cases {unstable[:8]})"
    )
