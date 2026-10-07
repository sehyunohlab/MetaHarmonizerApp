import type { RefObject } from 'react';
import { Filter, Search, Sparkles } from 'lucide-react';
import type { MappingSortMode } from '../../lib/mappingFilters';
import type { FilterStage, QueueStats } from './types';

type MappingFiltersProps = {
  filterStage: FilterStage;
  search: string;
  searchRef: RefObject<HTMLInputElement>;
  llmEnabled: boolean;
  queueStats: QueueStats | null;
  sortMode: MappingSortMode;
  filteredCount: number;
  mappingsCount: number;
  onFilterStageChange: (stage: FilterStage) => void;
  onSearchChange: (search: string) => void;
};

export function MappingFilters({
  filterStage,
  search,
  searchRef,
  llmEnabled,
  queueStats,
  sortMode,
  filteredCount,
  mappingsCount,
  onFilterStageChange,
  onSearchChange,
}: MappingFiltersProps) {
  return (
    <div className="flex items-center gap-4 card p-3">
      <Filter className="w-4 h-4 text-slate-400" />
      <div className="flex items-center gap-2">
        <label htmlFor="stage-filter" className="text-xs font-medium text-slate-500">Stage:</label>
        <select
          id="stage-filter"
          value={filterStage}
          onChange={(e) => onFilterStageChange(e.target.value as FilterStage)}
          className="text-sm border border-slate-200 rounded-lg px-2 py-1 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="all">All</option>
          <option value="stage1">S1 Dict/Fuzzy</option>
          <option value="stage2">S2 Value/Ontology</option>
          <option value="stage3">S3 Semantic</option>
          {llmEnabled && <option value="stage4">S4 LLM</option>}
          <option value="invalid">Invalid</option>
          <option value="unmapped">Unmapped</option>
        </select>
      </div>
      <div className="relative">
        <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
        <input
          ref={searchRef}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          aria-label="Search columns"
          placeholder="Search columns…  ( / )"
          className="w-48 rounded-lg border border-slate-200 py-1 pl-7 pr-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        />
      </div>
      {queueStats && (
        <span className="text-xs text-slate-500">
          {queueStats.risky} risky · {queueStats.batchable_groups} batchable group
          {queueStats.batchable_groups === 1 ? '' : 's'}
        </span>
      )}
      {sortMode === 'smart' && (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-primary-600 dark:text-primary-300">
          <Sparkles className="h-3 w-3" /> Smart review order
        </span>
      )}
      <span className="text-xs text-slate-400 ml-auto">
        {filteredCount} of {mappingsCount} shown
      </span>
    </div>
  );
}
