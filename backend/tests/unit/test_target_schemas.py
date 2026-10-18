"""Target schemas: the default is the lab's curated cBioPortal vocabulary.

``data/schema/registry/omicsmlrepo_cbio`` is generated from OmicsMLRepoData's
``inst/extdata/cBioPortal_data_dictionary.csv`` by
``scripts/refresh_lab_dictionary.py``; these tests pin the committed files to
that generation, so they cannot drift from the lab's dictionary by hand.
"""

from __future__ import annotations

import csv
import io
import json

from app.engine_adapter import _schema_registry
from scripts import refresh_lab_dictionary as refresh

REG = refresh.REGISTRY
PREFIX = refresh.PREFIX


def _dictionary() -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO((REG / f"{PREFIX}_schema.csv").read_text(encoding="utf-8"))))


def test_the_lab_vocabulary_is_the_default_and_listed_first(monkeypatch):
    monkeypatch.delenv("ENGINE_TARGET_SCHEMA", raising=False)

    assert _schema_registry.default_key() == "omicsmlprepo_cbio"
    first, *rest = _schema_registry.available_schemas()
    assert first == {"key": "omicsmlprepo_cbio", "label": "cBioPortal curated (lab vocabulary)", "fields": 44}
    assert [s["key"] for s in rest] == ["cbioportal", "gdc", "cmd"]


def test_an_operator_default_is_listed_first(monkeypatch):
    monkeypatch.setenv("ENGINE_TARGET_SCHEMA", "gdc")

    assert _schema_registry.default_key() == "gdc"
    assert [s["key"] for s in _schema_registry.available_schemas()] == ["gdc", "omicsmlprepo_cbio", "cbioportal", "cmd"]


def test_the_registry_is_generated_from_the_lab_dictionary():
    rows = _dictionary()
    meta = json.loads((REG / f"{PREFIX}_dictionary.meta.json").read_text(encoding="utf-8"))
    # The lab's file byte for byte (a Windows checkout may have CRLF line ends).
    data = (REG / f"{PREFIX}_schema.csv").read_bytes().replace(b"\r\n", b"\n")
    assert refresh._blob_sha(data) == meta["blob"]
    assert meta["fields"] == len(rows) == 44

    assert (REG / f"{PREFIX}_target_attrs.csv").read_text(encoding="utf-8") == refresh.target_attrs(rows)
    values = json.loads((REG / f"{PREFIX}_target_attrs_allowed_values.json").read_text(encoding="utf-8"))
    assert values == refresh.allowed_values(rows, refresh._engine_values())


def test_allowed_values_are_the_lab_lists_and_never_patterns():
    rows = _dictionary()
    values = refresh.allowed_values(rows, {"sex": ["male", "Female"], "cancer_status": ["Tumor Free"]})

    assert values["age_group"] == ["Newborn", "Infant", "Child", "Adolescent", "Adult", "Elderly"]
    assert values["sex"] == ["Female", "Male"]  # the dictionary's spelling wins a repeat
    assert "age_at_diagnosis" not in values and "tumor_staging_tnm" not in values  # [0-9]+, T[X1-4]...
    assert "cancer_status" not in values  # not a field of the dictionary


def test_every_alias_names_a_field_of_the_dictionary():
    fields = {row["col.name"] for row in _dictionary()}
    alias_path = next(REG.glob(f"{PREFIX}_target_attrs_alias*.csv"))
    with open(alias_path, encoding="utf-8") as handle:
        assert {row["field_name"] for row in csv.DictReader(handle)} <= fields


def test_dictionary_lists_use_the_registry_delimiter():
    # The lab's schema registry delimits every list cell with "|"; the engine's
    # corpus builder splits dynamic.enum roots on it.
    by_field = {row["col.name"]: row for row in _dictionary()}
    assert by_field["target_condition"]["dynamic.enum"] == "NCIT:C7057|EFO_0000408"
    assert by_field["sex"]["allowedvalues"] == "Female|Male"
    for row in by_field.values():
        for column in ("static.enum", "dynamic.enum", "corpus.type"):
            assert ";" not in row[column], (row["col.name"], column)
    # A regex keeps its "|" alternation and is left as the lab wrote it.
    assert by_field["tumor_staging_tnm"]["allowedvalues"] == "T[X1-4]N[X0-3]M[X0-1]|pTis|Tis"
    assert refresh.standardize_lists([{"allowedvalues": "a;b", "static.enum": "NA"}]) == [
        {"allowedvalues": "a|b", "static.enum": "NA"}
    ]


def test_field_separators_follow_the_lab_dictionaries_and_release():
    # The lab's cBioPortal dictionary: "<;>" for most multi-valued fields, ";"
    # for three; its published release joins ancestry values with ";" too.
    lab = _schema_registry.field_separators("omicsmlprepo_cbio")
    assert {f: lab[f] for f in ("body_site", "disease_type", "treatment_name")} == dict.fromkeys(
        ("body_site", "disease_type", "treatment_name"), "<;>"
    )
    assert {f: lab[f] for f in ("target_condition", "study_design", "smoker", "ancestry", "ancestry_details")} == (
        dict.fromkeys(("target_condition", "study_design", "smoker", "ancestry", "ancestry_details"), ";")
    )
    assert "sex" not in lab  # single-valued: the default separator applies

    # curatedMetagenomicData separates most fields with ";", key:value fields with "<;>".
    cmd = _schema_registry.field_separators("cmd")
    assert (cmd["disease"], cmd["curator"], cmd["feces_phenotype"]) == (";", ";", "<;>")

    # cBioPortal's attribute IDs and GDC name no separator.
    assert _schema_registry.field_separators("cbioportal") == {}
    assert _schema_registry.field_separators("gdc") == {}
    assert _schema_registry.field_separators(None) == {}
