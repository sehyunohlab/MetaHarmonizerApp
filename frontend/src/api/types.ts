/*  TypeScript types shared across the dashboard.  */

export interface Study {
    id: string;
    name: string;
    upload_date: string;
    status: string;
    file_path?: string;
    row_count?: number;
    column_count?: number;
}

export interface AlternativeMatch {
    field: string;
    score: number;
    method?: string;
}

export interface Mapping {
    id: number;
    study_id: string;
    raw_column: string;
    matched_field: string | null;
    confidence_score: number | null;
    stage: string | null;
    method: string | null;
    alternatives: AlternativeMatch[];
    status: string;
    curator_field: string | null;
    curator_note: string | null;
    reviewed_at: string | null;
    reviewed_by: string | null;
}

export interface OntologyMapping {
    id: number;
    study_id: string;
    field_name: string;
    raw_value: string;
    ontology_term: string | null;
    ontology_id: string | null;
    confidence_score: number | null;
    status: string;
    curator_term: string | null;
    curator_id: string | null;
}

export interface StageBreakdown {
    stage: string;
    count: number;
    percentage: number;
}

export interface ConfidenceBucket {
    bucket: string;
    min_val: number;
    max_val: number;
    count: number;
}

export interface QualityMetrics {
    study_id: string;
    total_columns: number;
    mapped_columns: number;
    unmapped_columns: number;
    avg_confidence: number;
    auto_accepted: number;
    pending_review: number;
    rejected: number;
    new_field_suggestions: number;
    stage_breakdown: StageBreakdown[];
    confidence_distribution: ConfidenceBucket[];
}

/** 202 response from the async harmonize endpoint. */
export interface HarmonizeAccepted {
    job_id: number;
    study_id: string;
    study_name: string;
    status: string; // "queued"
    row_count: number;
    column_count: number;
    message: string;
}

/** A live progress event pushed over the job WebSocket. */
export interface JobProgress {
    study_id: string;
    type: 'progress' | 'complete' | 'failed' | 'cancelled';
    stage: string;
    state: string;
    pct: number;
    message: string;
    result?: { columns: number; rows: number; ontology_values: number };
}

export interface HarmonizationResults {
    study: Study;
    mappings: Mapping[];
    total: number;
}

export interface OntologySearchResult {
    term: string;
    ontology_id: string;
    ontology: string;
    score: number;
}

/* Auth */

export type Role = 'curator' | 'admin';

export interface User {
    id: number;
    email: string;
    name: string | null;
    role: Role;
    is_active: boolean;
    email_verified: boolean;
    approved?: boolean;
    admin_requested?: boolean;
}

export interface TokenResponse {
    access_token: string;
    token_type: string;
    user: User;
}

/** Generic ``{ message }`` envelope (register, verify, reset, …). */
export interface MessageResponse {
    message: string;
}

export interface SessionInfo {
    id: number;
    ip: string | null;
    user_agent: string | null;
    created_at: string;
    last_seen: string | null;
    current: boolean;
}

export interface ApiTokenInfo {
    id: number;
    scope: 'read' | 'write';
    created_at: string;
    revoked_at: string | null;
}

export interface ApiTokenCreated extends ApiTokenInfo {
    token: string;
}

/** Shape of the backend's unified error envelope (spec §6.1). */
export interface ApiErrorBody {
    error: {
        code: string;
        message: string;
        details?: Record<string, unknown>;
        request_id?: string;
    };
}

/* Audit (admin oversight) */

export interface AuditEvent {
    id: number;
    study_id: string | null;
    actor_id: number | null;
    action: string;
    mapping_id: number | null;
    old_value: string | null;
    new_value: string | null;
    details: { curator?: string } | null;
    created_at: string;
}

/** Cursor-paginated list envelope returned by the backend. */
export interface Paginated<T> {
    items: T[];
    next_cursor: string | null;
}

/* Export preview — harmonized CSV vs. original upload */

export type ExportColumnAction = 'renamed' | 'matched' | 'kept' | 'dropped';
export type ExportMappingStatus = 'accepted' | 'pending' | 'rejected' | 'unmapped';
export type ExportDropReason = 'no_target' | 'duplicate_target' | 'name_conflict';
/** Why a cell differs: ontology term rewrite, or spreadsheet formula escape. */
export type ExportChangeReason = 'ontology' | 'escaped' | 'other';

export interface ExportPreviewSummary {
    rows: number;
    columns_before: number;
    columns_after: number;
    renamed: number;
    matched: number;
    kept: number;
    dropped: number;
    /** Exported columns whose mapping is still awaiting review. */
    pending: number;
    changed_cells: number;
    changed_rows: number;
    /** rows × exported columns */
    compared_cells: number;
}

export interface ExportValueChange {
    before: string;
    after: string;
    count: number;
    reason: ExportChangeReason;
}

export interface ExportColumnChange {
    source: string;
    /** Export column name; null when the column is not exported. */
    target: string | null;
    action: ExportColumnAction;
    mapping_status: ExportMappingStatus;
    drop_reason: ExportDropReason | null;
    /** For a dropped column: the source column that took its export name. */
    conflicts_with: string | null;
    changed_cells: number;
    value_changes: ExportValueChange[];
    /** Distinct changes beyond those listed in value_changes. */
    more_value_changes: number;
}

export interface ExportCellChange {
    /** Index into ExportPreviewRows.columns */
    column: number;
    before: string;
    reason: ExportChangeReason;
}

export interface ExportPreviewRow {
    /** 1-based data row number */
    line: number;
    values: string[];
    changes: ExportCellChange[];
}

export interface ExportPreviewRows {
    total: number;
    offset: number;
    limit: number;
    columns: string[];
    items: ExportPreviewRow[];
}

export interface ExportPreview {
    study_id: string;
    summary: ExportPreviewSummary;
    columns: ExportColumnChange[];
    rows: ExportPreviewRows;
}

export interface ExportPreviewQuery {
    offset: number;
    limit: number;
    changedOnly: boolean;
    /** Export column to focus on (rows where it changed); null for all. */
    column: string | null;
}
