from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from scripts.graft_efo import _copy_efo_tables, _copy_hf_hub


def _rows(path: Path, table: str) -> list[tuple]:
    with sqlite3.connect(path) as connection:
        return connection.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()


def test_copy_efo_tables_preserves_source_and_replaces_destination(tmp_path: Path):
    old_db = tmp_path / "old.sqlite"
    new_db = tmp_path / "new.sqlite"
    with sqlite3.connect(old_db) as connection:
        connection.execute('CREATE TABLE "efo_synonym_phenotype" (id INTEGER, label TEXT)')
        connection.executemany(
            'INSERT INTO "efo_synonym_phenotype" VALUES (?, ?)',
            [(1, "alpha"), (2, "beta")],
        )
        connection.execute('CREATE TABLE "not_efo" (id INTEGER)')
    with sqlite3.connect(new_db) as connection:
        connection.execute('CREATE TABLE "efo_synonym_phenotype" (id INTEGER, label TEXT)')
        connection.execute('INSERT INTO "efo_synonym_phenotype" VALUES (9, "stale")')

    _copy_efo_tables(old_db, new_db)

    expected = [(1, "alpha"), (2, "beta")]
    assert _rows(old_db, "efo_synonym_phenotype") == expected
    assert _rows(new_db, "efo_synonym_phenotype") == expected
    with sqlite3.connect(new_db) as connection:
        names = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "not_efo" not in names


def test_copy_efo_tables_handles_source_only_table(tmp_path: Path):
    old_db = tmp_path / "old.sqlite"
    new_db = tmp_path / "new.sqlite"
    with sqlite3.connect(old_db) as connection:
        connection.execute('CREATE TABLE "efo_phenotype" (id INTEGER)')
        connection.execute('INSERT INTO "efo_phenotype" VALUES (1)')
    sqlite3.connect(new_db).close()

    _copy_efo_tables(old_db, new_db)

    assert _rows(old_db, "efo_phenotype") == [(1,)]
    assert _rows(new_db, "efo_phenotype") == [(1,)]


def test_copy_hf_hub_preserves_model_tree(tmp_path: Path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    model = source / "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots" / "v1"
    model.mkdir(parents=True)
    (model / "config.json").write_text('{"model":"mini"}', encoding="utf-8")
    (model / "model.safetensors").write_bytes(b"weights")

    copied = _copy_hf_hub(source, destination)

    assert copied == 2
    copied_model = destination / model.relative_to(source)
    assert (copied_model / "config.json").read_text(encoding="utf-8") == '{"model":"mini"}'
    assert (copied_model / "model.safetensors").read_bytes() == b"weights"


def test_copy_hf_hub_handles_missing_source(tmp_path: Path):
    assert _copy_hf_hub(tmp_path / "missing", tmp_path / "destination") == 0


MODEL = "models--sentence-transformers--all-MiniLM-L6-v2"


def _hf_model(hub: Path, *, blob_mode: int) -> None:
    """One model laid out like the HuggingFace hub cache: the content lives in
    ``blobs/`` and ``snapshots/`` links to it."""
    blob = hub / MODEL / "blobs" / "53aa5117"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"weights")
    blob.chmod(blob_mode)
    snapshot = hub / MODEL / "snapshots" / "v1"
    snapshot.mkdir(parents=True)
    (snapshot / "model.safetensors").symlink_to("../../blobs/53aa5117")


@pytest.fixture
def hub_layout(tmp_path: Path) -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root ignores file permissions, which this regression is about")
    try:
        (tmp_path / "probe").symlink_to("target")
    except OSError:
        pytest.skip("creating symlinks needs extra privileges on this platform")


def test_copy_hf_hub_over_a_cache_the_kb_build_already_filled(tmp_path: Path, hub_layout):
    # The published bundle stores read-only blobs, and the KB build has just
    # downloaded the same model (the scheduled refresh that failed on 2026-10-01).
    source = tmp_path / "bundle" / "hf_hub"
    destination = tmp_path / "home" / "hub"
    _hf_model(source, blob_mode=0o444)
    _hf_model(destination, blob_mode=0o644)

    _copy_hf_hub(source, destination)

    link = destination / MODEL / "snapshots" / "v1" / "model.safetensors"
    assert link.is_symlink()
    assert os.readlink(link) == "../../blobs/53aa5117"
    assert link.read_bytes() == b"weights"


def test_copy_hf_hub_can_run_twice(tmp_path: Path, hub_layout):
    source = tmp_path / "bundle" / "hf_hub"
    destination = tmp_path / "home" / "hub"
    _hf_model(source, blob_mode=0o444)

    _copy_hf_hub(source, destination)
    _copy_hf_hub(source, destination)

    assert (destination / MODEL / "snapshots" / "v1" / "model.safetensors").is_symlink()
    assert (destination / MODEL / "blobs" / "53aa5117").read_bytes() == b"weights"