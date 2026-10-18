"""Harmonized table provenance + export preview (pure, no database)."""

from __future__ import annotations

import io

import pandas as pd
import pytest

from app.services import export_preview
from app.services.export_preview import UnknownColumnError, build_preview
from app.services.exporter import harmonize_table


def _frames(csv_text: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(original cell text, type-inferred frame) — as the export endpoints read a file."""
    text = pd.read_csv(io.StringIO(csv_text), dtype=str, keep_default_na=False)
    typed = pd.read_csv(io.StringIO(csv_text), low_memory=False)
    return text, typed


def _m(raw, matched, status="accepted", curator=None, confidence=0.9):
    return {
        "raw_column": raw,
        "matched_field": matched,
        "curator_field": curator,
        "status": status,
        "confidence_score": confidence,
    }


SAMPLE = (
    "patient,age,sex,bmi,note\n"
    "P1,51,F,22.50,=SUM(A1)\n"
    "P2,,M,NA,-5\n"
    "P3,7,F,30,plain\n"
)


def test_export_keeps_original_cell_text():
    text, typed = _frames(SAMPLE)
    table = harmonize_table(
        text, typed, [_m("patient", "patient_id"), _m("age", "age_years"), _m("bmi", "bmi")], {}
    )

    out = pd.read_csv(io.StringIO(table.to_csv()), dtype=str, keep_default_na=False)
    # Integers in a column with gaps are not reformatted as floats, "NA" stays
    # "NA", and trailing zeros survive — no pandas round-trip artifacts.
    assert list(out["age_years"]) == ["51", "", "7"]
    assert list(out["bmi"]) == ["22.50", "NA", "30"]
    assert list(out["patient_id"]) == ["P1", "P2", "P3"]


def test_rewrites_match_inferred_values_but_keep_unmatched_text():
    text, typed = _frames("id,code\na,1\nb,2\nc,\nd,3\n")
    rewrites = {"sex": {"1.0": "Male", "2.0": "Female"}}  # raw_value as the pipeline records it

    table = harmonize_table(text, typed, [_m("code", "sex")], rewrites)

    # A value without a confirmed term stays in original_sex_value only.
    assert list(table.frame["curated_sex"]) == ["Male", "Female", "NA", "NA"]
    assert list(table.frame["original_sex_value"]) == ["1", "2", "NA", "3"]
    assert list(table.rewritten["curated_sex"]) == [True, True, False, False]


def test_rewrites_match_values_mapped_after_a_schema_edit():
    # A re-map after a schema edit keys rows by the uploaded text ("1", "TRUE"),
    # not the inferred value ("1.0", "True"); a curator's term wins over the
    # engine's when a value has a row in both spellings.
    from app.services.exporter import FieldRewrites

    text, typed = _frames("id,code,smoker\na,1,TRUE\nb,2,FALSE\nc,,\n")
    sex = FieldRewrites()
    sex.update({"1": "Male", "2.0": "engine term", "2": "Female"})
    sex.reviewed.add("2")

    table = harmonize_table(
        text, typed, [_m("code", "sex"), _m("smoker", "smoking")],
        {"sex": sex, "smoking": {"TRUE": "Smoker"}},
    )

    assert list(table.frame["curated_sex"]) == ["Male", "Female", "NA"]
    assert list(table.frame["curated_smoking"]) == ["Smoker", "NA", "NA"]
    assert list(table.rewritten["curated_sex"]) == [True, True, False]


def test_missing_cells_are_never_rewritten():
    # Even when a lookup holds the missing-value marker or pandas' "nan".
    text, typed = _frames("id,site\na,NA\nb,lung\nc,\nd,NA\n")
    rewrites = {"body_site": {"NA": "not applicable", "nan": "?", "": "?", "lung": "Lung"}}

    table = harmonize_table(text, typed, [_m("site", "body_site")], rewrites)

    assert list(table.frame["curated_body_site"]) == ["NA", "Lung", "NA", "NA"]
    assert list(table.frame["curated_body_site_source"]) == ["NA", "site", "NA", "NA"]
    assert list(table.rewritten["curated_body_site"]) == [False, True, False, False]


def test_a_curated_field_is_written_as_the_labs_four_columns():
    from app.services.exporter import FieldRewrites

    text, typed = _frames("id,site,detail\n1,Lung,Lung\n2,lung,Upper lobe\n3,Unknown,\n4,,\n")
    terms = FieldRewrites()
    terms.update({"Lung": "Lung", "lung": "Lung", "Upper lobe": "Upper Lobe of the Lung"})
    terms.ids.update({"Lung": "NCIT:C12468", "lung": "NCIT:C12468", "Upper lobe": "NCIT:C33887"})

    table = harmonize_table(
        text, typed, [_m("id", "sample_id"), _m("site", "body_site"), _m("detail", "body_site")],
        {"body_site": terms},
    )

    assert list(table.frame.columns) == [
        "sample_id",
        "original_body_site_value",
        "curated_body_site",
        "curated_body_site_ontology_term_id",
        "curated_body_site_source",
    ]
    rows = table.frame.drop(columns="sample_id").values.tolist()
    assert rows == [
        # Repeats stay in the original value; a term is listed once.
        ["LUNG<;>LUNG", "Lung", "NCIT:C12468", "site;detail"],
        ["LUNG<;>UPPER LOBE", "Lung<;>Upper Lobe of the Lung", "NCIT:C12468<;>NCIT:C33887", "site;detail"],
        # A value without a confirmed term is left out of the curated value.
        ["UNKNOWN", "NA", "NA", "site"],
        ["NA", "NA", "NA", "NA"],
    ]
    # Only the curated column compares with the upload; it is a term change.
    assert list(table.original["curated_body_site"]) == ["Lung<;>Lung", "lung<;>Upper lobe", "Unknown", "NA"]
    assert list(table.rewritten["curated_body_site"]) == [True, True, False, False]
    assert table.original["original_body_site_value"].equals(table.frame["original_body_site_value"])


def test_identifiers_and_kept_columns_are_not_curated():
    text, typed = _frames("pid,curated_sex,sex\nP1,x,F\n")
    mappings = [_m("pid", "patient_id"), _m("curated_sex", "other", status="rejected"), _m("sex", "sex")]

    table = harmonize_table(text, typed, mappings, {"patient_id": {"P1": "Patient 1"}, "sex": {"F": "Female"}})

    # An identifier keeps one plain column; a rejected column whose name a
    # curated field takes is left out.
    assert list(table.frame.columns)[:2] == ["patient_id", "original_sex_value"]
    assert "curated_sex" in table.frame.columns and list(table.frame["curated_sex"]) == ["Female"]
    kept = next(p for p in table.plan if p.source == "curated_sex")
    assert (kept.action, kept.drop_reason, kept.conflicts_with) == ("dropped", "name_conflict", "sex")


def test_formula_like_text_is_escaped_but_numbers_are_not():
    text, typed = _frames(SAMPLE)
    table = harmonize_table(text, typed, [_m("note", "comment")], {})

    assert list(table.frame["comment"]) == ["'=SUM(A1)", "-5", "plain"]
    assert list(table.escaped["comment"]) == [True, False, False]


def test_column_plan_actions_and_drop_reasons():
    text, typed = _frames("a,b,c,d,e,f,g,h,i,j\n1,2,3,4,5,6,7,8,9,10\n")
    mappings = [
        _m("a", "alpha"),  # merged with 'e' into 'alpha'
        _m("b", "b"),  # matched: already the schema name
        _m("c", "gamma", status="rejected"),  # kept under its own name
        _m("d", None, status="pending"),  # no target suggested
        _m("e", "alpha", confidence=0.99),  # merged into 'alpha' with 'a'
        _m("f", "zeta", status="rejected"),
        _m("g", "f", status="pending"),  # takes the name 'f', so rejected 'f' can't be kept
        _m("h", "sample_id"),  # an identifier keeps one column...
        _m("i", "sample_id", status="pending", confidence=0.99),  # ...so 'i' loses to accepted 'h'
        _m("j", "alpha", status="pending", confidence=0.99),  # unreviewed: not merged into 'alpha'
    ]

    table = harmonize_table(text, typed, mappings, {})
    plan = {
        p.source: (p.target, p.action, p.mapping_status, p.drop_reason, p.conflicts_with)
        for p in table.plan
    }

    assert plan == {
        "a": ("alpha", "merged", "accepted", None, None),
        "b": ("b", "matched", "accepted", None, None),
        "c": ("c", "kept", "rejected", None, None),
        "d": (None, "dropped", "pending", "no_target", None),
        "e": ("alpha", "merged", "accepted", None, None),
        "f": (None, "dropped", "rejected", "name_conflict", "g"),  # 'g' took the name 'f'
        "g": ("f", "renamed", "pending", None, None),
        "h": ("sample_id", "renamed", "accepted", None, None),
        "i": (None, "dropped", "pending", "duplicate_target", "h"),  # 'h' took 'sample_id'
        "j": (None, "dropped", "pending", "duplicate_target", "a"),  # 'alpha' has accepted columns
    }
    # A merged column sits where its first column was uploaded.
    assert list(table.frame.columns) == ["alpha", "b", "c", "f", "sample_id"]
    assert list(table.frame["alpha"]) == ["1<;>5"]


def test_merged_columns_join_distinct_values_in_upload_order():
    text, typed = _frames(
        "Ethnicity,id,Region,Origin\n"
        "Asian,1,Japan,Asian\n"  # 'Asian' twice: listed once
        ",2,Kenya,\n"  # blank cells are skipped
        "NA,3,NA,\n"  # a row with no value keeps the first column's text
        "=x,4,,White\n"  # a merged value starting like a formula is escaped
    )
    mappings = [_m("Ethnicity", "race"), _m("id", "sample_id"), _m("Region", "race"), _m("Origin", "race")]

    table = harmonize_table(text, typed, mappings, {})

    assert list(table.frame.columns) == ["race", "sample_id"]
    assert list(table.frame["race"]) == ["Asian<;>Japan", "Kenya", "NA", "'=x<;>White"]
    assert list(table.original["race"]) == ["Asian<;>Japan", "Kenya", "NA", "=x<;>White"]
    assert list(table.escaped["race"]) == [False, False, False, True]
    assert not table.rewritten["race"].any()


def test_merge_follows_the_labs_curated_cbioportal_metadata():
    # Rows of MetaHarmonizer's examples/data/query_with_selected_fields_for_bie.csv,
    # written as the lab writes them: the original value keeps every value
    # (repeats too) in capitals, the curated value lists each term once, and
    # "<;>" keeps "...; INTRAHEPATIC" one value.
    from app.services.exporter import FieldRewrites

    text, typed = _frames(
        "DIAGNOSIS,DIAGNOSIS_AT_INCLUSION,SPECIFIC_DIAGNOSIS,DETAILED\n"
        "MYELODYSPLASTIC SYNDROMES,MYELODYSPLASTIC SYNDROMES,REFRACTORY ANAEMIA WITH EXCESS BLASTS,\n"
        "CHOLANGIOCARCINOMA,,,CHOLANGIOCARCINOMA; INTRAHEPATIC\n"
    )
    mappings = [_m(c, "disease") for c in ("DIAGNOSIS", "DIAGNOSIS_AT_INCLUSION", "SPECIFIC_DIAGNOSIS", "DETAILED")]
    disease = FieldRewrites()
    for raw, term, term_id in [
        ("MYELODYSPLASTIC SYNDROMES", "Myelodysplastic Syndrome", "NCIT:C3247"),
        ("REFRACTORY ANAEMIA WITH EXCESS BLASTS", "Myelodysplastic Syndrome with Excess Blasts", "NCIT:C7506"),
        ("CHOLANGIOCARCINOMA", "Cholangiocarcinoma", "NCIT:C4436"),
        ("CHOLANGIOCARCINOMA; INTRAHEPATIC", "Intrahepatic Cholangiocarcinoma", "NCIT:C35417"),
    ]:
        disease[raw], disease.ids[raw] = term, term_id

    table = harmonize_table(text, typed, mappings, {"disease": disease})

    assert table.frame.to_dict("list") == {
        "original_disease_value": [
            "MYELODYSPLASTIC SYNDROMES<;>MYELODYSPLASTIC SYNDROMES<;>REFRACTORY ANAEMIA WITH EXCESS BLASTS",
            "CHOLANGIOCARCINOMA<;>CHOLANGIOCARCINOMA; INTRAHEPATIC",
        ],
        "curated_disease": [  # the curated_disease values in that file
            "Myelodysplastic Syndrome<;>Myelodysplastic Syndrome with Excess Blasts",
            "Cholangiocarcinoma<;>Intrahepatic Cholangiocarcinoma",
        ],
        "curated_disease_ontology_term_id": ["NCIT:C3247<;>NCIT:C7506", "NCIT:C4436<;>NCIT:C35417"],
        "curated_disease_source": [
            "DIAGNOSIS;DIAGNOSIS_AT_INCLUSION;SPECIFIC_DIAGNOSIS",
            "DIAGNOSIS;DETAILED",
        ],
    }


def test_a_value_with_several_terms_follows_the_labs_harmonized_files():
    # MetaHarmonizer_Test_Data, data/per_study/harmonized/coad_silu_2022_harmonized.csv.
    # The lab's body site map gives one value several terms ("Liver, Inguinal" is
    # Liver and Inguinal Region); a curator records them joined by "<;>".
    from app.services.exporter import FieldRewrites

    text, typed = _frames(
        "LOCATION_METASTASIS_AT_DX,TUMOR_ANATOMIC_LOCATION\n"
        '"Bronchus, Lung, Liver, Lymph Node Intra-Abdominal",Ceceum\n'
        '"Liver, Inguinal",Colon Transversum\n'
    )
    site = FieldRewrites()
    for raw, terms, ids in [
        (
            "Bronchus, Lung, Liver, Lymph Node Intra-Abdominal",
            "Intra-Abdominal Lymph Node<;>Bronchus<;>Lung<;>Liver",
            "NCIT:C12360<;>NCIT:C12683<;>NCIT:C12468<;>NCIT:C12392",
        ),
        ("Ceceum", "Cecum", "NCIT:C12381"),
        ("Liver, Inguinal", "Liver<;>Inguinal Region", "NCIT:C12392<;>NCIT:C12726"),
        ("Colon Transversum", "Transverse Colon", "NCIT:C12385"),
    ]:
        site[raw], site.ids[raw] = terms, ids
    mappings = [_m("LOCATION_METASTASIS_AT_DX", "body_site"), _m("TUMOR_ANATOMIC_LOCATION", "body_site")]

    table = harmonize_table(text, typed, mappings, {"body_site": site})

    assert table.frame.to_dict("list") == {
        "original_body_site_value": [
            "BRONCHUS, LUNG, LIVER, LYMPH NODE INTRA-ABDOMINAL<;>CECEUM",
            "LIVER, INGUINAL<;>COLON TRANSVERSUM",
        ],
        "curated_body_site": [
            "Intra-Abdominal Lymph Node<;>Bronchus<;>Lung<;>Liver<;>Cecum",
            "Liver<;>Inguinal Region<;>Transverse Colon",
        ],
        "curated_body_site_ontology_term_id": [
            "NCIT:C12360<;>NCIT:C12683<;>NCIT:C12468<;>NCIT:C12392<;>NCIT:C12381",
            "NCIT:C12392<;>NCIT:C12726<;>NCIT:C12385",
        ],
        "curated_body_site_source": [  # that file joins these two with "<;>", most with ";"
            "LOCATION_METASTASIS_AT_DX;TUMOR_ANATOMIC_LOCATION",
            "LOCATION_METASTASIS_AT_DX;TUMOR_ANATOMIC_LOCATION",
        ],
    }


def test_each_term_of_a_row_is_listed_once_with_its_id():
    from app.services.exporter import FieldRewrites

    text, typed = _frames("a,b\nAbdomen/Pelvis,pelvis\n")
    site = FieldRewrites()
    site["Abdomen/Pelvis"], site.ids["Abdomen/Pelvis"] = "Abdomen<;>Pelvis", "NCIT:C12664"
    site["pelvis"], site.ids["pelvis"] = "Pelvis", "NCIT:C12767"

    table = harmonize_table(text, typed, [_m("a", "body_site"), _m("b", "body_site")], {"body_site": site})

    assert list(table.frame["curated_body_site"]) == ["Abdomen<;>Pelvis"]
    # The first value has no id for Pelvis; the second value's id fills it.
    assert list(table.frame["curated_body_site_ontology_term_id"]) == ["NCIT:C12664<;>NCIT:C12767"]


def test_a_field_the_lab_separates_with_a_semicolon_is_joined_with_one():
    # The lab's published cBioPortal metadata (Zenodo 16458151):
    # target_condition "Acute Lymphoblastic Leukemia;MLL Gene Rearrangement",
    # ids "NCIT:C3167;NCIT:C122623"; its data dictionary gives ";" for it.
    from app.services.exporter import FieldRewrites

    text, typed = _frames(
        "condition,condition_detail,design_a,design_b\n"
        "ALL,MLL rearranged,cohort,longitudinal\n"
        "ALL,,cohort,cohort\n"
    )
    condition = FieldRewrites()
    for raw, term, term_id in [
        ("ALL", "Acute Lymphoblastic Leukemia", "NCIT:C3167"),
        ("MLL rearranged", "MLL Gene Rearrangement", "NCIT:C122623"),
    ]:
        condition[raw], condition.ids[raw] = term, term_id
    mappings = [
        _m("condition", "target_condition"),
        _m("condition_detail", "target_condition"),
        _m("design_a", "study_design"),
        _m("design_b", "study_design"),
    ]
    separators = {"target_condition": ";", "study_design": ";"}

    table = harmonize_table(text, typed, mappings, {"target_condition": condition}, separators)

    assert list(table.frame["curated_target_condition"]) == [
        "Acute Lymphoblastic Leukemia;MLL Gene Rearrangement",
        "Acute Lymphoblastic Leukemia",
    ]
    assert list(table.frame["curated_target_condition_ontology_term_id"]) == ["NCIT:C3167;NCIT:C122623", "NCIT:C3167"]
    # The lab's notebooks always join the original values with "<;>".
    assert list(table.frame["original_target_condition_value"]) == ["ALL<;>MLL REARRANGED", "ALL"]
    assert list(table.frame["study_design"]) == ["cohort;longitudinal", "cohort"]

    # Merging alone is not a value change: the upload is joined the same way.
    preview = build_preview("s1", text, table)
    by_source = {c["source"]: c for c in preview["columns"]}
    assert by_source["design_a"]["value_changes"] == []
    assert {v["before"] for v in by_source["condition"]["value_changes"]} == {"ALL;MLL rearranged", "ALL"}


def test_other_fields_keep_the_default_separator():
    text, typed = _frames("a,b\nlung,liver\n")

    table = harmonize_table(
        text, typed, [_m("a", "body_site"), _m("b", "body_site")], {}, {"target_condition": ";"}
    )

    assert list(table.frame["body_site"]) == ["lung<;>liver"]


def test_merged_columns_rewrite_each_value_before_joining():
    text, typed = _frames("Gender,Sex\nF,female\nM,\n,F\n")
    rewrites = {"sex": {"F": "Female", "female": "Female", "M": "Male"}}

    table = harmonize_table(text, typed, [_m("Gender", "sex"), _m("Sex", "sex")], rewrites)

    # F and female are both "Female", so the first row's curated value holds one term.
    assert list(table.frame["curated_sex"]) == ["Female", "Male", "Female"]
    assert list(table.frame["original_sex_value"]) == ["F<;>FEMALE", "M", "F"]
    assert list(table.frame["curated_sex_source"]) == ["Gender;Sex", "Gender", "Sex"]
    assert list(table.original["curated_sex"]) == ["F<;>female", "M", "F"]
    assert list(table.rewritten["curated_sex"]) == [True, True, True]


def test_preview_shows_a_merged_column_once_with_its_changes():
    text, typed = _frames("Gender,id,Sex\nF,1,female\nM,2,M\n,3,\n")
    mappings = [_m("Gender", "sex"), _m("id", "sample_id"), _m("Sex", "sex", confidence=0.6)]
    table = harmonize_table(text, typed, mappings, {"sex": {"F": "Female", "female": "Female"}})

    preview = build_preview("s1", text, table)

    summary = preview["summary"]
    assert (summary["columns_before"], summary["columns_after"]) == (3, 5)
    assert (summary["merged"], summary["renamed"], summary["dropped"]) == (2, 1, 0)
    assert summary["pending"] == 0
    by_source = {c["source"]: c for c in preview["columns"]}
    assert (by_source["Gender"]["action"], by_source["Sex"]["action"]) == ("merged", "merged")
    assert by_source["Gender"]["target"] == "curated_sex"
    # The merged column's changes are reported once, on its first column; "M"
    # has no confirmed term, so the curated value leaves it out.
    assert by_source["Gender"]["changed_cells"] == 2
    assert by_source["Gender"]["value_changes"] == [
        {"before": "F<;>female", "after": "Female", "count": 1, "reason": "ontology"},
        {"before": "M<;>M", "after": "NA", "count": 1, "reason": "other"},
    ]
    assert (by_source["Sex"]["changed_cells"], by_source["Sex"]["value_changes"]) == (0, [])
    rows = preview["rows"]
    assert rows["columns"] == [
        "original_sex_value", "curated_sex", "curated_sex_ontology_term_id", "curated_sex_source", "sample_id",
    ]
    assert [r["values"] for r in rows["items"]] == [
        ["F<;>FEMALE", "Female", "NA", "Gender;Sex", "1"],
        ["M<;>M", "NA", "NA", "Gender;Sex", "2"],
        ["NA", "NA", "NA", "NA", "3"],
    ]
    # Only the curated column compares with the upload.
    assert [r["changes"] for r in rows["items"]] == [
        [{"column": 1, "before": "F<;>female", "reason": "ontology"}],
        [{"column": 1, "before": "M<;>M", "reason": "other"}],
        [],
    ]


def test_columns_without_any_mapping_are_dropped_as_unmapped():
    text, typed = _frames("keep,extra\n1,2\n")
    table = harmonize_table(text, typed, [_m("keep", "kept_field")], {})

    extra = next(p for p in table.plan if p.source == "extra")
    assert (extra.action, extra.mapping_status, extra.drop_reason) == ("dropped", "unmapped", "no_target")


def _preview_fixture():
    text, typed = _frames(
        "id,sex,site,note\n"
        "1,F,stool,ok\n"
        "2,M,stool,=1+1\n"
        "3,F,skin,ok\n"
        "4,F,stool,ok\n"
    )
    mappings = [
        _m("id", "sample_id"),
        _m("sex", "sex"),
        _m("site", "body_site", status="pending"),
        _m("note", "comment"),
    ]
    rewrites = {"sex": {"F": "Female", "M": "Male"}, "body_site": {"stool": "feces"}}
    return text, harmonize_table(text, typed, mappings, rewrites)


def test_preview_summary_and_grouped_value_changes():
    text, table = _preview_fixture()

    preview = build_preview("s1", text, table)

    assert preview["summary"] == {
        "rows": 4,
        "columns_before": 4,
        "columns_after": 10,  # sex and body_site are curated: four columns each
        "renamed": 3,
        "matched": 1,
        "merged": 0,
        "kept": 0,
        "dropped": 0,
        "pending": 1,
        "changed_cells": 9,
        "changed_rows": 4,
        "compared_cells": 40,
    }
    by_source = {c["source"]: c for c in preview["columns"]}
    assert by_source["sex"]["value_changes"] == [
        {"before": "F", "after": "Female", "count": 3, "reason": "ontology"},
        {"before": "M", "after": "Male", "count": 1, "reason": "ontology"},
    ]
    assert by_source["site"]["mapping_status"] == "pending"
    # "skin" has no confirmed term, so the curated value leaves it out.
    assert by_source["site"]["value_changes"] == [
        {"before": "stool", "after": "feces", "count": 3, "reason": "ontology"},
        {"before": "skin", "after": "NA", "count": 1, "reason": "other"},
    ]
    assert by_source["note"]["value_changes"] == [
        {"before": "=1+1", "after": "'=1+1", "count": 1, "reason": "escaped"}
    ]
    assert by_source["id"]["changed_cells"] == 0 and by_source["id"]["value_changes"] == []


def test_preview_lists_every_ontology_change_and_caps_only_escapes(monkeypatch):
    monkeypatch.setattr(export_preview, "MAX_VALUE_CHANGES", 1)
    text, typed = _frames("id,sex,note\n1,F,=1\n2,M,=2\n3,F,ok\n")
    table = harmonize_table(
        text, typed, [_m("id", "sample_id"), _m("sex", "sex"), _m("note", "comment")],
        {"sex": {"F": "Female", "M": "Male"}},
    )

    by_source = {c["source"]: c for c in build_preview("s1", text, table)["columns"]}

    assert [v["after"] for v in by_source["sex"]["value_changes"]] == ["Female", "Male"]
    assert by_source["sex"]["more_value_changes"] == 0
    assert [v["before"] for v in by_source["note"]["value_changes"]] == ["=1"]
    assert by_source["note"]["more_value_changes"] == 1


def test_every_rename_and_ontology_change_is_reported():
    # 19 columns renamed by the schema mapping and 30 values rewritten to terms.
    names = [f"col_{i}" for i in range(19)]
    values = [f"value {i}" for i in range(30)]
    header = ",".join([*names, "site"])
    lines = [",".join([*(f"{n}-{r}" for n in names), values[r % 30]]) for r in range(60)]
    text, typed = _frames("\n".join([header, *lines]) + "\n")
    mappings = [*(_m(n, f"field_{i}") for i, n in enumerate(names)), _m("site", "site")]
    rewrites = {"site": {v: f"Term {i}" for i, v in enumerate(values)}}
    table = harmonize_table(text, typed, mappings, rewrites)

    preview = build_preview("s1", text, table)

    assert preview["summary"]["renamed"] == 19
    site = next(c for c in preview["columns"] if c["source"] == "site")
    assert len(site["value_changes"]) == 30 and site["more_value_changes"] == 0
    assert {(v["before"], v["after"]) for v in site["value_changes"]} == {
        (v, f"Term {i}") for i, v in enumerate(values)
    }
    assert all(v["reason"] == "ontology" for v in site["value_changes"])


def test_preview_rows_page_and_filters():
    text, table = _preview_fixture()

    page = build_preview("s1", text, table, offset=1, limit=2)["rows"]
    assert page["columns"] == [
        "sample_id",
        "original_sex_value", "curated_sex", "curated_sex_ontology_term_id", "curated_sex_source",
        "original_body_site_value", "curated_body_site", "curated_body_site_ontology_term_id",
        "curated_body_site_source",
        "comment",
    ]
    assert page["total"] == 4 and [r["line"] for r in page["items"]] == [2, 3]
    assert page["changed_total"] == 4
    second = page["items"][0]
    assert second["values"] == ["2", "M", "Male", "NA", "sex", "STOOL", "feces", "NA", "site", "'=1+1"]
    assert second["changes"] == [
        {"column": 2, "before": "M", "reason": "ontology"},
        {"column": 6, "before": "stool", "reason": "ontology"},
        {"column": 9, "before": "=1+1", "reason": "escaped"},
    ]

    only_comment = build_preview("s1", text, table, changed_only=True, columns=["comment"])["rows"]
    assert only_comment["total"] == 1 and only_comment["items"][0]["line"] == 2
    assert only_comment["changed_total"] == 1

    everything = build_preview("s1", text, table, columns=["comment"])["rows"]
    assert everything["total"] == 4 and everything["changed_total"] == 1


def test_preview_filters_rows_changed_in_any_chosen_column():
    text, typed = _frames("id,a,b,c\n1,x,p,k\n2,y,q,k\n3,x,q,k\n4,z,p,k\n")
    mappings = [_m("id", "sample_id"), _m("a", "alpha"), _m("b", "beta"), _m("c", "gamma")]
    # Every value has a confirmed term; only x and q change.
    terms = {"alpha": {"x": "X", "y": "y", "z": "z"}, "beta": {"q": "Q", "p": "p"}}
    table = harmonize_table(text, typed, mappings, terms)

    def lines(**kwargs):
        rows = build_preview("s1", text, table, **kwargs)["rows"]
        return [r["line"] for r in rows["items"]], rows["changed_total"]

    assert lines(changed_only=True, columns=["curated_alpha"]) == ([1, 3], 2)
    assert lines(changed_only=True, columns=["curated_beta"]) == ([2, 3], 2)
    assert lines(changed_only=True, columns=["curated_beta", "curated_alpha"]) == ([1, 2, 3], 3)
    # A renamed column and an untouched one have no changed values.
    assert lines(changed_only=True, columns=["sample_id", "gamma"]) == ([], 0)
    # No scope means every column; without changed_only every row is kept.
    assert lines(changed_only=True) == ([1, 2, 3], 3)
    assert lines(columns=["curated_alpha"]) == ([1, 2, 3, 4], 2)


def test_preview_rejects_unknown_column():
    text, table = _preview_fixture()
    with pytest.raises(UnknownColumnError, match="'not_exported' is not a column"):
        build_preview("s1", text, table, columns=["not_exported"])
    # Filters use export names: the upload's "note" is exported as "comment".
    with pytest.raises(UnknownColumnError, match="'note', 'x' are not columns"):
        build_preview("s1", text, table, columns=["curated_sex", "note", "x"])


def test_preview_with_renames_only_has_no_changed_rows():
    text, typed = _frames("a,b\nx,1\ny,2\n")
    table = harmonize_table(text, typed, [_m("a", "alpha"), _m("b", "beta")], {})

    preview = build_preview("s1", text, table)

    assert preview["summary"]["changed_cells"] == 0
    assert preview["summary"]["renamed"] == 2
    # Every row is listed by default; asking for changed rows lists none.
    assert [r["values"] for r in preview["rows"]["items"]] == [["x", "1"], ["y", "2"]]
    changed = build_preview("s1", text, table, changed_only=True)["rows"]
    assert changed["total"] == 0 and changed["items"] == []
    assert changed["changed_total"] == 0


def test_preview_when_every_column_is_dropped():
    text, typed = _frames("a,b\nx,1\n")
    table = harmonize_table(text, typed, [], {})

    preview = build_preview("s1", text, table, changed_only=False)

    assert preview["summary"]["columns_after"] == 0
    assert preview["summary"]["dropped"] == 2
    assert preview["rows"]["columns"] == []
    assert preview["rows"]["items"] == [{"line": 1, "values": [], "changes": []}]
    assert preview["rows"]["changed_total"] == 0
