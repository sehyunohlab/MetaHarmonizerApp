"""Per-field ontology corpora from a target schema's data dictionary (the lab's
design: shbrief/MetaHarmonizerSchemaRegistry scripts/README.md and the engine's
``knowledge_db/combined_corpus_builder``).

Covers the units derived from dictionary entries, the installed check, and the
per-unit engine runs merged by score, with a fake engine. Needs the engine
package for its corpus helpers.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("pandas")
pytest.importorskip("metaharmonizer")
import pandas as pd  # noqa: E402

from app.engine_adapter import _field_corpora as fc  # noqa: E402
from app.engine_adapter import _ontology  # noqa: E402


def _row(**cells):
    row = {
        "col.name": "field",
        "col.class": "character",
        "corpus.type": "NA",
        "allowedvalues": "NA",
        "static.enum": "NA",
        "dynamic.enum": "NA",
        "dynamic.enum.property": "NA",
    }
    row.update({key.replace("_", "."): value for key, value in cells.items()})
    return row


def test_each_dynamic_root_is_a_unit_and_unfetchable_ontologies_are_left_out():
    corpus = fc.field_corpus(_row(dynamic_enum="NCIT:C7057|HANCESTRO:0004|NCBITaxon:1"))

    assert [unit.key for unit in corpus.units] == ["ncit_c7057_descendant"]
    assert corpus.units[0].root == "NCIT:C7057"
    assert [reason.split(":")[0] for reason in corpus.left_out] == ["HANCESTRO", "NCBITaxon"]


def test_a_root_the_engine_ships_uses_its_corpus_unless_only_children():
    (unit,) = fc.field_corpus(_row(dynamic_enum="UBERON_0001062")).units
    assert unit.root == "UBERON:0001062"
    assert unit.official == ("bodysite", "uberon")

    (unit,) = fc.field_corpus(
        _row(dynamic_enum="UBERON:0001062", dynamic_enum_property="children")
    ).units
    assert (unit.prop, unit.official) == ("children", None)


def test_allowed_values_bind_to_static_ids_by_position_one_unit_per_ontology():
    corpus = fc.field_corpus(
        _row(allowedvalues="Healthy|feces", static_enum="NCIT:C115935|UBERON:0001988")
    )

    assert {unit.ontology: unit.terms for unit in corpus.units} == {
        "ncit": (("NCIT:C115935", "Healthy"),),
        "uberon": (("UBERON:0001988", "feces"),),
    }
    assert corpus.left_out == ()


def test_static_ids_without_lined_up_labels_keep_the_ids():
    corpus = fc.field_corpus(_row(allowedvalues="a|b|c", static_enum="NCIT:C1|NCIT:C2"))

    (unit,) = corpus.units
    assert unit.terms == (("NCIT:C1", ""), ("NCIT:C2", ""))
    assert corpus.left_out == ("allowed values that do not line up with the static ids",)


@pytest.mark.parametrize(
    "row",
    [
        _row(col_class="numeric", dynamic_enum="NCIT:C7057"),  # e.g. age_at_death naming a root
        _row(corpus_type="regexp", allowedvalues="^[0-9]+$"),
        _row(allowedvalues="Male|Female"),  # labels without ontology ids
        _row(dynamic_enum="HANCESTRO:0004"),  # only an ontology the engine cannot fetch
        _row(),
    ],
)
def test_fields_without_a_corpus_the_engine_can_use(row):
    assert fc.field_corpus(row) is None


def test_the_lab_dictionaries_derive_their_units():
    cbio = fc.field_corpora("omicsmlprepo_cbio")
    assert set(cbio) == {"age_group", "country", "disease_type", "target_condition"}
    assert [unit.key for unit in cbio["target_condition"].units] == [
        "ncit_c7057_descendant",
        "efo_0000408_descendant",
    ]
    assert [unit.key for unit in cbio["country"].units] == ["ncit_c25464_descendant"]

    cmd = fc.field_corpora("cmd")
    assert [unit.ontology for unit in cmd["disease"].units] == ["ncit", "mondo", "ncit"]
    assert {unit.ontology for unit in cmd["body_site"].units} == {"uberon"}
    assert cmd["body_site_details"].units[0].official == ("bodysite", "uberon")
    assert [unit.key for unit in cmd["treatment"].units][0] == "ncit_c1908_descendant"

    # No ontology ids or roots in these dictionaries (or no dictionary).
    assert fc.field_corpora("cbioportal") == {}
    assert fc.field_corpora("gdc") == {}


@pytest.fixture
def kb(tmp_path, monkeypatch):
    """An empty KB: the data directory and the engine's FAISS directory."""
    from metaharmonizer import _paths

    monkeypatch.setenv("METAHARMONIZER_DATA_DIR", str(tmp_path / "data"))
    faiss_dir = tmp_path / "faiss"
    faiss_dir.mkdir()
    monkeypatch.setattr(_paths, "FAISS_INDEX_DIR", faiss_dir)
    fc.units_dir().mkdir(parents=True)
    return faiss_dir


def _install(faiss_dir, unit, frame):
    """Write a unit as the KB build leaves it: corpus, indexes, manifest entry."""
    frame.to_csv(fc.unit_csv(unit), index=False)
    indexes = fc._index_names(unit, "abcd1234")
    for name in indexes:
        (faiss_dir / name).write_bytes(b"index")
    manifest = fc.read_manifest()
    manifest.setdefault("units", {})[unit.key] = {
        "rows": len(frame),
        "bytes": fc.unit_csv(unit).stat().st_size,
        "corpus_hash": "abcd1234",
        "indexes": indexes,
    }
    (fc.units_dir() / fc.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    return [faiss_dir / name for name in indexes]


def test_a_unit_is_installed_only_with_its_built_corpus_and_indexes(kb):
    unit = fc.Unit(key="ncit_c1_descendant", ontology="ncit", root="NCIT:C1")
    assert not fc.installed(unit)

    indexes = _install(kb, unit, pd.DataFrame({"label": ["A"], "obo_id": ["NCIT:C2"]}))
    assert [index.name for index in indexes] == [
        "st_sap_bert_ncit_field_abcd1234.index",
        "st_sap_bert_ncit_field_abcd1234.index.ids.npy",
        "synonym_sap_bert_ncit_field_abcd1234.index",  # the default pipeline's stage 2.5
    ]
    assert fc.installed(unit)

    for index in indexes:
        index.write_bytes(b"")
        assert not fc.installed(unit)
        index.write_bytes(b"index")
    fc.unit_csv(unit).write_text("label,obo_id\nA,NCIT:C2\nB,NCIT:C3\n", encoding="utf-8")
    assert not fc.installed(unit)  # the corpus changed after its build


def test_an_engine_corpus_unit_is_installed_with_that_corpus(monkeypatch):
    from app.engine_adapter import kb_assets

    asked = []
    monkeypatch.setattr(
        kb_assets, "engine_corpus_installed", lambda *tuple_: asked.append(tuple_) or True
    )
    unit = fc.Unit(key="u", ontology="uberon", root="UBERON:0001062", official=("bodysite", "uberon"))

    assert fc.installed(unit)
    assert asked == [("bodysite", "uberon")]


def test_unit_corpora_are_read_verbatim():
    import io

    frame = fc.read_unit(io.StringIO("label,obo_id\nNA,NCIT:C1\nNone,NCIT:C2\n"))
    assert frame["label"].tolist() == ["NA", "None"]


def test_the_concept_tables_get_the_suffix_the_engine_will_use():
    # The engine's own normalization and hash, without constructing it (which
    # would fetch the corpus's concepts).
    import logging

    from metaharmonizer.engine.ontology_mapping_engine import OntoMapEngine
    from metaharmonizer.utils.corpus_hash import compute_corpus_hash

    corpus = pd.DataFrame(
        {
            "label": ["Lung Carcinoma", "Melanoma", "Melanoma", "feces", "NA"],
            "obo_id": ["NCIT:C4878", "NCIT:C3224", "NCIT:C3224", "UBERON:0001988", "NCIT:C1"],
            "iri": ["", "", "", "", ""],
        }
    )
    engine = OntoMapEngine.__new__(OntoMapEngine)
    engine._logger = logging.getLogger("test")
    engine.filter_obsolete = False

    assert fc._engine_corpus_hash(corpus) == compute_corpus_hash(engine._normalize_df(corpus, need_code=True))


def test_a_unit_is_built_whole_or_not_at_all(kb, monkeypatch):
    from metaharmonizer.engine import ontology_mapping_engine

    unit = fc.Unit(key="ncit_c1_descendant", ontology="ncit", root="NCIT:C1")
    monkeypatch.setattr(fc, "FETCH_BACKOFF_SECONDS", 0)
    monkeypatch.setattr(
        fc,
        "build_unit_records",
        lambda unit_: [{"label": "A", "obo_id": "NCIT:C2"}, {"label": "B", "obo_id": "NCIT:C3"}],
    )
    missing = [{"C3"}, set()]  # the first construction left a concept out
    monkeypatch.setattr(fc, "_missing_concepts", lambda engine, unit_: missing.pop(0))
    filled = []
    monkeypatch.setattr(
        fc,
        "_fill_concept_tables",
        lambda unit_, corpus, records: filled.append((corpus["label"].tolist(), len(records))) or "_abcd1234",
    )
    constructed = []

    class Engine:
        def __init__(self, *, corpus_category, query_ls, corpus_df, ontology_source, **options):
            assert not fc.unit_csv(unit).exists()  # the corpus is written last
            assert options == fc.UNIT_ENGINE_KWARGS
            constructed.append(corpus_df["label"].tolist())
            self._corpus_hash = "abcd1234"

        def run(self):
            for name in fc._index_names(unit, "abcd1234"):
                (kb / name).write_bytes(b"index")

    monkeypatch.setattr(ontology_mapping_engine, "OntoMapEngine", Engine)

    entry = fc.build_units([unit])[unit.key]

    assert filled == [(["A", "B"], 2)]  # the concept tables come from the fetched records
    assert constructed == [["A", "B"], ["A", "B"]]
    assert (entry["rows"], entry["corpus_hash"]) == (2, "abcd1234")
    assert fc.installed(unit)
    # Installed: a second build leaves it alone.
    assert fc.build_units([unit])[unit.key] == entry
    assert len(constructed) == 2


def test_a_unit_whose_concepts_cannot_be_fetched_is_not_installed(kb, monkeypatch):
    from metaharmonizer.engine import ontology_mapping_engine

    unit = fc.Unit(key="ncit_c1_descendant", ontology="ncit", root="NCIT:C1")
    monkeypatch.setattr(fc, "FETCH_BACKOFF_SECONDS", 0)
    monkeypatch.setattr(fc, "build_unit_records", lambda unit_: [{"label": "A", "obo_id": "NCIT:C2"}])
    monkeypatch.setattr(fc, "_missing_concepts", lambda engine, unit_: {"C2"})
    monkeypatch.setattr(fc, "_fill_concept_tables", lambda *args: "_abcd1234")

    class Engine:
        def __init__(self, **kwargs):
            self._corpus_hash = "abcd1234"

        def run(self):
            pytest.fail("an incomplete unit must not be indexed")

    monkeypatch.setattr(ontology_mapping_engine, "OntoMapEngine", Engine)

    with pytest.raises(RuntimeError, match="no concept data for 1 code"):
        fc.build_units([unit])
    assert not fc.unit_csv(unit).exists()
    assert not fc.unit_csv(unit).with_suffix(".csv.tmp").exists()
    assert not fc.installed(unit)


def test_a_field_maps_against_each_installed_unit_and_merges_by_score(kb):
    ncit = fc.Unit(key="ncit_u", ontology="ncit", root="NCIT:C7057")
    mondo = fc.Unit(key="mondo_u", ontology="mondo", root="MONDO:0000001")
    unbuilt = fc.Unit(key="efo_u", ontology="efo", root="EFO:0000408")
    _install(kb, ncit, pd.DataFrame({"label": ["Lung Carcinoma", "Melanoma"], "obo_id": ["NCIT:C4878", "NCIT:C3224"]}))
    _install(kb, mondo, pd.DataFrame({"label": ["lung carcinoma", "Melanoma"], "obo_id": ["MONDO:0005138", "MONDO:0005105"]}))
    candidates = {
        "ncit": {"lung ca": ("Lung Carcinoma", 0.80), "melanoma": ("Melanoma", 1.0), "xyz": ("Not Found", 0.0)},
        "mondo": {"lung ca": ("lung carcinoma", 0.92), "melanoma": ("Melanoma", 0.99), "xyz": ("Not Found", 0.0)},
    }
    runs = []

    class Engine:
        def __init__(self, *, corpus_category, query_ls, corpus_df, ontology_source, **options):
            assert corpus_category == fc.UNIT_CATEGORY
            assert options == fc.UNIT_ENGINE_KWARGS
            assert len(corpus_df) == 2
            runs.append(ontology_source)
            self.source, self.queries = ontology_source, query_ls

        def run(self):
            return pd.DataFrame(
                [
                    {"query": q, "match1": candidates[self.source][q][0], "match1_score": candidates[self.source][q][1]}
                    for q in self.queries
                ]
            )

    corpus = fc.FieldCorpus(field="disease", units=(ncit, mondo, unbuilt))
    rows = _ontology._map_with_units(Engine, "disease", corpus, ["lung ca", "melanoma", "xyz"])

    assert runs == ["ncit", "mondo"]  # never the unbuilt unit
    by_value = {row["raw_value"]: row for row in rows}
    # The best-scoring candidate across the units, with its own unit's code.
    assert (by_value["lung ca"]["ontology_term"], by_value["lung ca"]["ontology_id"]) == (
        "lung carcinoma",
        "MONDO:0005138",
    )
    assert by_value["lung ca"]["confidence_score"] == 0.92
    # The same label in two units keeps the higher score and that unit's code.
    assert (by_value["melanoma"]["ontology_term"], by_value["melanoma"]["ontology_id"]) == (
        "Melanoma",
        "NCIT:C3224",
    )
    # No candidate anywhere: an unmapped row.
    assert (by_value["xyz"]["ontology_term"], by_value["xyz"]["ontology_id"]) == (None, None)
    assert all(row["field_name"] == "disease" for row in rows)


def test_the_target_schemas_dictionary_routes_before_the_engine_corpora(monkeypatch):
    # cMD's dictionary lists UBERON terms for body_site: they win over the
    # engine corpus the field name would otherwise get.
    unit = fc.Unit(key="uberon_terms", ontology="uberon", terms=(("UBERON:0001988", "feces"),))
    corpus = fc.FieldCorpus(field="body_site", units=(unit,))
    asked = []

    def corpora(key):
        asked.append(key)
        return {"body_site": corpus} if key == "cmd" else {}

    monkeypatch.setattr(_ontology, "runtime_asset_issues", lambda: [])
    monkeypatch.setattr(fc, "field_corpora", corpora)
    monkeypatch.setattr(fc, "installed", lambda unit: True)
    mapped = []
    monkeypatch.setattr(
        _ontology,
        "_map_with_units",
        lambda engine, field, corpus_, values: mapped.append((field, corpus_, values)) or [],
    )

    class Engine:
        def __init__(self, *, corpus_category, query_ls, ontology_source, **options):
            mapped.append((corpus_category, ontology_source, query_ls))
            self.query = query_ls

        def run(self):
            return pd.DataFrame([{"query": q, "match1": q, "match1_score": 1.0} for q in self.query])

    class Pkg:
        OntoMapEngine = Engine

    raw_df = pd.DataFrame({"site": ["stool"], "dx": ["melanoma"]})
    schema = [
        {"raw_column": "site", "matched_field": "body_site"},
        {"raw_column": "dx", "matched_field": "disease"},
    ]
    _, handled = _ontology.map_values_via_engine(Pkg(), raw_df, schema, "cmd")

    assert asked == ["cmd"]
    assert handled == {"body_site", "disease"}
    assert mapped == [("body_site", corpus, ["stool"]), ("disease", "ncit", ["melanoma"])]


def test_an_unknown_target_schema_uses_the_default_schemas_dictionary(monkeypatch):
    from app.engine_adapter import _schema_registry

    asked = []
    monkeypatch.setattr(_ontology, "runtime_asset_issues", lambda: [])
    monkeypatch.setattr(fc, "field_corpora", lambda key: asked.append(key) or {})

    class Pkg:
        OntoMapEngine = object

    _ontology.map_values_via_engine(Pkg(), pd.DataFrame({"x": []}), [], "no-such-schema")

    assert asked == [_schema_registry.default_key()]


def test_an_unreadable_dictionary_leaves_the_engine_corpora(monkeypatch):
    def broken(key):
        raise OSError("dictionary missing")

    monkeypatch.setattr(_ontology, "runtime_asset_issues", lambda: [])
    monkeypatch.setattr(fc, "field_corpora", broken)

    class Engine:
        def __init__(self, *, corpus_category, query_ls, ontology_source, **options):
            self.query = query_ls

        def run(self):
            return pd.DataFrame([{"query": q, "match1": "Melanoma", "match1_score": 1.0} for q in self.query])

    class Pkg:
        OntoMapEngine = Engine

    rows, handled = _ontology.map_values_via_engine(
        Pkg(), pd.DataFrame({"dx": ["melanoma"]}), [{"raw_column": "dx", "matched_field": "disease"}], "cmd"
    )

    assert handled == {"disease"}
    assert rows[0]["ontology_term"] == "Melanoma"


def test_a_field_is_ontology_bearing_when_its_schema_has_an_installed_corpus(monkeypatch):
    unit = fc.Unit(key="ncit_c25464_descendant", ontology="ncit", root="NCIT:C25464")
    monkeypatch.setenv("ENGINE_IMPL", "metaharmonizer")
    monkeypatch.setenv("ONTOLOGY_ENGINE", "1")
    monkeypatch.setattr(
        fc, "field_corpora", lambda key: {"country": fc.FieldCorpus("country", (unit,))} if key == "cmd" else {}
    )
    monkeypatch.setattr(fc, "installed", lambda unit: True)

    assert _ontology.is_ontology_field("country", "cmd")
    assert not _ontology.is_ontology_field("ancestry", "cmd")

    monkeypatch.setattr(fc, "installed", lambda unit: False)
    assert not _ontology.is_ontology_field("country", "cmd")

    monkeypatch.setenv("ONTOLOGY_ENGINE", "0")
    monkeypatch.setattr(fc, "installed", lambda unit: True)
    assert not _ontology.is_ontology_field("country", "cmd")
