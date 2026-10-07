"""API schemas for value → ontology-term mappings and term search."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class OntologyMappingOut(BaseModel):
    id: int
    study_id: str
    field_name: str
    raw_value: str
    ontology_term: Optional[str] = None
    ontology_id: Optional[str] = None
    confidence_score: Optional[float] = None
    status: str = "pending"
    curator_term: Optional[str] = None
    curator_id: Optional[str] = None
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None


class OntologyEditRequest(BaseModel):
    new_term: str
    new_id: Optional[str] = None
    note: str = ""
    remember: bool = True  # ADR-0002: remember for the curator's future studies


class OntologySearchResult(BaseModel):
    term: str
    ontology_id: str
    ontology: str
    score: float
