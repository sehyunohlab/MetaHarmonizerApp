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

    assert list(table.frame["sex"]) == ["Male", "Female", "", "3"]
    assert list(table.rewritten["sex"]) == [True, True, False, False]


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

    assert list(table.frame["sex"]) == ["Male", "Female", ""]
    assert list(table.frame["smoking"]) == ["Smoker", "FALSE", ""]
    assert list(table.rewritten["sex"]) == [True, True, False]


def test_missing_cells_are_never_rewritten():
    # Even when a lookup holds the missing-value marker or pandas' "nan".
    text, typed = _frames("id,site\na,NA\nb,lung\nc,\nd,NA\n")
    rewrites = {"body_site": {"NA": "not applicable", "nan": "?", "": "?", "lung": "Lung"}}

    table = harmonize_table(text, typed, [_m("site", "body_site")], rewrites)

    assert list(table.frame["body_site"]) == ["NA", "Lung", "", "NA"]
    assert list(table.rewritten["body_site"]) == [False, True, False, False]


def test_formula_like_text_is_escaped_but_numbers_are_not():
    text, typed = _frames(SAMPLE)
    table = harmonize_table(text, typed, [_m("note", "comment")], {})

    assert list(table.frame["comment"]) == ["'=SUM(A1)", "-5", "plain"]
    assert list(table.escaped["comment"]) == [True, False, False]


def test_column_plan_actions_and_drop_reasons():
    text, typed = _frames("a,b,c,d,e,f,g\n1,2,3,4,5,6,7\n")
    mappings = [
        _m("a", "alpha"),  # renamed
        _m("b", "b"),  # matched: already the schema name
        _m("c", "gamma", status="rejected"),  # kept under its own name
        _m("d", None, status="pending"),  # no target suggested
        _m("e", "alpha", status="pending", confidence=0.99),  # loses 'alpha' to accepted 'a'
        _m("f", "zeta", status="rejected"),
        _m("g", "f", status="pending"),  # takes the name 'f', so rejected 'f' can't be kept
    ]

    table = harmonize_table(text, typed, mappings, {})
    plan = {
        p.source: (p.target, p.action, p.mapping_status, p.drop_reason, p.conflicts_with)
        for p in table.plan
    }

    assert plan == {
        "a": ("alpha", "renamed", "accepted", None, None),
        "b": ("b", "matched", "accepted", None, None),
        "c": ("c", "kept", "rejected", None, None),
        "d": (None, "dropped", "pending", "no_target", None),
        "e": (None, "dropped", "pending", "duplicate_target", "a"),  # 'a' took 'alpha'
        "f": (None, "dropped", "rejected", "name_conflict", "g"),  # 'g' took the name 'f'
        "g": ("f", "renamed", "pending", None, None),
    }
    assert list(table.frame.columns) == ["alpha", "b", "c", "f"]


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
        "columns_after": 4,
        "renamed": 3,
        "matched": 1,
        "kept": 0,
        "dropped": 0,
        "pending": 1,
        "changed_cells": 8,
        "changed_rows": 4,
        "compared_cells": 16,
    }
    by_source = {c["source"]: c for c in preview["columns"]}
    assert by_source["sex"]["value_changes"] == [
        {"before": "F", "after": "Female", "count": 3, "reason": "ontology"},
        {"before": "M", "after": "Male", "count": 1, "reason": "ontology"},
    ]
    assert by_source["site"]["mapping_status"] == "pending"
    assert by_source["site"]["value_changes"] == [
        {"before": "stool", "after": "feces", "count": 3, "reason": "ontology"}
    ]
    assert by_source["note"]["value_changes"] == [
        {"before": "=1+1", "after": "'=1+1", "count": 1, "reason": "escaped"}
    ]
    assert by_source["id"]["changed_cells"] == 0 and by_source["id"]["value_changes"] == []


def test_preview_caps_listed_value_changes(monkeypatch):
    monkeypatch.setattr(export_preview, "MAX_VALUE_CHANGES", 1)
    text, table = _preview_fixture()

    sex = next(c for c in build_preview("s1", text, table)["columns"] if c["source"] == "sex")

    assert [v["before"] for v in sex["value_changes"]] == ["F"]  # most frequent first
    assert sex["more_value_changes"] == 1


def test_preview_rows_page_and_filters():
    text, table = _preview_fixture()

    page = build_preview("s1", text, table, offset=1, limit=2)["rows"]
    assert page["columns"] == ["sample_id", "sex", "body_site", "comment"]
    assert page["total"] == 4 and [r["line"] for r in page["items"]] == [2, 3]
    second = page["items"][0]
    assert second["values"] == ["2", "Male", "feces", "'=1+1"]
    assert second["changes"] == [
        {"column": 1, "before": "M", "reason": "ontology"},
        {"column": 2, "before": "stool", "reason": "ontology"},
        {"column": 3, "before": "=1+1", "reason": "escaped"},
    ]

    only_comment = build_preview("s1", text, table, changed_only=True, column="comment")["rows"]
    assert only_comment["total"] == 1 and only_comment["items"][0]["line"] == 2

    everything = build_preview("s1", text, table, column="comment")["rows"]
    assert everything["total"] == 4


def test_preview_rejects_unknown_column():
    text, table = _preview_fixture()
    with pytest.raises(UnknownColumnError):
        build_preview("s1", text, table, column="not_exported")


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


def test_preview_when_every_column_is_dropped():
    text, typed = _frames("a,b\nx,1\n")
    table = harmonize_table(text, typed, [], {})

    preview = build_preview("s1", text, table, changed_only=False)

    assert preview["summary"]["columns_after"] == 0
    assert preview["summary"]["dropped"] == 2
    assert preview["rows"]["columns"] == []
    assert preview["rows"]["items"] == [{"line": 1, "values": [], "changes": []}]
