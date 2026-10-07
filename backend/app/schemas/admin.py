"""API schemas for admin-only endpoints (alias dictionary, curation KB promotion)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class AliasEntry(BaseModel):
    source: str
    field_name: str


# Two-layer curation KB promotion (ADR-0002, Q10 two-stage approval).
class PromoteRequest(BaseModel):
    kind: str          # 'schema' | 'ontology'
    source_key: str
    decision: str      # 'accept' | 'reject'
    target_field: str | None = None
    target_term: str | None = None
    target_id: str | None = None


class ReviewLearnedRequest(BaseModel):
    action: Literal["promote", "dismiss"]
    candidates: list[PromoteRequest]


class UnpromoteLearnedRequest(BaseModel):
    ids: list[int]
