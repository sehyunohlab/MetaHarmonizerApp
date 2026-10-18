"""Selectable target schemas for the schema mapper.

Discovers the SchemaRegistry artifacts installed under
``backend/data/schema/registry/<name>/`` — each carrying a
``<key>_target_attrs.csv`` (+ optional alias / allowed-values siblings) — so a
curator can choose which target schema an upload is mapped against (GDC,
cBioPortal, cMD, …).

Reads CSV/JSON only — it does **not** import ``metaharmonizer`` — so routers can
list the choices without paying the engine's torch import cost.
"""

from __future__ import annotations

import csv
import io
import logging
import os
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_REGISTRY_DIR = Path(__file__).resolve().parents[2] / "data" / "schema" / "registry"

# Friendly labels + a stable display order for the known schemas.
_LABELS: dict[str, str] = {
    "omicsmlprepo_cbio": "cBioPortal curated (lab vocabulary)",
    "cbioportal": "cBioPortal clinical attributes",
    "gdc": "GDC — cancer (CPTAC)",
    "cmd": "curatedMetagenomicData",
}
_ORDER = ["omicsmlprepo_cbio", "cbioportal", "gdc", "cmd"]
# The lab's curated cBioPortal vocabulary (OmicsMLRepoData's data dictionary,
# refreshed by scripts/refresh_lab_dictionary.py): the fields of the lab's
# harmonized metadata and of its SchemaMapper ground truth.
_DEFAULT = "omicsmlprepo_cbio"

_SUFFIX = "_target_attrs.csv"


def _field_count(path: Path) -> int:
    try:
        with open(path, encoding="utf-8") as fh:
            return max(0, sum(1 for _ in fh) - 1)  # minus header
    except Exception:  # noqa: BLE001
        return 0


@lru_cache(maxsize=1)
def _discover() -> dict[str, dict]:
    found: dict[str, dict] = {}
    if not _REGISTRY_DIR.is_dir():
        return found
    for sub in sorted(_REGISTRY_DIR.iterdir()):
        if not sub.is_dir():
            continue
        target = next(iter(sorted(sub.glob(f"*{_SUFFIX}"))), None)
        if not target:
            continue
        key = target.name[: -len(_SUFFIX)]
        alias = next(iter(sorted(sub.glob("*_target_attrs_alias*.csv"))), None)
        values = next(iter(sorted(sub.glob("*_target_attrs_allowed_values.json"))), None)
        dictionary = sub / f"{key}_schema.csv"
        found[key] = {
            "key": key,
            "label": _LABELS.get(key, key),
            "fields": _field_count(target),
            "target_schema_path": str(target),
            "alias_dict_path": str(alias) if alias else None,
            "value_dict_path": str(values) if values else None,
            "dictionary_path": str(dictionary) if dictionary.is_file() else None,
        }
    return found


# Separators the lab's published curated data uses for a field its data
# dictionary gives none: in its cBioPortal release (OmicsMLRepo, Zenodo
# record 16458151), ancestry joins values with ";" in 2,167 cells and
# ancestry_details in 20, never with "<;>".
_RELEASE_SEPARATORS: dict[str, dict[str, str]] = {
    "omicsmlprepo_cbio": {"ancestry": ";", "ancestry_details": ";"},
}


@lru_cache(maxsize=16)
def field_separators(key: str | None) -> dict[str, str]:
    """``{field name (lower case): separator}`` for the fields of target schema
    ``key`` whose values the lab joins with a given separator: its data
    dictionary's ``delimiter`` column (``<;>`` or ``;``). Empty for a schema
    without a dictionary, such as GDC."""
    schema = _discover().get(key or "")
    found = dict(_RELEASE_SEPARATORS.get(key or "", {}))
    path = schema and schema.get("dictionary_path")
    if not path:
        return found
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            text = fh.read()
        # The lab writes its dictionaries with R: comma-separated, or
        # space-separated with quotes (write.table).
        first = text.split("\n", 1)[0]
        rows = csv.DictReader(io.StringIO(text), delimiter="," if first.count(",") > first.count(" ") else " ")
        for row in rows:
            name, separator = (row.get("col.name") or "").strip(), (row.get("delimiter") or "").strip()
            if name and separator and separator != "NA":
                found[name.lower()] = separator
    except Exception:  # noqa: BLE001 — a missing dictionary means the default separator
        logger.warning("could not read the data dictionary of %s", key, exc_info=True)
    return found


def available_schemas() -> list[dict]:
    """Public list (key, label, fields) for the picker — no filesystem paths.
    The default schema comes first."""
    found = _discover()
    first = default_key()
    order = [first, *(k for k in _ORDER if k != first)]
    ordered = [found[k] for k in order if k in found]
    ordered += [v for k, v in found.items() if k not in order]
    return [{"key": s["key"], "label": s["label"], "fields": s["fields"]} for s in ordered]


def resolve(key: str | None) -> dict | None:
    """Full record (incl. paths) for a schema key, or None."""
    if not key:
        return None
    return _discover().get(key)


def default_key() -> str:
    """Default schema when none is chosen: ``ENGINE_TARGET_SCHEMA`` if it names an
    installed schema, else the lab's curated cBioPortal vocabulary, else the
    first available."""
    env = os.getenv("ENGINE_TARGET_SCHEMA")
    if env and env in _discover():
        return env
    if _DEFAULT in _discover():
        return _DEFAULT
    keys = list(_discover())
    return keys[0] if keys else _DEFAULT


def is_valid(key: str | None) -> bool:
    return bool(key) and key in _discover()
