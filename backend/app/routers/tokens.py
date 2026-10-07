"""
Personal API tokens (Sprint 3, slice 4).

A signed-in user can mint long-lived tokens for CLI / programmatic access.
The plaintext is shown exactly once; afterwards only the hash is stored. A
token can be used in place of an access JWT via ``Authorization: Bearer mh_...``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_api_token
from app.db.models import User
from app.db.session import get_db
from app.repositories import api_tokens as api_tokens_repo
from app.routers.deps import current_user
from app.schemas.auth import ApiTokenCreate, ApiTokenCreated, ApiTokenInfo

router = APIRouter(prefix="/api/v1/tokens", tags=["tokens"])


@router.post("", response_model=ApiTokenCreated, status_code=201)
async def create_token(
    body: ApiTokenCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiTokenCreated:
    plain, token_hash = generate_api_token()
    record = await api_tokens_repo.create_token(
        db, user_id=user.id, token_hash=token_hash, scope=body.scope
    )
    await db.commit()
    await db.refresh(record)
    out = ApiTokenCreated(
        **ApiTokenInfo.model_validate(record).model_dump(),
        token=plain,  # shown once
    )
    return out


@router.get("", response_model=list[ApiTokenInfo])
async def list_tokens(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApiTokenInfo]:
    rows = await api_tokens_repo.list_for_user(db, user.id)
    return [ApiTokenInfo.model_validate(t) for t in rows]


@router.delete("/{token_id}", status_code=204)
async def revoke_token(
    token_id: int,
    response: Response,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await api_tokens_repo.revoke(db, user_id=user.id, token_id=token_id)
    await db.commit()
    response.status_code = 204
    return response
