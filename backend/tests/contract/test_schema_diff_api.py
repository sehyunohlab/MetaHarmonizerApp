"""Schema-diff endpoint test (G6 layer A) — real admin route + Postgres.

Seeds two schema versions pointing at temp CSVs and diffs them through
GET /api/v1/admin/schema-versions/diff. Skipped if Postgres is down or pandas
is unavailable (the endpoint parses CSVs with pandas).
"""

from __future__ import annotations

import uuid

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytest.importorskip("pandas")
import pandas as pd  # noqa: E402

import app.db.session as db_session  # noqa: E402
from app.db.models import SchemaVersion, User  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def diff_app(database_url, tmp_path):
    engine = create_async_engine(database_url, poolclass=sa.pool.NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
    except Exception:
        await engine.dispose()
        pytest.skip("dev Postgres not reachable")

    db_session.engine = engine
    db_session.SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    v1_csv = tmp_path / "v1.csv"
    v2_csv = tmp_path / "v2.csv"
    pd.DataFrame({"sex": ["Male", "Female"], "age": ["1", "2"]}).to_csv(v1_csv, index=False)
    pd.DataFrame({"sex": ["Male", "Female", "Unknown"], "body_site": ["feces", "blood", "skin"]}).to_csv(v2_csv, index=False)

    label_a = f"diffA_{uuid.uuid4().hex[:6]}"
    label_b = f"diffB_{uuid.uuid4().hex[:6]}"
    async with db_session.SessionLocal() as s:
        a = SchemaVersion(label=label_a, source_path=str(v1_csv), is_current=False)
        b = SchemaVersion(label=label_b, source_path=str(v2_csv), is_current=False)
        s.add_all([a, b])
        await s.flush()
        ids = (a.id, b.id)
        await s.commit()

    from fastapi import FastAPI
    from app.routers.deps import current_user
    from app.core.middleware import install_observability
    from app.routers import admin

    app = FastAPI()
    install_observability(app)
    app.include_router(admin.router)
    app.dependency_overrides[current_user] = lambda: User(
        id=1, email="admin@test.local", role="admin"
    )

    yield app, ids

    async with db_session.SessionLocal() as s:
        await s.execute(sa.text("DELETE FROM schema_versions WHERE label IN (:a, :b)"),
                        {"a": label_a, "b": label_b})
        await s.commit()
    await engine.dispose()


def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_schema_diff_endpoint(diff_app):
    app, (from_id, to_id) = diff_app
    async with _client(app) as client:
        r = await client.get(
            "/api/v1/admin/schema-versions/diff",
            params={"from_id": from_id, "to_id": to_id},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [f["field"] for f in body["added_fields"]] == ["body_site"]
    assert [f["field"] for f in body["removed_fields"]] == ["age"]
    changed = {c["field"]: c for c in body["changed_fields"]}
    assert "sex" in changed
    assert changed["sex"]["added_values"] == ["Unknown"]
    assert body["summary"]["added"] == 1
    assert body["summary"]["removed"] == 1
