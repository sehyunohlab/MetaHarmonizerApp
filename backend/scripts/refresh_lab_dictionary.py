"""Refresh the lab's cBioPortal vocabulary from its data dictionary.

The default target schema, ``data/schema/registry/omicsmlrepo_cbio``, is the
lab's curated cBioPortal vocabulary: OmicsMLRepoData's
``inst/extdata/cBioPortal_data_dictionary.csv``. This downloads that file and
regenerates what the schema mapper reads from it:

- ``omicsmlprepo_cbio_schema.csv``: the dictionary, byte for byte, with its
  commit in ``omicsmlprepo_cbio_dictionary.meta.json``;
- ``omicsmlprepo_cbio_target_attrs.csv``: ``field_name,is_numeric_field``
  (numeric when ``col.class`` is ``numeric``);
- ``omicsmlprepo_cbio_target_attrs_allowed_values.json``: each field's listed
  ``allowedvalues`` (not regular expressions), then the values the engine's own
  cBioPortal preset lists for it (``cbio_target_attrs_allowed_values.json`` in
  the vendored wheel, the lab's curated values).

``--rename old=new`` renames a field in the alias dictionary and the LinkML
schema when the lab renames one. Alias rows for fields the dictionary no longer
has, and fields without any alias, are reported.

Usage (from backend/)::

    python -m scripts.refresh_lab_dictionary [--ref <branch|commit>] [--rename old=new ...]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REGISTRY = BACKEND / "data" / "schema" / "registry" / "omicsmlrepo_cbio"
PREFIX = "omicsmlprepo_cbio"
REPO = "waldronlab/OmicsMLRepoData"
DICTIONARY = "inst/extdata/cBioPortal_data_dictionary.csv"
ENGINE_VALUES = "metaharmonizer/_bundled_data/schema/cbio_target_attrs_allowed_values.json"


def _github(path: str, *, raw: bool = False) -> bytes:
    url = f"https://api.github.com/repos/{REPO}" + (f"/{path}" if path else "")
    request = urllib.request.Request(url)
    request.add_header("Accept", "application/vnd.github.raw" if raw else "application/vnd.github+json")
    if os.environ.get("GITHUB_TOKEN"):
        request.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _engine_values() -> dict[str, list[str]]:
    wheel = next((BACKEND / "vendor").glob("metaharmonizer-*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        return json.loads(archive.read(ENGINE_VALUES))


def target_attrs(rows: list[dict[str, str]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["field_name", "is_numeric_field"])
    for row in rows:
        writer.writerow([row["col.name"], "yes" if row["col.class"] == "numeric" else "no"])
    return out.getvalue()


def allowed_values(rows: list[dict[str, str]], engine: dict[str, list[str]]) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for row in rows:
        field, listed = row["col.name"], (row.get("allowedvalues") or "").strip()
        found: list[str] = []
        # A pattern such as [0-9]+ or T[X1-4]N[X0-3]M[X0-1] is not a value list.
        if listed not in ("", "NA") and row.get("corpus.type") != "regexp" and not re.search(r"[\[\]\\+*]", listed):
            found = [v.strip() for v in re.split(r"[|;]", listed) if v.strip()]
        seen = {v.lower() for v in found}
        for value in engine.get(field, []):
            if value.lower() not in seen:
                seen.add(value.lower())
                found.append(value)
        if found:
            values[field] = found
    return values


def _rename_aliases(path: Path, renames: dict[str, str]) -> None:
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames, rows = reader.fieldnames or [], list(reader)
    for row in rows:
        row["field_name"] = renames.get(row["field_name"], row["field_name"])
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ref", help="OmicsMLRepoData branch, tag or commit (default: its default branch)")
    parser.add_argument("--rename", action="append", default=[], metavar="OLD=NEW")
    args = parser.parse_args(argv)
    renames = dict(item.split("=", 1) for item in args.rename)
    ref = args.ref or json.loads(_github(""))["default_branch"]

    data = _github(f"contents/{DICTIONARY}?ref={ref}", raw=True)
    commit = json.loads(_github(f"commits?path={DICTIONARY}&sha={ref}&per_page=1"))[0]
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
    fields = [row["col.name"] for row in rows]

    (REGISTRY / f"{PREFIX}_schema.csv").write_bytes(data)
    (REGISTRY / f"{PREFIX}_dictionary.meta.json").write_text(
        json.dumps(
            {
                "source": f"https://github.com/{REPO}/blob/{commit['sha']}/{DICTIONARY}",
                "commit": commit["sha"],
                "committed": commit["commit"]["committer"]["date"],
                "blob": _blob_sha(data),
                "fields": len(fields),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (REGISTRY / f"{PREFIX}_target_attrs.csv").write_text(target_attrs(rows), encoding="utf-8")
    (REGISTRY / f"{PREFIX}_target_attrs_allowed_values.json").write_text(
        json.dumps(allowed_values(rows, _engine_values()), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    alias_path = next(REGISTRY.glob(f"{PREFIX}_target_attrs_alias*.csv"))
    linkml = REGISTRY / f"{PREFIX}.linkml.yaml"
    if renames:
        _rename_aliases(alias_path, renames)
        text = linkml.read_text(encoding="utf-8")
        for old, new in renames.items():
            text = re.sub(rf"\b{re.escape(old)}\b", new, text)
        linkml.write_text(text, encoding="utf-8")

    with open(alias_path, encoding="utf-8") as handle:
        aliased = {row["field_name"] for row in csv.DictReader(handle)}
    print(f"{len(fields)} fields from {REPO}@{commit['sha'][:7]} ({commit['commit']['committer']['date']})")
    stale = sorted(aliased - set(fields))
    if stale:
        print(f"alias rows for fields the dictionary no longer has: {stale} (use --rename old=new)")
    missing = [f for f in fields if f not in aliased]
    if missing:
        print(f"fields without aliases: {missing}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
