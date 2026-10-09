from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import io
from pathlib import Path
from zipfile import ZipFile

import pytest
from packaging.requirements import Requirement

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "strip_unused_nltk_dependency.py"
SPEC = importlib.util.spec_from_file_location("strip_unused_nltk_dependency", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _wheel(
    tmp_path: Path,
    source: str,
    requirement: str = "nltk",
) -> Path:
    wheel = tmp_path / "example-1.0.0-py3-none-any.whl"
    metadata_name = "example-1.0.0.dist-info/METADATA"
    record_name = "example-1.0.0.dist-info/RECORD"
    metadata = (
        "Metadata-Version: 2.1\n"
        "Name: example\n"
        "Version: 1.0.0\n"
        f"Requires-Dist: {requirement}\n"
        "Requires-Dist: requests>=2\n"
    ).encode()
    with ZipFile(wheel, "w") as archive:
        archive.writestr("example/__init__.py", source)
        archive.writestr(metadata_name, metadata)
        archive.writestr(
            record_name,
            f"{metadata_name},sha256=old,{len(metadata)}\n{record_name},,\n",
        )
    return wheel


def test_strip_removes_metadata_and_updates_record(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_SOURCE_ROOTS", ())
    wheel = _wheel(tmp_path, "VALUE = 1\n")

    assert MODULE.strip_unused_dependency(wheel)
    MODULE.verify_dependency_absent(wheel)

    with ZipFile(wheel) as archive:
        metadata_name = "example-1.0.0.dist-info/METADATA"
        metadata = archive.read(metadata_name)
        rows = list(
            csv.reader(
                io.StringIO(archive.read("example-1.0.0.dist-info/RECORD").decode("utf-8"))
            )
        )
    assert b"Requires-Dist: nltk" not in metadata
    assert b"Requires-Dist: requests>=2" in metadata
    metadata_row = next(row for row in rows if row[0] == metadata_name)
    digest = base64.urlsafe_b64encode(hashlib.sha256(metadata).digest()).rstrip(b"=").decode()
    assert metadata_row == [metadata_name, f"sha256={digest}", str(len(metadata))]


def test_strip_refuses_when_engine_references_nltk(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_SOURCE_ROOTS", ())
    wheel = _wheel(tmp_path, "import nltk\n")

    with pytest.raises(ValueError, match="referenced at runtime"):
        MODULE.strip_unused_dependency(wheel)


@pytest.mark.parametrize(
    "requirement",
    [
        "NLTK>=3.9",
        'nltk[corpus]~=3.9; python_version >= "3.10"',
        "nltk @ https://example.invalid/nltk.whl",
    ],
)
def test_strip_recognizes_pep508_dependency_forms(
    tmp_path: Path,
    monkeypatch,
    requirement: str,
) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_SOURCE_ROOTS", ())
    wheel = _wheel(tmp_path, "VALUE = 1\n", requirement)

    assert MODULE.strip_unused_dependency(wheel)
    MODULE.verify_dependency_absent(wheel)


def test_default_wheel_is_independent_of_working_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    assert MODULE._default_wheel().parent == MODULE.VENDOR_DIR


# A long extra (82 characters) and a multi-line license with an empty line, as
# in the upstream 9c7f100 wheel. Re-serializing METADATA wrapped the extra at
# its ";", and pip refused the wheel: "Expected a marker variable or quoted
# string".
LONG_EXTRA = 'metaharmonizer[eval,llm-anthropic,llm-gemini,llm-openai,notebook]; extra == "all"'
UPSTREAM_METADATA = (
    "Metadata-Version: 2.4\n"
    "Name: example\n"
    "Version: 1.0.0\n"
    "License: MIT License\n"
    "        \n"
    "        Copyright (c) 2026 Example Authors\n"
    "Requires-Dist: pandas>=2.0\n"
    "Requires-Dist: nltk>=3.8\n"
    f"Requires-Dist: {LONG_EXTRA}\n"
    "Provides-Extra: all\n"
    "\n"
    "# Example\n"
    "\n"
    "Requires-Dist: nltk in the description is prose, not metadata.\n"
)


def _metadata_wheel(tmp_path: Path, metadata: bytes) -> Path:
    wheel = tmp_path / "example-1.0.0-py3-none-any.whl"
    metadata_name = "example-1.0.0.dist-info/METADATA"
    record_name = "example-1.0.0.dist-info/RECORD"
    with ZipFile(wheel, "w") as archive:
        archive.writestr("example/__init__.py", "VALUE = 1\n")
        archive.writestr(metadata_name, metadata)
        archive.writestr(
            record_name,
            f"{metadata_name},sha256=old,{len(metadata)}\n{record_name},,\n",
        )
    return wheel


def _stripped(tmp_path: Path, metadata: bytes) -> bytes:
    wheel = _metadata_wheel(tmp_path, metadata)
    assert MODULE.strip_unused_dependency(wheel)
    MODULE.verify_dependency_absent(wheel)
    with ZipFile(wheel) as archive:
        return archive.read("example-1.0.0.dist-info/METADATA")


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_strip_removes_only_the_dependency_line(tmp_path: Path, monkeypatch, newline: str) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_SOURCE_ROOTS", ())
    original = UPSTREAM_METADATA.replace("\n", newline).encode()

    stripped = _stripped(tmp_path, original)

    assert stripped == original.replace(f"Requires-Dist: nltk>=3.8{newline}".encode(), b"")
    requirements = MODULE._metadata_message(stripped).get_all("Requires-Dist")
    assert requirements == ["pandas>=2.0", LONG_EXTRA]
    for requirement in requirements:
        Requirement(requirement)  # what pip parses; a wrapped marker raises here


def test_strip_removes_a_wrapped_dependency_line(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "PROJECT_SOURCE_ROOTS", ())
    original = UPSTREAM_METADATA.replace(
        "Requires-Dist: nltk>=3.8\n",
        'Requires-Dist: nltk>=3.8;\n python_version >= "3.10"\n',
    ).encode()

    stripped = _stripped(tmp_path, original)

    assert b"nltk>=3.8" not in stripped.split(b"\n\n", 1)[0]
    assert stripped.endswith(b"Requires-Dist: nltk in the description is prose, not metadata.\n")
