import type { Dispatch, SetStateAction } from 'react';
import { Check, ChevronDown, ChevronRight, Loader2, Pencil, Plus, Sparkles, X } from 'lucide-react';
import type { OntologyMapping } from '../../api/types';
import ConfidenceBadge from '../../components/ConfidenceBadge';
import { Card, CardBody } from '../../components/ui/Card';
import type { EditState, OntologyStats, OntologySuggestion, UnmatchedGroupItem } from './types';

interface UnmatchedMappingsCardProps {
  stats: OntologyStats;
  showUnmatched: boolean;
  setShowUnmatched: Dispatch<SetStateAction<boolean>>;
  finding: boolean;
  findSuggestions: () => Promise<void>;
  suggestedRows: UnmatchedGroupItem[];
  showAllSuggestions: boolean;
  setShowAllSuggestions: Dispatch<SetStateAction<boolean>>;
  suggestions: Record<number, OntologySuggestion>;
  busy: Record<number, boolean>;
  applySuggestion: (m: OntologyMapping) => Promise<void>;
  dismissSuggestion: (m: OntologyMapping) => void;
  setEditState: Dispatch<SetStateAction<EditState | null>>;
  groupedUnmatched: Record<string, UnmatchedGroupItem[]>;
  expandedFields: Record<string, boolean>;
  setExpandedFields: Dispatch<SetStateAction<Record<string, boolean>>>;
}

export function UnmatchedMappingsCard({
  stats,
  showUnmatched,
  setShowUnmatched,
  finding,
  findSuggestions,
  suggestedRows,
  showAllSuggestions,
  setShowAllSuggestions,
  suggestions,
  busy,
  applySuggestion,
  dismissSuggestion,
  setEditState,
  groupedUnmatched,
  expandedFields,
  setExpandedFields,
}: UnmatchedMappingsCardProps) {
  return (
    stats.unmatched > 0 && (
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
          <button
            onClick={() => setShowUnmatched((s) => !s)}
            className="flex items-center gap-2 text-left text-sm font-medium text-slate-700 dark:text-slate-300"
          >
            {showUnmatched ? <ChevronDown className="h-4 w-4 text-slate-400" /> : <ChevronRight className="h-4 w-4 text-slate-400" />}
            {stats.unmatched.toLocaleString()} values had no ontology match
          </button>
          <button
            onClick={findSuggestions}
            disabled={finding}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary-700 disabled:opacity-60"
          >
            {finding ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            {finding ? 'Searching ontology…' : 'Find suggestions'}
          </button>
        </div>
        {showUnmatched && (
          <CardBody className="max-h-[60vh] space-y-4 overflow-y-auto border-t border-slate-100 pt-4 dark:border-slate-800">
            {/* Suggested matches found by the ontology search */}
            {suggestedRows.length > 0 && (
              <div className="space-y-2 rounded-xl border border-primary-100 bg-primary-50/40 p-3 dark:border-primary-500/25 dark:bg-primary-500/10">
                <p className="flex items-center gap-1.5 text-xs font-semibold text-primary-800 dark:text-primary-300">
                  <Sparkles className="h-3.5 w-3.5" />
                  {suggestedRows.length} suggested {suggestedRows.length === 1 ? 'match' : 'matches'} — review &amp; apply
                </p>
                <ul className="space-y-1.5">
                  {(showAllSuggestions ? suggestedRows : suggestedRows.slice(0, 8)).map(({ row: m, count }) => {
                    const s = suggestions[m.id];
                    const isBusy = !!busy[m.id];
                    return (
                      <li key={m.id} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg bg-white px-3 py-2 dark:bg-slate-800/60">
                        <div className="flex min-w-0 flex-1 items-center gap-2">
                          <code className="rounded bg-slate-100 dark:bg-slate-800/70 px-1.5 py-0.5 text-xs text-slate-700 dark:text-slate-300">{m.raw_value}</code>
                          {count > 1 && (
                            <span className="rounded bg-slate-100 dark:bg-slate-800/70 px-1 text-[10px] text-slate-500">×{count}</span>
                          )}
                          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-300" />
                          <span className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">{s.term}</span>
                          <span className="truncate font-mono text-[11px] text-slate-400">{s.ontId}</span>
                          <span className="text-[10px] text-slate-400">in {m.field_name}</span>
                        </div>
                        <ConfidenceBadge score={s.score} size="sm" />
                        {isBusy ? (
                          <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
                        ) : (
                          <div className="flex items-center gap-1">
                            <button
                              title={count > 1 ? `Apply to all ${count} occurrences` : 'Apply this term'}
                              onClick={() => applySuggestion(m)}
                              className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-2 py-1 text-xs font-medium text-white hover:bg-emerald-700"
                            >
                              <Check className="h-3 w-3" /> Apply{count > 1 ? ' all' : ''}
                            </button>
                            <button
                              title="Edit before applying"
                              onClick={() => setEditState({ id: m.id, term: s.term, ontId: s.ontId, raw: m.raw_value })}
                              className="rounded p-1 text-blue-500 hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-blue-500/15 dark:shadow-none"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </button>
                            <button
                              title="Dismiss"
                              onClick={() => dismissSuggestion(m)}
                              className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-200 dark:shadow-none"
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
                {suggestedRows.length > 8 && (
                  <button
                    onClick={() => setShowAllSuggestions((v) => !v)}
                    className="text-xs font-medium text-primary-700 hover:text-primary-800 dark:text-primary-300 dark:hover:text-primary-200"
                  >
                    {showAllSuggestions ? 'Show fewer' : `View all ${suggestedRows.length} suggestions`}
                  </button>
                )}
              </div>
            )}

            <p className="text-xs text-slate-500">
              These values didn’t match a controlled-vocabulary term (often sample IDs, study
              names, or free text). Use <span className="font-medium text-slate-600 dark:text-slate-300">Find suggestions</span> to
              search the ontology automatically, or click any value to assign a term manually
              (applies to every occurrence of that value).
            </p>
            {Object.entries(groupedUnmatched).map(([field, items]) => {
              const expanded = !!expandedFields[field];
              const shown = expanded ? items : items.slice(0, 40);
              return (
                <div key={field}>
                  <p className="mb-1 text-xs font-semibold text-slate-600 dark:text-slate-300">
                    {field}{' '}
                    <span className="font-normal text-slate-400">
                      · {items.length} distinct value{items.length !== 1 ? 's' : ''}
                    </span>
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {shown.map(({ row: m, count }) => (
                      <button
                        key={m.id}
                        title={count > 1 ? `Assign a term to all ${count} occurrences` : 'Assign an ontology term'}
                        onClick={() => setEditState({ id: m.id, term: '', ontId: '', raw: m.raw_value })}
                        className="group inline-flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-500 hover:bg-primary-50 hover:text-primary-700 dark:bg-slate-800/70 dark:hover:bg-primary-500/15 dark:hover:text-primary-300"
                      >
                        {m.raw_value}
                        {count > 1 && <span className="text-slate-400">×{count}</span>}
                        <Plus className="h-2.5 w-2.5 opacity-0 transition group-hover:opacity-100" />
                      </button>
                    ))}
                    {items.length > 40 && (
                      <button
                        onClick={() => setExpandedFields((p) => ({ ...p, [field]: !expanded }))}
                        className="px-1 py-0.5 text-[11px] font-medium text-primary-700 hover:text-primary-800 dark:text-primary-300 dark:hover:text-primary-200"
                      >
                        {expanded ? 'Show fewer' : `View all ${items.length}`}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </CardBody>
        )}
      </Card>
    )
  );
}
