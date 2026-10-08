from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.services import ontology_rerun
from app.services.harmonizer import supports_ontology_mapping


def _upload(monkeypatch, mappings=(), **columns):
    """Stub the uploaded file and the study's mappings. A column is a list of
    uploaded values, or a dict ``{uploaded text: inferred text}``."""
    forms = {
        name: values if isinstance(values, dict) else {v: v for v in values}
        for name, values in columns.items()
    }
    monkeypatch.setattr(
        ontology_rerun,
        "_value_forms",
        lambda file_key, wanted: {c: forms[c] for c in wanted if c in forms},
    )
    monkeypatch.setattr(
        ontology_rerun.mappings_repo, "get_mappings", lambda *args: _async_value(list(mappings))
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("old_field", "new_field"),
    [("notes", "body_site"), ("body_site", "body_site")],
)
async def test_field_edit_or_accept_into_ontology_adds_value_mappings(
    monkeypatch, old_field, new_field
):
    inserted: list[dict] = []

    class Engine:
        def health(self):
            return SimpleNamespace(version="0.4.1")

        def map_values(self, raw_df, schema_mappings):
            assert raw_df.to_dict(orient="list") == {"biopsy_location": ["lung", "liver"]}
            assert schema_mappings == [
                {
                    "raw_column": "biopsy_location",
                    "matched_field": "body_site",
                    "curator_field": "body_site",
                }
            ]
            return [
                {
                    "field_name": "body_site",
                    "raw_value": value,
                    "ontology_term": value.title(),
                    "ontology_id": f"UBERON:{index}",
                    "confidence_score": 1.0,
                    "status": "accepted",
                }
                for index, value in enumerate(raw_df["biopsy_location"])
            ]

    async def delete_unreviewed(*args, **kwargs):
        return 0

    async def existing_keys(*args, **kwargs):
        return set()

    async def insert_rows(db, study_id, rows):
        assert study_id == "study-1"
        inserted.extend(rows)

    async def no_cache(*args, **kwargs):
        return {}

    async def cache_rows(*args, **kwargs):
        return None

    async def get_study(*args, **kwargs):
        return {"schema_version_id": 1, "ontology_snapshot_id": 1}

    _upload(monkeypatch, biopsy_location=["lung", "liver"])
    monkeypatch.setattr(ontology_rerun, "get_engine", lambda: Engine())
    monkeypatch.setattr(ontology_rerun.ontology_repo, "delete_unreviewed_ontology", delete_unreviewed)
    monkeypatch.setattr(ontology_rerun.ontology_repo, "existing_value_keys", existing_keys)
    monkeypatch.setattr(ontology_rerun.ontology_repo, "insert_ontology_mappings", insert_rows)
    monkeypatch.setattr(ontology_rerun.proposal_repo, "lookup", no_cache)
    monkeypatch.setattr(ontology_rerun.proposal_repo, "upsert_many", cache_rows)
    monkeypatch.setattr(ontology_rerun.studies_repo, "get_study", get_study)

    result = await ontology_rerun.rerun_column_ontology(
        object(),
        study_id="study-1",
        file_key="upload.csv",
        raw_column="biopsy_location",
        old_field=old_field,
        new_field=new_field,
    )

    assert result == {"added": 2, "removed": 0}
    assert {(row["field_name"], row["raw_value"]) for row in inserted} == {
        ("body_site", "lung"),
        ("body_site", "liver"),
    }


@pytest.mark.asyncio
async def test_ontology_rerun_complete_cache_hit_skips_engine_mapping(monkeypatch):
    inserted: list[dict] = []

    class Engine:
        def health(self):
            return SimpleNamespace(version="0.4.1")

        def map_values(self, *args, **kwargs):
            pytest.fail("complete ontology cache hit must skip engine mapping")

    async def cached(*args, **kwargs):
        return {
            "body site::lung": {
                "field_name": "body_site",
                "raw_value": "lung",
                "ontology_term": "Lung",
                "ontology_id": "UBERON:0002048",
                "confidence_score": 1.0,
                "status": "accepted",
            }
        }

    async def insert_rows(db, study_id, rows):
        inserted.extend(rows)

    async def get_study(*args, **kwargs):
        return {"schema_version_id": 1, "ontology_snapshot_id": 1}

    _upload(monkeypatch, site=["lung"])
    monkeypatch.setattr(ontology_rerun, "get_engine", lambda: Engine())
    monkeypatch.setattr(
        ontology_rerun.studies_repo,
        "get_study",
        get_study,
    )
    monkeypatch.setattr(ontology_rerun.proposal_repo, "lookup", cached)
    monkeypatch.setattr(
        ontology_rerun.ontology_repo, "delete_unreviewed_ontology",
        lambda *args, **kwargs: _async_value(0),
    )
    monkeypatch.setattr(
        ontology_rerun.ontology_repo, "existing_value_keys",
        lambda *args, **kwargs: _async_value(set()),
    )
    monkeypatch.setattr(ontology_rerun.ontology_repo, "insert_ontology_mappings", insert_rows)

    result = await ontology_rerun.rerun_column_ontology(
        object(), study_id="study", file_key="upload.csv",
        raw_column="site", old_field="body_site", new_field="body_site",
    )
    assert result == {"added": 1, "removed": 0}
    assert inserted[0]["ontology_id"] == "UBERON:0002048"


async def _async_value(value):
    return value


@pytest.mark.asyncio
async def test_field_edit_out_of_ontology_removes_only_repository_selected_rows(monkeypatch):
    calls: list[tuple[str, set[str], set[str]]] = []

    async def delete_unreviewed(db, study_id, fields, values):
        calls.append((study_id, fields, values))
        return 2 if fields == {"body_site"} else 0

    async def fail_insert(*args, **kwargs):
        pytest.fail("moving out of an ontology field must not insert rows")

    _upload(monkeypatch, biopsy_location=["lung", "liver"])
    monkeypatch.setattr(
        ontology_rerun,
        "get_engine",
        lambda: pytest.fail("moving out of an ontology field must not invoke the engine"),
    )
    monkeypatch.setattr(ontology_rerun.ontology_repo, "delete_unreviewed_ontology", delete_unreviewed)
    monkeypatch.setattr(ontology_rerun.ontology_repo, "insert_ontology_mappings", fail_insert)

    result = await ontology_rerun.rerun_column_ontology(
        object(),
        study_id="study-2",
        file_key="upload.csv",
        raw_column="biopsy_location",
        old_field="body_site",
        new_field="notes",
    )

    assert result == {"added": 0, "removed": 2}
    assert sorted(calls, key=lambda c: sorted(c[1])) == [
        ("study-2", {"body_site"}, {"lung", "liver"}),
        ("study-2", {"notes"}, {"lung", "liver"}),
    ]


@pytest.mark.asyncio
async def test_moving_out_keeps_the_rows_another_column_of_the_field_uses(monkeypatch):
    # Rejecting the losing duplicate column must not strip the winner's terms:
    # ontology rows are per field, and Tumor_Site still fills body_site.
    deleted: dict[str, set[str]] = {}

    async def delete_unreviewed(db, study_id, fields, values):
        (field,) = fields
        deleted[field] = set(values)
        return len(values)

    _upload(
        monkeypatch,
        mappings=[
            {"raw_column": "Tumor_Site", "matched_field": "body_site", "status": "accepted"},
            {"raw_column": "Biopsy_Site", "matched_field": "body_site", "status": "rejected"},
            {"raw_column": "Old_Site", "matched_field": "body_site", "status": "rejected"},
        ],
        Tumor_Site=["Uterus", "Ovary"],
        Biopsy_Site=["Uterus", "Lung"],
        Old_Site=["Lung"],
    )
    monkeypatch.setattr(ontology_rerun.ontology_repo, "delete_unreviewed_ontology", delete_unreviewed)

    result = await ontology_rerun.rerun_column_ontology(
        object(), study_id="s", file_key="upload.csv",
        raw_column="Biopsy_Site", old_field="body_site", new_field=None,
    )

    assert deleted == {"body_site": {"Lung"}}
    assert result == {"added": 0, "removed": 1}


@pytest.mark.asyncio
async def test_rerun_matches_rows_in_either_spelling_of_a_value(monkeypatch):
    # The pipeline keys a value's row by its inferred spelling ("1.0"); a
    # re-map by the uploaded text ("1"). Both must be cleaned up, and a value
    # that already has a row in either spelling must not get a second one.
    deleted: dict[str, set[str]] = {}
    inserted: list[dict] = []

    class Engine:
        def health(self):
            return SimpleNamespace(version="0.4.1")

        def map_values(self, raw_df, schema_mappings):
            return [
                {"field_name": "sex", "raw_value": v, "ontology_term": v, "status": "pending"}
                for v in raw_df["Sex_Code"]
            ]

    async def delete_unreviewed(db, study_id, fields, values):
        (field,) = fields
        deleted[field] = set(values)
        return 0

    async def existing_keys(db, study_id, fields, values):
        assert set(values) == {"1", "1.0", "2", "2.0"}
        return {("sex", "1.0")}  # a curator already reviewed "1" (pipeline spelling)

    async def insert_rows(db, study_id, rows):
        inserted.extend(rows)

    _upload(monkeypatch, Sex_Code={"1": "1.0", "2": "2.0"})
    monkeypatch.setattr(ontology_rerun, "get_engine", lambda: Engine())
    monkeypatch.setattr(ontology_rerun.ontology_repo, "delete_unreviewed_ontology", delete_unreviewed)
    monkeypatch.setattr(ontology_rerun.ontology_repo, "existing_value_keys", existing_keys)
    monkeypatch.setattr(ontology_rerun.ontology_repo, "insert_ontology_mappings", insert_rows)
    monkeypatch.setattr(ontology_rerun.proposal_repo, "lookup", lambda *a, **k: _async_value({}))
    monkeypatch.setattr(ontology_rerun.proposal_repo, "upsert_many", lambda *a, **k: _async_value(None))
    monkeypatch.setattr(ontology_rerun.studies_repo, "get_study", lambda *a: _async_value({}))

    result = await ontology_rerun.rerun_column_ontology(
        object(), study_id="s", file_key="upload.csv",
        raw_column="Sex_Code", old_field="race", new_field="sex",
    )

    spellings = {"1", "1.0", "2", "2.0"}
    assert deleted == {"race": spellings, "sex": spellings}
    assert [row["raw_value"] for row in inserted] == ["2"]
    assert result == {"added": 1, "removed": 0}


def test_value_forms_pairs_uploaded_and_inferred_spellings(monkeypatch, tmp_path):
    upload = tmp_path / "upload.csv"
    upload.write_text("Sex_Code,Smoker,Site,Other\n1,TRUE,Lung,x\n,FALSE,NA,y\n2,,  ,z\n01,TRUE,Lung,w\n")

    class Storage:
        def local(self, key):
            import contextlib

            return contextlib.nullcontext(upload)

    monkeypatch.setattr(ontology_rerun, "get_storage", lambda: Storage())

    forms = ontology_rerun._value_forms("upload.csv", ["Sex_Code", "Smoker", "Site", "Missing"])

    assert forms == {
        "Sex_Code": {"1": "1.0", "2": "2.0", "01": "1.0"},
        "Smoker": {"TRUE": "True", "FALSE": "False"},
        "Site": {"Lung": "Lung"},
    }


def test_dictionary_backed_fields_support_ontology_mapping():
    assert supports_ontology_mapping("sex")
    assert supports_ontology_mapping("country")
    assert supports_ontology_mapping("body_site")
    assert not supports_ontology_mapping("notes")