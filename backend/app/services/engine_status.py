"""Runtime readiness of the engine's knowledge-base assets.

Routers, health probes, and the readiness middleware (wired in app/main.py) ask
this service instead of importing the engine adapter directly — only services
and workers call ``app.engine_adapter``. Imports stay lazy so probing readiness
never loads the engine stack.
"""

from __future__ import annotations


def runtime_engine_required() -> bool:
    """True when the configured engine needs the on-disk ontology KB assets."""
    from app.engine_adapter.kb_assets import runtime_engine_required as _required

    return _required()


def runtime_asset_issues() -> list[str]:
    """Missing or invalid KB assets the ontology engine needs (empty when ready)."""
    from app.engine_adapter._ontology import runtime_asset_issues as _issues

    return _issues()


def runtime_asset_error() -> str | None:
    """User-facing reason ontology harmonization can't run now, else ``None``."""
    from app.engine_adapter._ontology import runtime_asset_error as _error

    return _error()
