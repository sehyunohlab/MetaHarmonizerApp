"""The fallback ontology tables (``ONTOLOGY_MAP`` / ``_STATIC_NCIT``) use real codes.

``data/schema/ontology_code_labels.json`` records each code's names as NCI EVS
and OLS4 returned them (``python -m scripts.verify_ontology_codes --write``).
Every term must be one of its code's names, so a code typed in by hand, without
that check, fails here. Before this check, 60 entries named other concepts
(United States and United Kingdom swapped, Japan coded as Kenya, ...).
"""

from __future__ import annotations

import json

import pandas as pd

from app.services.harmonizer import ONTOLOGY_MAP, _load_field_value_dict, run_ontology_mapping
from scripts.verify_ontology_codes import SNAPSHOT, problems, used_codes


def _labels() -> dict[str, list[str]]:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))["labels"]


def test_every_code_names_its_term():
    assert problems(_labels()) == []


def test_every_code_was_checked_against_its_ontology():
    assert used_codes() <= set(_labels())


def test_a_code_naming_another_concept_is_caught(monkeypatch):
    # United States and United Kingdom swapped, as they were.
    monkeypatch.setitem(ONTOLOGY_MAP["country"], "usa", ("United States", "NCIT:C17233"))

    assert problems(_labels()) == [
        "ONTOLOGY_MAP['country']['usa']: 'United States' is not a name of NCIT:C17233 ('united kingdom')"
    ]


def test_age_groups_follow_the_lab_dictionary():
    # OmicsMLRepoData inst/extdata/cBioPortal_data_dictionary.csv, age_group:
    # allowed values Newborn|Infant|Child|Adolescent|Adult|Elderly, these codes.
    lab = {
        "Newborn": "NCIT:C16731",
        "Infant": "NCIT:C27956",
        "Child": "NCIT:C16423",
        "Adolescent": "NCIT:C27954",
        "Adult": "NCIT:C17600",
        "Elderly": "NCIT:C16268",
    }
    assert dict(ONTOLOGY_MAP["age_group"].values()) == lab
    assert _load_field_value_dict()["age_group"] == list(lab)


def test_ancestry_uses_the_lab_dictionary_categories():
    # The lab dictionary: ancestry is a child of HANCESTRO:0004.
    assert {code[: len("HANCESTRO:")] for _term, code in ONTOLOGY_MAP["ancestry"].values()} == {"HANCESTRO:"}


def test_values_map_to_the_right_concepts():
    raw = pd.DataFrame(
        {
            "nation": ["USA", "GBR", "Japan"],
            "race": ["white", "African American", "asian"],
            "age": ["children 2-11 years old", "elderly", "newborn"],
            "dx": ["CRC", "UC", "adenoma"],
        }
    )
    mappings = [
        {"raw_column": "nation", "matched_field": "country"},
        {"raw_column": "race", "matched_field": "ancestry"},
        {"raw_column": "age", "matched_field": "age_group"},
        {"raw_column": "dx", "matched_field": "disease"},
    ]

    rows = run_ontology_mapping(raw, mappings)

    assert {(r["raw_value"], r["ontology_term"], r["ontology_id"]) for r in rows} == {
        ("USA", "United States", "NCIT:C17234"),
        ("GBR", "United Kingdom", "NCIT:C17233"),
        ("Japan", "Japan", "NCIT:C16764"),
        ("white", "European Ancestry", "HANCESTRO:0005"),
        ("African American", "African American or Afro-Caribbean Ancestry", "HANCESTRO:0016"),
        ("asian", "Asian Ancestry", "HANCESTRO:0008"),
        ("children 2-11 years old", "Child", "NCIT:C16423"),
        ("elderly", "Elderly", "NCIT:C16268"),
        ("newborn", "Newborn", "NCIT:C16731"),
        ("CRC", "Colorectal Carcinoma", "NCIT:C2955"),
        ("UC", "Ulcerative Colitis", "NCIT:C2952"),
        ("adenoma", "Adenoma", "NCIT:C2855"),
    }
