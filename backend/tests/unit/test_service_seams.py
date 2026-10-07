"""Service seams that keep routers off the engine adapter (see STRUCTURE.md)."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

import app.core.storage as storage_mod
import app.engine_adapter as engine_adapter
from app.engine_adapter import schema_dicts
from app.services import llm_rematch, schema_catalog


class _FakeStorage:
    def __init__(self) -> None:
        self.keys: list[str] = []

    @contextmanager
    def local(self, key: str):
        self.keys.append(key)
        yield Path("local") / key


class _FakeEngine:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def llm_match(self, csv_path: str, raw_column: str) -> list[dict]:
        self.calls.append((csv_path, raw_column))
        if self.error:
            raise self.error
        return [{"field": "sex", "score": 0.9}]


def test_llm_suggestions_read_the_stored_study_file(monkeypatch) -> None:
    storage, engine = _FakeStorage(), _FakeEngine()
    monkeypatch.setattr(storage_mod, "get_storage", lambda: storage)
    monkeypatch.setattr(engine_adapter, "get_engine", lambda: engine)

    assert llm_rematch.llm_suggestions("study.csv", "SEX") == [{"field": "sex", "score": 0.9}]
    assert storage.keys == ["study.csv"]
    assert engine.calls == [(str(Path("local") / "study.csv"), "SEX")]


def test_llm_runtime_failure_is_reported_as_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(storage_mod, "get_storage", _FakeStorage)
    monkeypatch.setattr(
        engine_adapter, "get_engine", lambda: _FakeEngine(RuntimeError("quota exceeded"))
    )

    with pytest.raises(llm_rematch.LLMMatchUnavailable, match="quota exceeded"):
        llm_rematch.llm_suggestions("study.csv", "SEX")


def test_engine_construction_errors_propagate_unchanged(monkeypatch) -> None:
    def broken_engine():
        raise RuntimeError("engine wheel missing")

    monkeypatch.setattr(storage_mod, "get_storage", _FakeStorage)
    monkeypatch.setattr(engine_adapter, "get_engine", broken_engine)

    with pytest.raises(RuntimeError, match="engine wheel missing") as exc_info:
        llm_rematch.llm_suggestions("study.csv", "SEX")
    assert not isinstance(exc_info.value, llm_rematch.LLMMatchUnavailable)


def test_duplicate_alias_maps_to_service_error(monkeypatch) -> None:
    def add_alias(source: str, field_name: str) -> None:
        raise schema_dicts.AliasExists(f"'{source}' already maps to '{field_name}'.")

    monkeypatch.setattr(schema_dicts, "add_alias", add_alias)

    with pytest.raises(schema_catalog.AliasExistsError, match="already maps to 'sex'"):
        schema_catalog.add_alias("gender", "sex")


def test_invalid_alias_value_error_propagates(monkeypatch) -> None:
    def add_alias(source: str, field_name: str) -> None:
        raise ValueError("unknown field")

    monkeypatch.setattr(schema_dicts, "add_alias", add_alias)

    with pytest.raises(ValueError, match="unknown field"):
        schema_catalog.add_alias("gender", "nope")
