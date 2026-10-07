"""Architecture guard: the backend layering documented in backend/STRUCTURE.md.

Every import in ``app/`` — including function-level (lazy) imports — must follow
the allowed dependency direction between top-level packages.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# App packages each layer may import (its own package is always allowed).
# app/main.py is the composition root and may import anything.
ALLOWED: dict[str, set[str]] = {
    "core": set(),
    "db": {"core"},
    "schemas": {"core"},
    "engine_adapter": {"core"},
    "repositories": {"core", "db"},
    "services": {"core", "db", "repositories", "schemas", "engine_adapter"},
    "workers": {"core", "db", "repositories", "schemas", "services", "engine_adapter"},
    "routers": {"core", "db", "repositories", "schemas", "services", "workers"},
}

# Deliberate, documented exceptions: (file relative to app/, imported module).
EXCEPTIONS: set[tuple[str, str]] = {
    # Dictionary fallback for value mapping; see "Why isn't ONTOLOGY_MAP behind
    # the adapter?" in app/engine_adapter/README.md.
    ("engine_adapter/metaharmonizer_impl.py", "app.services.harmonizer"),
}


def _imported_app_modules(path: Path) -> list[str]:
    package = path.relative_to(APP_DIR.parent).with_suffix("").parts[:-1]
    modules: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = ".".join(package[: len(package) - node.level + 1])
                target = f"{base}.{node.module}" if node.module else base
            else:
                target = node.module or ""
            if node.module is None or target == "app":
                modules.extend(f"{target}.{alias.name}" for alias in node.names)
            else:
                modules.append(target)
    return [m for m in modules if m == "app" or m.startswith("app.")]


def _layer_of(module: str) -> str:
    parts = module.split(".")
    return parts[1] if len(parts) > 1 else "app"


def test_layer_dependencies_follow_structure_md() -> None:
    violations: list[str] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        rel = path.relative_to(APP_DIR)
        if len(rel.parts) == 1:
            continue  # app/main.py + app/__init__.py: the composition root
        layer = rel.parts[0]
        assert layer in ALLOWED, (
            f"Unknown package app/{layer}/ — add it to ALLOWED and backend/STRUCTURE.md"
        )
        for module in _imported_app_modules(path):
            target = _layer_of(module)
            if target == layer or target in ALLOWED[layer]:
                continue
            if (rel.as_posix(), module) in EXCEPTIONS:
                continue
            violations.append(f"app/{rel.as_posix()} imports {module} ({layer} -> {target})")
    assert not violations, "Layering violations:\n" + "\n".join(violations)


def test_documented_exceptions_are_still_needed() -> None:
    for rel, module in sorted(EXCEPTIONS):
        assert module in _imported_app_modules(APP_DIR / rel), (
            f"Stale layering exception (remove it): app/{rel} -> {module}"
        )
