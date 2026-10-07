"""API schemas for study quality / analytics metrics."""

from __future__ import annotations

from pydantic import BaseModel


class StageBreakdown(BaseModel):
    stage: str
    count: int
    percentage: float


class ConfidenceBucket(BaseModel):
    bucket: str
    min_val: float
    max_val: float
    count: int


class QualityMetrics(BaseModel):
    study_id: str
    total_columns: int
    mapped_columns: int
    unmapped_columns: int
    avg_confidence: float
    auto_accepted: int
    pending_review: int
    rejected: int
    new_field_suggestions: int
    stage_breakdown: list[StageBreakdown]
    confidence_distribution: list[ConfidenceBucket]
