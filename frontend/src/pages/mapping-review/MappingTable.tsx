import React from 'react';
import {
  ArrowUpDown,
  Check,
  ChevronDown,
  ChevronUp,
  Loader2,
  Pencil,
  Sparkles,
  X,
} from 'lucide-react';
import ConfidenceBadge from '../../components/ConfidenceBadge';
import StageBadge from '../../components/StageBadge';
import StatusBadge from '../../components/StatusBadge';
import { TableFrame } from '../../components/ui/Table';
import type { Mapping } from '../../api/types';
import type { MappingSortMode } from '../../lib/mappingFilters';
import { ColumnContextPanel } from './ColumnContextPanel';
import type { GroupInfo, LlmSuggestion, SortKey } from './types';

type MappingTableProps = {
  loading: boolean;
  filteredMappings: Mapping[];
  selected: Set<number>;
  cursor: number;
  sortKey: SortKey;
  sortMode: MappingSortMode;
  smartOrder: boolean;
  groupInfo: GroupInfo;
  selectedGroups: Set<string>;
  expandedRow: number | null;
  selectedId: string | null;
  llmEnabled: boolean;
  llmBusyId: number | null;
  llmResults: Record<number, LlmSuggestion[]>;
  onToggleSelectAll: () => void;
  onToggleSelect: (id: number) => void;
  onSelectGroup: (groupKey: string) => void;
  onSort: (key: SortKey) => void;
  onCursorChange: (cursor: number) => void;
  onAccept: (id: number) => void;
  onReject: (id: number) => void;
  onOpenEdit: (mapping: Mapping) => void;
  onExpandedRowChange: (row: number | null) => void;
  onApplyAlternative: (id: number, field: string) => void;
  onLlmRematch: (id: number) => void;
};

export function MappingTable({
  loading,
  filteredMappings,
  selected,
  cursor,
  sortKey,
  sortMode,
  smartOrder,
  groupInfo,
  selectedGroups,
  expandedRow,
  selectedId,
  llmEnabled,
  llmBusyId,
  llmResults,
  onToggleSelectAll,
  onToggleSelect,
  onSelectGroup,
  onSort,
  onCursorChange,
  onAccept,
  onReject,
  onOpenEdit,
  onExpandedRowChange,
  onApplyAlternative,
  onLlmRematch,
}: MappingTableProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-primary-500 animate-spin" />
      </div>
    );
  }

  return (
    <TableFrame>
      <table className="w-full text-sm">
        <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 dark:bg-slate-800/50 dark:border-slate-800">
          <tr>
            <th className="px-3 py-3 text-left">
              <input
                type="checkbox"
                checked={selected.size === filteredMappings.length && filteredMappings.length > 0}
                onChange={onToggleSelectAll}
                className="checkbox"
              />
            </th>
            <SortableHeader label="Raw Column" sortKey="raw_column" current={sortKey} mode={sortMode} onSort={onSort} />
            <th className="px-3 py-3 text-left text-xs font-medium text-slate-500 uppercase">
              Matched Field
            </th>
            <SortableHeader label="Confidence" sortKey="confidence_score" current={sortKey} mode={sortMode} onSort={onSort} />
            <SortableHeader label="Stage" sortKey="stage" current={sortKey} mode={sortMode} onSort={onSort} />
            <SortableHeader label="Status" sortKey="status" current={sortKey} mode={sortMode} onSort={onSort} />
            <th className="px-3 py-3 text-left text-xs font-medium text-slate-500 uppercase">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-slate-800">
          {filteredMappings.map((m, idx) => (
            <React.Fragment key={m.id}>
              <tr
                data-row-cursor={idx === cursor ? 'true' : undefined}
                onClick={() => onCursorChange(idx)}
                className={`hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors ${
                  idx === cursor ? 'ring-2 ring-inset ring-primary-400' : ''
                } ${selected.has(m.id) ? 'bg-primary-50 dark:bg-primary-500/10' : ''}`}
              >
                <td className="px-3 py-2.5">
                  <input
                    type="checkbox"
                    checked={selected.has(m.id)}
                    onChange={() => onToggleSelect(m.id)}
                    className="checkbox"
                  />
                </td>
                <td className="px-3 py-2.5 font-mono text-xs font-medium text-slate-900 dark:text-slate-100">
                  {m.raw_column}
                </td>
                <td className="px-3 py-2.5 font-mono text-xs text-primary-700 dark:text-primary-300">
                  {m.curator_field || m.matched_field || (
                    <span className="text-slate-400 italic">unmapped</span>
                  )}
                  {smartOrder && m.status === 'pending' && (groupInfo[m.id]?.size ?? 0) > 1 && (() => {
                    const gsel = selectedGroups.has(groupInfo[m.id].key);
                    return (
                      <button
                        onClick={(e) => { e.stopPropagation(); onSelectGroup(groupInfo[m.id].key); }}
                        title={gsel ? 'Deselect this look-alike group' : 'Select all pending look-alikes in this group for a batch decision'}
                        className={`ml-2 rounded-full px-1.5 py-0.5 text-[10px] font-semibold transition ${
                          gsel
                            ? 'bg-primary-600 text-white hover:bg-primary-700'
                            : 'bg-primary-50 text-primary-600 hover:bg-primary-100 dark:bg-primary-500/15 dark:text-primary-300 dark:hover:bg-primary-500/25'
                        }`}
                      >
                        {gsel ? '✓' : '⌄'} {groupInfo[m.id].size} in group
                      </button>
                    );
                  })()}
                </td>
                <td className="px-3 py-2.5">
                  <ConfidenceBadge score={m.confidence_score} size="sm" />
                </td>
                <td className="px-3 py-2.5">
                  <StageBadge stage={m.stage} />
                </td>
                <td className="px-3 py-2.5">
                  <StatusBadge status={m.status} />
                </td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-1">
                    {m.status !== 'accepted' && (
                      <button
                        onClick={() => onAccept(m.id)}
                        className="p-1 rounded-sm text-green-600 hover:bg-green-100 dark:text-green-400 dark:hover:bg-green-500/15"
                        title="Accept"
                      >
                        <Check className="w-4 h-4" />
                      </button>
                    )}
                    {m.status !== 'rejected' && (
                      <button
                        onClick={() => onReject(m.id)}
                        className="p-1 rounded-sm text-red-600 hover:bg-red-100 dark:text-red-400 dark:hover:bg-red-500/15"
                        title="Reject"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    )}
                    <button
                      onClick={() => onOpenEdit(m)}
                      className="p-1 rounded-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-500/15"
                      title="Edit"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => onExpandedRowChange(expandedRow === m.id ? null : m.id)}
                      className="p-1 rounded-sm text-slate-500 hover:bg-slate-200 dark:text-slate-400 dark:hover:bg-slate-700"
                      title="Details"
                    >
                      {expandedRow === m.id ? (
                        <ChevronUp className="w-4 h-4" />
                      ) : (
                        <ChevronDown className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </td>
              </tr>

              {/* Expanded detail */}
              {expandedRow === m.id && (
                <tr>
                  <td colSpan={7} className="bg-slate-50 px-6 py-4 dark:bg-slate-800/40">
                    <div className="grid grid-cols-2 gap-6 text-xs">
                      <div>
                        <h4 className="font-semibold text-slate-700 mb-2 dark:text-slate-300">
                          Top-5 Alternative Matches
                        </h4>
                        {m.alternatives.length > 0 ? (
                          <ul className="space-y-1">
                            {m.alternatives.map((alt, i) => (
                              <li key={`${alt.field}-${i}`} className="flex items-center gap-2">
                                <span className="font-mono text-primary-700 dark:text-primary-300">
                                  {alt.field}
                                </span>
                                <ConfidenceBadge
                                  score={alt.score}
                                  size="sm"
                                />
                                <span className="text-slate-400">
                                  {alt.method}
                                </span>
                                {m.status !== 'accepted' && (
                                  <button
                                    onClick={() => onApplyAlternative(m.id, alt.field)}
                                    className="ml-auto rounded-md px-2 py-0.5 text-[11px] font-semibold text-primary-600 hover:bg-primary-50 dark:text-primary-300 dark:hover:bg-primary-500/10"
                                  >
                                    Apply
                                  </button>
                                )}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-slate-400 italic">
                            No alternative matches
                          </p>
                        )}

                        {/* On-demand Stage-4 LLM rematch — hidden when the server has no LLM key */}
                        {llmEnabled && (
                        <div className="mt-3 border-t border-slate-200 pt-3 dark:border-slate-800">
                          <button
                            onClick={() => onLlmRematch(m.id)}
                            disabled={llmBusyId === m.id}
                            className="flex items-center gap-1.5 rounded-md bg-orange-50 px-2.5 py-1 text-[11px] font-semibold text-orange-700 hover:bg-orange-100 disabled:opacity-60 dark:bg-orange-500/15 dark:text-orange-300 dark:hover:bg-orange-500/25"
                          >
                            <Sparkles className="h-3.5 w-3.5" />
                            {llmBusyId === m.id ? 'Asking the LLM…' : 'Try LLM rematch'}
                          </button>
                          {llmResults[m.id]?.length > 0 && (
                            <ul className="mt-2 space-y-1">
                              {llmResults[m.id].map((s, i) => (
                                <li key={`llm-${s.field}-${i}`} className="flex items-center gap-2">
                                  <Sparkles className="h-3 w-3 text-orange-400" />
                                  <span className="font-mono text-orange-700 dark:text-orange-300">{s.field}</span>
                                  <ConfidenceBadge score={s.confidence} size="sm" />
                                  {m.status !== 'accepted' && (
                                    <button
                                      onClick={() => onApplyAlternative(m.id, s.field)}
                                      className="ml-auto rounded-md px-2 py-0.5 text-[11px] font-semibold text-orange-600 hover:bg-orange-50 dark:text-orange-300 dark:hover:bg-orange-500/15"
                                    >
                                      Apply
                                    </button>
                                  )}
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                        )}
                      </div>
                      <div>
                        <h4 className="font-semibold text-slate-700 mb-2 dark:text-slate-300">
                          Mapping Details
                        </h4>
                        <dl className="space-y-1">
                          <dt className="text-slate-500 dark:text-slate-400">Method</dt>
                          <dd className="text-slate-900 dark:text-slate-100">
                            {m.method || 'N/A'}
                          </dd>
                          <dt className="text-slate-500 dark:text-slate-400">
                            Curator Note
                          </dt>
                          <dd className="text-slate-900 dark:text-slate-100">
                            {m.curator_note || '—'}
                          </dd>
                          {m.reviewed_at && (
                            <>
                              <dt className="text-slate-500 dark:text-slate-400">
                                Reviewed
                              </dt>
                              <dd className="text-slate-900 dark:text-slate-100">
                                {new Date(m.reviewed_at).toLocaleString()}
                              </dd>
                            </>
                          )}
                        </dl>

                        {/* Column context — sample values to disambiguate */}
                        {selectedId && (
                          <div className="mt-3 border-t border-slate-200 pt-3 dark:border-slate-800">
                            <h4 className="font-semibold text-slate-700 mb-2 dark:text-slate-300">
                              Column values
                            </h4>
                            <ColumnContextPanel studyId={selectedId} column={m.raw_column} />
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>

      {filteredMappings.length === 0 && (
        <div className="text-center py-12 text-slate-400">
          No mappings match the current filters.
        </div>
      )}
    </TableFrame>
  );
}

/* Sortable header cell */
function SortableHeader({
  label,
  sortKey,
  current,
  mode,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  current: SortKey;
  mode: MappingSortMode;
  onSort: (k: SortKey) => void;
}) {
  return (
    <th
      className="px-3 py-3 text-left text-xs font-medium text-slate-500 uppercase cursor-pointer select-none hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
      onClick={() => onSort(sortKey)}
      title={mode === 'smart' ? `Smart review order active. Sort ${label} descending` : `Sort ${label}`}
    >
      <span className="flex items-center gap-1">
        {label}
        <ArrowUpDown className="w-3 h-3" />
        {mode !== 'smart' && current === sortKey && (
          <span className="text-primary-600 dark:text-primary-300">{mode === 'ascending' ? '↑' : '↓'}</span>
        )}
      </span>
    </th>
  );
}
