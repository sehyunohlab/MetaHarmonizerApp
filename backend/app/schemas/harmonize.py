"""API schemas for submitting a harmonization job."""

from __future__ import annotations

from pydantic import BaseModel


class HarmonizeAccepted(BaseModel):
    """Returned by the async harmonize endpoint — work runs in the background;
    the client follows progress over the job WebSocket."""

    job_id: int
    study_id: str
    study_name: str
    status: str  # "queued"
    row_count: int
    column_count: int
    message: str
