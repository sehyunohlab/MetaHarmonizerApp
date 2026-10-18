"""Check every code in the fallback ontology tables against its ontology.

Each ``ONTOLOGY_MAP`` term must be the name or a synonym of its code's concept.
Each ``_STATIC_NCIT`` key must be too, or share its code with an
``ONTOLOGY_MAP`` term (abbreviations such as ``crc`` or ``usa``), and so must
each code the ``d7e8f9a0b1c2`` data migration writes. NCIt codes are looked up
in NCI EVS; UBERON and HANCESTRO codes in OLS4.

``--write`` records the names found in ``data/schema/ontology_code_labels.json``,
which ``tests/unit/test_ontology_codes.py`` checks offline, so a code added
without running this script fails the tests.

Usage (from backend/)::

    python -m scripts.verify_ontology_codes            # check, exit 1 on a problem
    python -m scripts.verify_ontology_codes --write    # check and record
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

from app.services.harmonizer import ONTOLOGY_MAP, _STATIC_NCIT

SNAPSHOT = Path(__file__).resolve().parents[1] / "data" / "schema" / "ontology_code_labels.json"
# The data migration that rewrote stored rows to the codes below.
MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "d7e8f9a0b1c2_fix_wrong_ontology_codes.py"
EVS = "https://api-evsrest.nci.nih.gov/api/v1"
OLS = "https://www.ebi.ac.uk/ols4/api"


def curie(code: str) -> str:
    """``C1234`` → ``NCIT:C1234``; a prefixed code is returned as is."""
    return code if ":" in code else f"NCIT:{code}"


def migration_fixes() -> list[tuple[str, str, str | None, str | None]]:
    """The migration's ``(term, wrong code, right code, renamed term)`` rows."""
    spec = importlib.util.spec_from_file_location("fix_wrong_ontology_codes", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FIXES


def used_codes() -> set[str]:
    codes = {curie(code) for code in _STATIC_NCIT.values()}
    codes |= {curie(code) for vmap in ONTOLOGY_MAP.values() for _term, code in vmap.values() if code}
    codes |= {right for _term, _wrong, right, _renamed in migration_fixes() if right}
    return codes


def problems(labels: dict[str, list[str]]) -> list[str]:
    """What is wrong with the tables, given each code's names (lowercase)."""
    mapped = {curie(code) for vmap in ONTOLOGY_MAP.values() for _term, code in vmap.values() if code}
    found: list[str] = []
    for field, vmap in ONTOLOGY_MAP.items():
        for raw, (term, code) in vmap.items():
            if not code:
                continue
            names = labels.get(curie(code))
            if names is None:
                found.append(f"ONTOLOGY_MAP[{field!r}][{raw!r}]: {curie(code)} is not a known concept")
            elif term.lower() not in names:
                found.append(
                    f"ONTOLOGY_MAP[{field!r}][{raw!r}]: {term!r} is not a name of {curie(code)} ({names[0]!r})"
                )
    for key, code in _STATIC_NCIT.items():
        names = labels.get(curie(code))
        if names is None:
            found.append(f"_STATIC_NCIT[{key!r}]: {curie(code)} is not a known concept")
        elif key not in names and curie(code) not in mapped:
            found.append(f"_STATIC_NCIT[{key!r}]: not a name of {curie(code)} ({names[0]!r})")
    for term, _wrong, right, renamed in migration_fixes():
        if right is None:
            continue
        names = labels.get(right)
        written = renamed or term
        if names is None or written.lower() not in names:
            found.append(f"migration FIXES: {written!r} is not a name of {right}")
    return found


def _get(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def _names(name: str, synonyms: list[str]) -> list[str]:
    rest = sorted({s.strip().lower() for s in synonyms if s and s.strip()} - {name.lower()})
    return [name.lower(), *rest]


def fetch(codes: set[str]) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Each code's names, first its preferred name, and the ontology versions."""
    labels: dict[str, list[str]] = {}
    ncit = sorted(c.split(":", 1)[1] for c in codes if c.startswith("NCIT:"))
    for i in range(0, len(ncit), 50):
        batch = _get(f"{EVS}/concept/ncit?include=synonyms&list={','.join(ncit[i:i + 50])}")
        for concept in batch:
            if concept.get("active") is False:
                continue  # a retired concept is reported as unknown
            labels[f"NCIT:{concept['code']}"] = _names(
                concept["name"], [s.get("name", "") for s in concept.get("synonyms", [])]
            )
    versions = {"ncit": _get(f"{EVS}/metadata/terminologies?latest=true&terminology=ncit")[0]["version"]}
    for code in sorted(c for c in codes if not c.startswith("NCIT:")):
        prefix, local = code.split(":", 1)
        ontology = prefix.lower()
        iri = urllib.parse.quote(urllib.parse.quote(f"http://purl.obolibrary.org/obo/{prefix}_{local}", safe=""), safe="")
        try:
            term = _get(f"{OLS}/ontologies/{ontology}/terms/{iri}")
        except urllib.error.HTTPError:
            continue
        if term.get("is_obsolete"):
            continue
        labels[code] = _names(term["label"], term.get("synonyms") or [])
        if ontology not in versions:
            config = _get(f"{OLS}/ontologies/{ontology}")["config"]
            versions[ontology] = config.get("version") or config.get("versionIri") or ""
    return labels, versions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help=f"record the names in {SNAPSHOT.name}")
    args = parser.parse_args(argv)

    labels, versions = fetch(used_codes())
    found = problems(labels)
    for problem in found:
        print(problem)
    print(f"{len(labels)} codes checked against {versions}; {len(found)} problem(s)")
    if args.write and not found:
        SNAPSHOT.write_text(
            json.dumps(
                {"checked": date.today().isoformat(), "versions": versions, "labels": dict(sorted(labels.items()))},
                indent=1,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {SNAPSHOT}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
