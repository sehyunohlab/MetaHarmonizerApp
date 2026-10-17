"""The d7e8f9a0b1c2 data migration rewrites ontology codes that named other concepts.

Runs on a throwaway database: migrate to the revision before it, store rows with
the old codes (as production had: "USA" kept as United States with the United
Kingdom's code), migrate to head, and check each row. A row with its right code
is left alone. Skipped if Postgres is unreachable.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.asyncio

BACKEND = Path(__file__).resolve().parents[2]
DBNAME = "mh_codefix_test"
BEFORE = "c6d7e8f9a0b1"


def _sync_dsn(url: str) -> str:
    return url.replace("+asyncpg", "")


async def _admin_exec(base_url: str, sql: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(_sync_dsn(base_url).rsplit("/", 1)[0] + "/postgres")
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND),
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
    )


async def test_stored_rows_get_the_right_codes(database_url):
    import asyncpg

    try:
        conn = await asyncpg.connect(_sync_dsn(database_url), timeout=3)
        await conn.close()
    except Exception:
        pytest.skip("dev Postgres not reachable (run scripts/dev_services.ps1 start)")

    throwaway = f"{database_url.rsplit('/', 1)[0]}/{DBNAME}"
    await _admin_exec(database_url, f'DROP DATABASE IF EXISTS "{DBNAME}"')
    await _admin_exec(database_url, f'CREATE DATABASE "{DBNAME}"')
    try:
        up = _alembic(throwaway, "upgrade", BEFORE)
        assert up.returncode == 0, up.stderr

        conn = await asyncpg.connect(_sync_dsn(throwaway))
        try:
            await conn.execute("INSERT INTO studies (id, name, status) VALUES ('s1', 's1', 'review')")
            rows = [
                # (field, raw, ontology term, ontology id, curator term, curator id)
                ("country", "USA", "United States", "NCIT:C17233", None, None),
                ("country", "GB", "United Kingdom", "NCIT:C17233", None, None),  # already right
                ("country", "JPN", "Japan", "NCIT:C16769", None, None),
                ("primary_site", "UBERON:0001988", "rib 8", "UBERON:0010757", "Bone Marrow Aspirate", "NCIT:C13286"),
                ("cancer_status", "tumor free", "Tumor Status - Free", "NCIT:C17629", None, None),
                ("age_group", "senior", "Senior", "NCIT:C25195", None, None),
                ("ancestry", "white", "European Ancestry", "NCIT:C43851", None, None),
            ]
            for field, raw, term, code, cterm, ccode in rows:
                await conn.execute(
                    "INSERT INTO ontology_mappings (study_id, field_name, raw_value, ontology_term, ontology_id,"
                    " curator_term, curator_id, status) VALUES ('s1', $1, $2, $3, $4, $5, $6, 'accepted')",
                    field, raw, term, code, cterm, ccode,
                )
            await conn.execute(
                "INSERT INTO learned_decisions (scope, kind, source_key, decision, target_term, target_id)"
                " VALUES ('shared', 'ontology', 'primary site::uberon 0001988', 'accept',"
                " 'Bone Marrow Aspirate', 'NCIT:C13286')"
            )
        finally:
            await conn.close()

        up = _alembic(throwaway, "upgrade", "head")
        assert up.returncode == 0, up.stderr

        conn = await asyncpg.connect(_sync_dsn(throwaway))
        try:
            fixed = await conn.fetch(
                "SELECT raw_value, ontology_term, ontology_id, curator_term, curator_id"
                " FROM ontology_mappings ORDER BY id"
            )
            learned = await conn.fetchrow("SELECT target_term, target_id FROM learned_decisions")
        finally:
            await conn.close()
        assert [tuple(r) for r in fixed] == [
            ("USA", "United States", "NCIT:C17234", None, None),
            ("GB", "United Kingdom", "NCIT:C17233", None, None),
            ("JPN", "Japan", "NCIT:C16764", None, None),
            ("UBERON:0001988", "rib 8", "UBERON:0010757", "Bone Marrow Aspirate", "NCIT:C133261"),
            ("tumor free", "Tumor Free", "NCIT:C156848", None, None),
            ("senior", "Senior", None, None, None),
            ("white", "European Ancestry", "HANCESTRO:0005", None, None),
        ]
        assert tuple(learned) == ("Bone Marrow Aspirate", "NCIT:C133261")
    finally:
        await _admin_exec(
            database_url,
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{DBNAME}' AND pid <> pg_backend_pid()",
        )
        await _admin_exec(database_url, f'DROP DATABASE IF EXISTS "{DBNAME}"')
