"""API schemas for studies."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class StudyOut(BaseModel):
    id: str
    name: str
    upload_date: str
    status: str
    file_path: Optional[str] = None
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    # Reproducibility pins: the schema version + ontology KB snapshot the study
    # was harmonized against.
    schema_version_id: Optional[int] = None
    ontology_snapshot_id: Optional[int] = None
