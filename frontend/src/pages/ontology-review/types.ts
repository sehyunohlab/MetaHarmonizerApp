import type { OntologyMapping } from '../../api/types';

export interface EditState { id: number; term: string; ontId: string; raw?: string }
export type StatusFilter = 'all' | 'pending' | 'accepted' | 'rejected';

export interface OntologySuggestion {
  term: string;
  ontId: string;
  score: number;
}

export interface OntologyStats {
  mapped: number;
  accepted: number;
  pending: number;
  unmatched: number;
}

export interface RewritePreviewRow {
  raw: string;
  term: string;
  ontId: string | null;
}

export interface UnmatchedGroupItem {
  row: OntologyMapping;
  count: number;
}
