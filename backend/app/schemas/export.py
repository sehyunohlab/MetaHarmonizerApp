"""API schemas for export previews (harmonized CSV vs. original upload)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ChangeReason = Literal["ontology", "escaped", "other"]


class ExportPreviewSummary(BaseModel):
    rows: int
    columns_before: int
    columns_after: int
    renamed: int
    matched: int
    kept: int
    dropped: int
    pending: int  # exported columns whose mapping is still awaiting review
    changed_cells: int
    changed_rows: int
    compared_cells: int  # rows × exported columns


class ExportValueChange(BaseModel):
    before: str
    after: str
    count: int
    reason: ChangeReason


class ExportColumnChange(BaseModel):
    source: str
    target: str | None
    action: Literal["renamed", "matched", "kept", "dropped"]
    mapping_status: Literal["accepted", "pending", "rejected", "unmapped"]
    drop_reason: Literal["no_target", "duplicate_target", "name_conflict"] | None
    conflicts_with: str | None  # dropped: the source column that took its export name
    changed_cells: int
    value_changes: list[ExportValueChange]
    more_value_changes: int  # distinct changes not listed in value_changes


class ExportCellChange(BaseModel):
    column: int  # index into ExportPreviewRows.columns
    before: str
    reason: ChangeReason


class ExportPreviewRow(BaseModel):
    line: int  # 1-based data row number
    values: list[str]  # exported values, aligned with ExportPreviewRows.columns
    changes: list[ExportCellChange]


class ExportPreviewRows(BaseModel):
    total: int  # rows matching the filter
    offset: int
    limit: int
    columns: list[str]
    items: list[ExportPreviewRow]


class ExportPreview(BaseModel):
    study_id: str
    summary: ExportPreviewSummary
    columns: list[ExportColumnChange]
    rows: ExportPreviewRows
