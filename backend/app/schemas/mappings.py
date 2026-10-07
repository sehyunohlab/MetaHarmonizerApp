"""API schemas for schema (column → field) mappings and curator review."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AlternativeMatch(BaseModel):
    field: str
    score: float
    method: Optional[str] = None


class MappingOut(BaseModel):
    id: int
    study_id: str
    raw_column: str
    matched_field: Optional[str] = None
    confidence_score: Optional[float] = None
    stage: Optional[str] = None
    method: Optional[str] = None
    alternatives: list[AlternativeMatch] = []
    status: str = "pending"
    curator_field: Optional[str] = None
    curator_note: Optional[str] = None
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None


class MappingEditRequest(BaseModel):
    new_field: str
    note: str = ""


class BatchUpdateRequest(BaseModel):
    mapping_ids: list[int]
    action: str = Field(..., pattern="^(accepted|rejected)$")
    remember: bool = True


class BatchUpdateResponse(BaseModel):
    updated: int
    action: str
