"""Export preview endpoint: harmonized CSV vs. original upload (owner-scoped).

Skipped if Postgres is down.
"""

from __future__ import annotations

import csv
import io
import uuid
from contextlib import contextmanager

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.core.settings as settings_mod
import app.db.session as db_session
from app.db.models import Mapping, OntologyMapping, Study, User

from _authflow import register_and_login

pytestmark = pytest.mark.asyncio

UPLOAD = (
    "sample,gender,age,notes\n"
    "S1,F,51,=cmd\n"
    "S2,M,,fine\n"
    "S3,F,7,NA\n"
)


class _FakeStorage:
    def __init__(self, files):
        self.files = files

    def exists(self, key):
        return key in self.files

    @contextmanager
    def local(self, key):
        yield self.files[key]


@pytest.fixture
async def env(database_url, monkeypatch, tmp_path):
    engine = create_async_engine(database_url, poolclass=sa.pool.NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
    except Exception:
        await engine.dispose()
        pytest.skip("dev Postgres not reachable")

    db_session.engine = engine
    db_session.SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    import app.core.redis as redis_mod

    redis_mod._client = None

    domain = f"t{uuid.uuid4().hex[:8]}.example.com"
    monkeypatch.setattr(settings_mod.settings, "allowed_email_domains", domain, raising=False)
    monkeypatch.setattr(settings_mod.settings, "hibp_check", False, raising=False)
    monkeypatch.setattr(settings_mod.settings, "auth_mode", "jwt", raising=False)

    upload = tmp_path / "upload.csv"
    upload.write_text(UPLOAD, encoding="utf-8")
    import app.routers.export as export_mod

    monkeypatch.setattr(export_mod, "get_storage", lambda: _FakeStorage({"upload.csv": upload}))

    from fastapi import FastAPI

    from app.core.middleware import install_observability
    from app.routers import auth, export

    app = FastAPI()
    install_observability(app)
    app.include_router(auth.router)
    app.include_router(export.router)

    def make_client() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    seeded: list[str] = []
    yield make_client, domain, seeded

    async with db_session.SessionLocal() as s:
        await s.execute(sa.delete(Study).where(Study.id.in_(seeded)))
        await s.execute(sa.delete(User).where(User.email.like(f"%@{domain}")))
        await s.commit()
    await engine.dispose()
    redis_mod._client = None


async def _seed_study(owner_id: int, seeded: list[str]) -> str:
    sid = f"prev_{uuid.uuid4().hex[:8]}"
    seeded.append(sid)
    async with db_session.SessionLocal() as s:
        s.add(Study(id=sid, name="preview", status="review", file_path="upload.csv", owner_id=owner_id))
        await s.flush()
        s.add_all([
            Mapping(study_id=sid, raw_column="sample", matched_field="sample_id",
                    confidence_score=1.0, status="accepted"),
            Mapping(study_id=sid, raw_column="gender", matched_field="sex",
                    confidence_score=0.95, status="accepted"),
            Mapping(study_id=sid, raw_column="age", matched_field="age_years",
                    confidence_score=0.7, status="pending"),
            Mapping(study_id=sid, raw_column="notes", matched_field="comment",
                    confidence_score=0.6, status="accepted"),
            OntologyMapping(study_id=sid, field_name="sex", raw_value="F",
                            ontology_term="Female", status="accepted"),
            OntologyMapping(study_id=sid, field_name="sex", raw_value="M",
                            ontology_term="Male", status="pending"),
        ])
        await s.commit()
    return sid


async def _exported(sid: str) -> bool:
    async with db_session.SessionLocal() as s:
        return await s.scalar(sa.select(Study.exported).where(Study.id == sid))


async def test_preview_matches_the_download_and_does_not_mark_export(env):
    make_client, domain, seeded = env
    async with make_client() as c:
        await register_and_login(c, f"admin@{domain}")  # bootstrap admin
        owner = await register_and_login(c, f"owner@{domain}")
        headers = {"Authorization": f"Bearer {owner['access_token']}"}
        sid = await _seed_study(owner["user"]["id"], seeded)

        r = await c.get(f"/api/v1/export/{sid}/preview", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert await _exported(sid) is False  # previewing is not exporting

        assert body["summary"] == {
            "rows": 3,
            "columns_before": 4,
            "columns_after": 4,
            "renamed": 4,
            "matched": 0,
            "kept": 0,
            "dropped": 0,
            "pending": 1,
            "changed_cells": 3,
            "changed_rows": 2,
            "compared_cells": 12,
        }
        gender = next(col for col in body["columns"] if col["source"] == "gender")
        assert gender["target"] == "sex"
        assert gender["value_changes"] == [
            {"before": "F", "after": "Female", "count": 2, "reason": "ontology"}
        ]
        rows = body["rows"]
        assert rows["columns"] == ["sample_id", "sex", "age_years", "comment"]
        assert [item["line"] for item in rows["items"]] == [1, 2, 3]  # every row by default
        assert rows["items"][1]["changes"] == []
        changed = (
            await c.get(
                f"/api/v1/export/{sid}/preview", params={"changed_only": "true"}, headers=headers
            )
        ).json()["rows"]
        assert [item["line"] for item in changed["items"]] == [1, 3]
        assert changed["items"][0]["changes"] == [
            {"column": 1, "before": "F", "reason": "ontology"},
            {"column": 3, "before": "=cmd", "reason": "escaped"},
        ]

        everything = (
            await c.get(
                f"/api/v1/export/{sid}/preview",
                params={"changed_only": "false", "limit": 10},
                headers=headers,
            )
        ).json()["rows"]

        download = await c.get(f"/api/v1/export/{sid}/harmonized", headers=headers)
        assert download.status_code == 200
        exported = list(csv.reader(io.StringIO(download.text)))
        assert exported[0] == everything["columns"]
        assert exported[1:] == [item["values"] for item in everything["items"]]
        # Original cell text survives: no "51.0", "NA" kept, blank stays blank.
        assert exported[1:] == [
            ["S1", "Female", "51", "'=cmd"],
            ["S2", "M", "", "fine"],
            ["S3", "Female", "7", "NA"],
        ]
        assert await _exported(sid) is True


async def test_preview_is_owner_scoped(env):
    make_client, domain, seeded = env
    async with make_client() as c:
        await register_and_login(c, f"admin@{domain}")
        owner = await register_and_login(c, f"owner@{domain}")
        intruder = await register_and_login(c, f"other@{domain}")
        sid = await _seed_study(owner["user"]["id"], seeded)

        other = {"Authorization": f"Bearer {intruder['access_token']}"}
        assert (await c.get(f"/api/v1/export/{sid}/preview", headers=other)).status_code == 404
        assert (await c.get(f"/api/v1/export/{sid}/preview")).status_code == 401


async def test_preview_validates_paging_and_column(env):
    make_client, domain, seeded = env
    async with make_client() as c:
        await register_and_login(c, f"admin@{domain}")
        owner = await register_and_login(c, f"owner@{domain}")
        headers = {"Authorization": f"Bearer {owner['access_token']}"}
        sid = await _seed_study(owner["user"]["id"], seeded)
        url = f"/api/v1/export/{sid}/preview"

        assert (await c.get(url, params={"limit": 500}, headers=headers)).status_code == 422
        assert (await c.get(url, params={"offset": -1}, headers=headers)).status_code == 422
        unknown = await c.get(url, params={"column": "gender"}, headers=headers)
        assert unknown.status_code == 422  # filters use export column names

        focused = (
            await c.get(url, params={"column": "comment", "changed_only": "true"}, headers=headers)
        ).json()
        assert focused["rows"]["total"] == 1
        assert focused["rows"]["items"][0]["line"] == 1

        beyond = (await c.get(url, params={"offset": 10}, headers=headers)).json()
        assert beyond["rows"]["total"] == 3 and beyond["rows"]["items"] == []
