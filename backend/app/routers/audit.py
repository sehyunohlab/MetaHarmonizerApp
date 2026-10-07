"""
Audit query router (U11) — ``GET /api/v1/audit``.

Cursor-paginated, newest-first, with optional study/action/actor filters.
Read-only: the audit log is append-only (enforced by a DB trigger), so there
are no write routes here.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, build_page, clamp_limit, decode_cursor
from app.db.models import User
from app.db.session import get_db
from app.repositories.audit import list_audit_events
from app.routers.deps import require_role
from app.schemas.audit import AuditEventOut

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("", response_model=Page[AuditEventOut])
async def query_audit(
    study_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    actor_id: int | None = Query(default=None),
    since: datetime | None = Query(default=None, description="ISO start of time range (inclusive)."),
    until: datetime | None = Query(default=None, description="ISO end of time range (inclusive)."),
    cursor: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=500),
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Page[AuditEventOut]:
    """List audit events newest-first. ``cursor`` continues a previous page.

    Admin-only: the audit log spans every user's decisions, so it's an
    oversight surface restricted to admins."""
    n = clamp_limit(limit)
    before_id = decode_cursor(cursor)
    rows = await list_audit_events(
        db,
        study_id=study_id,
        action=action,
        actor_id=actor_id,
        since=since,
        until=until,
        before_id=before_id if isinstance(before_id, int) else None,
        limit=n,
    )
    items = [AuditEventOut.model_validate(r) for r in rows]
    return build_page(items, limit=n, cursor_of=lambda e: e.id)
