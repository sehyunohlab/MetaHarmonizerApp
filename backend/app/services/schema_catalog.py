"""Target-schema catalog and column-alias dictionary.

Routers use this service instead of importing ``app.engine_adapter`` directly
(only services and workers call the adapter). Imports stay lazy so listing or
validating schemas never loads the engine stack.
"""

from __future__ import annotations

from typing import Any


class AliasExistsError(Exception):
    """The alias is already present in the built-in or admin layer."""


def available_schemas() -> list[dict]:
    """Installed target schemas (GDC / cBioPortal / cMD / …) for pickers."""
    from app.engine_adapter import _schema_registry

    return _schema_registry.available_schemas()


def default_schema_key() -> str:
    from app.engine_adapter import _schema_registry

    return _schema_registry.default_key()


def is_valid_schema(key: str | None) -> bool:
    from app.engine_adapter import _schema_registry

    return _schema_registry.is_valid(key)


def schema_field_names() -> list[str]:
    """Valid target field names for the active schema."""
    from app.engine_adapter import schema_dicts

    return schema_dicts.schema_field_names()


def alias_entries(query: str | None, limit: int) -> dict[str, Any]:
    """Search the merged alias dictionary (built-in + admin)."""
    from app.engine_adapter import schema_dicts

    return schema_dicts.alias_entries(query, limit)


def add_alias(source: str, field_name: str) -> None:
    """Add one admin alias. Raises ``AliasExistsError`` or ``ValueError``."""
    from app.engine_adapter import schema_dicts

    try:
        schema_dicts.add_alias(source, field_name)
    except schema_dicts.AliasExists as exc:
        raise AliasExistsError(str(exc)) from exc


def remove_alias(source: str, field_name: str) -> bool:
    """Remove one admin alias; False when it isn't in the admin layer."""
    from app.engine_adapter import schema_dicts

    return schema_dicts.remove_alias(source, field_name)


def export_aliases_csv(scope: str) -> str:
    """The alias dictionary as CSV (``merged`` or ``custom``)."""
    from app.engine_adapter import schema_dicts

    return schema_dicts.export_csv(scope)


def invalidate_aliases() -> None:
    """Rebuild the merged alias dict + engine on the next harmonize."""
    from app.engine_adapter import schema_dicts

    schema_dicts._invalidate()
