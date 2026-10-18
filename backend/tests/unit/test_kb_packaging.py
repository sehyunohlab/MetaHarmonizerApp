from __future__ import annotations

import functools
import hashlib
import http.server
import tarfile
import threading
from pathlib import Path

import pytest

from scripts import package_kb, seed_kb


def test_package_fails_closed_when_assets_are_incomplete(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(package_kb, "_corpus_csvs", lambda: [])
    monkeypatch.setattr(package_kb, "_model_cache_files", lambda: (None, []))
    monkeypatch.setattr(package_kb, "_hf_schema_model", lambda: (None, []))
    monkeypatch.setattr(
        package_kb,
        "installed_kb_issues",
        lambda **_kwargs: ["missing engine database"],
    )
    monkeypatch.setattr(package_kb, "_SCHEMA_CACHE", tmp_path / "missing-cache.json")

    result = package_kb.build_bundle(tmp_path / "bundle.tar.gz", dry_run=True)

    assert result == 1


def test_package_allows_explicit_development_only_incomplete_bundle(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(package_kb, "_corpus_csvs", lambda: [])
    monkeypatch.setattr(package_kb, "_model_cache_files", lambda: (None, []))
    monkeypatch.setattr(package_kb, "_hf_schema_model", lambda: (None, []))
    monkeypatch.setattr(
        package_kb,
        "installed_kb_issues",
        lambda **_kwargs: ["missing engine database"],
    )
    monkeypatch.setattr(package_kb, "_SCHEMA_CACHE", tmp_path / "missing-cache.json")

    result = package_kb.build_bundle(
        tmp_path / "bundle.tar.gz",
        dry_run=True,
        allow_incomplete=True,
    )

    assert result == 0


def test_seed_rejects_incomplete_bundle_before_extraction(tmp_path: Path) -> None:
    payload = tmp_path / "placeholder.txt"
    payload.write_text("incomplete", encoding="utf-8")
    bundle = tmp_path / "incomplete.tar.gz"
    with tarfile.open(bundle, "w:gz") as archive:
        archive.add(payload, arcname=payload.name)

    assert seed_kb.seed(bundle, force=False) == 1


def _field_corpus(tmp_path: Path) -> list[Path]:
    root = tmp_path / "fields"
    root.mkdir()
    (root / "units.json").write_text('{"units": {}}', encoding="utf-8")
    (root / "ncit_c25464_descendant_corpus.csv").write_text("label,obo_id\nChile,NCIT:C16427\n", encoding="utf-8")
    return [root / "units.json", root / "ncit_c25464_descendant_corpus.csv"]


def test_package_bundles_the_field_corpora(tmp_path, monkeypatch) -> None:
    cache = tmp_path / "cache.json"
    cache.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(package_kb, "_corpus_csvs", lambda: [])
    monkeypatch.setattr(package_kb, "_field_corpus_files", lambda: _field_corpus(tmp_path))
    monkeypatch.setattr(package_kb, "_model_cache_files", lambda: (None, []))
    monkeypatch.setattr(package_kb, "_hf_schema_model", lambda: (None, []))
    monkeypatch.setattr(package_kb, "installed_kb_issues", lambda **_kwargs: [])
    monkeypatch.setattr(package_kb, "_SCHEMA_CACHE", cache)
    monkeypatch.setattr(package_kb, "_engine_export", lambda dest: dest.write_bytes(b"kb"))

    assert package_kb.build_bundle(tmp_path / "bundle.tar.gz") == 0

    with tarfile.open(tmp_path / "bundle.tar.gz") as archive:
        names = set(archive.getnames())
    assert {"corpus/fields/units.json", "corpus/fields/ncit_c25464_descendant_corpus.csv"} <= names


def test_seed_installs_the_field_corpora(tmp_path, monkeypatch) -> None:
    pytest.importorskip("metaharmonizer")
    bundle = tmp_path / "bundle.tar.gz"
    with tarfile.open(bundle, "w:gz") as archive:
        for path in _field_corpus(tmp_path):
            archive.add(path, arcname=f"corpus/fields/{path.name}")
    monkeypatch.setenv("METAHARMONIZER_DATA_DIR", str(tmp_path / "data"))

    assert seed_kb.seed(bundle, force=False, allow_incomplete=True) == 0

    installed = tmp_path / "data" / "corpus" / "fields"
    assert sorted(p.name for p in installed.iterdir()) == [
        "ncit_c25464_descendant_corpus.csv",
        "units.json",
    ]


@pytest.fixture
def release(tmp_path):
    """A local stand-in for the release download URL: serves ``tmp_path/release``."""
    root = tmp_path / "release"
    root.mkdir()
    handler = functools.partial(_QuietHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield root, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args) -> None:
        pass


def test_download_joins_a_bundle_published_in_parts(release, tmp_path) -> None:
    root, base = release
    payload = bytes(range(256)) * 41
    (root / "kb_offline_bundle.tar.gz.part00").write_bytes(payload[:5000])
    (root / "kb_offline_bundle.tar.gz.part01").write_bytes(payload[5000:])
    (root / "kb_offline_bundle.tar.gz.parts").write_text(
        "kb_offline_bundle.tar.gz.part00\nkb_offline_bundle.tar.gz.part01\n", encoding="utf-8"
    )
    dest = tmp_path / "out" / "kb_offline_bundle.tar.gz"

    seed_kb._download(
        f"{base}/kb_offline_bundle.tar.gz", dest, sha256=hashlib.sha256(payload).hexdigest()
    )

    assert dest.read_bytes() == payload


def test_download_takes_a_whole_bundle_without_a_parts_list(release, tmp_path) -> None:
    root, base = release
    (root / "kb_offline_bundle.tar.gz").write_bytes(b"whole")
    dest = tmp_path / "kb_offline_bundle.tar.gz"

    seed_kb._download(f"{base}/kb_offline_bundle.tar.gz", dest, sha256=hashlib.sha256(b"whole").hexdigest())

    assert dest.read_bytes() == b"whole"


def test_download_refuses_a_parts_list_naming_other_files(release, tmp_path) -> None:
    root, base = release
    (root / "kb_offline_bundle.tar.gz.parts").write_text("../secrets\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="invalid parts list"):
        seed_kb._download(f"{base}/kb_offline_bundle.tar.gz", tmp_path / "out.tar.gz")
