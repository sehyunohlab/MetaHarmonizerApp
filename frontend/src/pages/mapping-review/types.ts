import type { MappingStatusFilter } from '../../lib/mappingFilters';

export type SortKey = 'raw_column' | 'confidence_score' | 'stage' | 'status';
export type FilterStage = 'all' | 'stage1' | 'stage2' | 'stage3' | 'stage4' | 'invalid' | 'unmapped';
export type FilterStatus = MappingStatusFilter;
export type GroupInfo = Record<number, { key: string; size: number; min: number; rank: number }>;
export type QueueStats = { groups: number; batchable_groups: number; risky: number };
export type LlmSuggestion = { field: string; confidence: number; reasoning: string };
