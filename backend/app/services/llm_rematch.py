"""Stage 4 — on-demand LLM rematch for a single raw column."""

from __future__ import annotations

from typing import Any


class LLMMatchUnavailable(RuntimeError):
    """The LLM stage could not run (provider error, missing key, …)."""


def llm_suggestions(file_path: str, raw_column: str) -> list[dict[str, Any]]:
    """Suggested target fields for ``raw_column`` of the stored study file.

    Raises ``LLMMatchUnavailable`` when reading the file or the LLM call fails
    with a ``RuntimeError``; errors while obtaining the engine propagate as-is.
    """
    from app.core.storage import get_storage
    from app.engine_adapter import get_engine

    engine = get_engine()
    try:
        with get_storage().local(file_path) as local_csv:
            return engine.llm_match(csv_path=str(local_csv), raw_column=raw_column)
    except RuntimeError as exc:
        raise LLMMatchUnavailable(str(exc)) from exc
