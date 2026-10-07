import type { Dispatch, SetStateAction } from 'react';
import { Check, ChevronRight, Loader2, Pencil, X } from 'lucide-react';
import type { OntologyMapping } from '../../api/types';
import ConfidenceBadge from '../../components/ConfidenceBadge';
import StatusBadge from '../../components/StatusBadge';
import { Card, CardBody } from '../../components/ui/Card';
import type { EditState, StatusFilter } from './types';

interface MatchedMappingsListProps {
  matchedFields: string[];
  groupedMatched: Record<string, OntologyMapping[]>;
  busy: Record<number, boolean>;
  statusFilter: StatusFilter;
  handleAccept: (id: number) => Promise<void>;
  handleReject: (id: number) => Promise<void>;
  setEditState: Dispatch<SetStateAction<EditState | null>>;
}

export function MatchedMappingsList({
  matchedFields,
  groupedMatched,
  busy,
  statusFilter,
  handleAccept,
  handleReject,
  setEditState,
}: MatchedMappingsListProps) {
  return (
    matchedFields.length === 0 ? (
      <Card>
        <CardBody className="py-8 text-center text-sm text-slate-400">
          No {statusFilter !== 'all' ? statusFilter : ''} values to show.
        </CardBody>
      </Card>
    ) : (
      <div className="space-y-4">
        {matchedFields.map((field) => (
          <div key={field} className="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/80 px-4 py-2.5 dark:border-slate-800 dark:bg-slate-800/50">
              <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">{field}</h2>
              <span className="text-xs text-slate-400">
                {groupedMatched[field].length} value{groupedMatched[field].length !== 1 ? 's' : ''}
              </span>
            </div>
            <ul className="divide-y divide-slate-100 dark:divide-slate-800">
              {groupedMatched[field].map((om) => {
                const isBusy = !!busy[om.id];
                const term = om.curator_term ?? om.ontology_term;
                const oid = om.curator_id ?? om.ontology_id;
                return (
                  <li key={om.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5 hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    {/* raw → term */}
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                      <code className="rounded-sm bg-slate-100 dark:bg-slate-800/70 px-1.5 py-0.5 text-xs text-slate-700 dark:text-slate-300">{om.raw_value}</code>
                      <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-300" />
                      <span className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">{term}</span>
                      {om.curator_term && <span className="text-[10px] text-amber-600">(edited)</span>}
                      {oid && <span className="truncate font-mono text-[11px] text-slate-400">{oid}</span>}
                    </div>
                    <ConfidenceBadge score={om.confidence_score} size="sm" />
                    <StatusBadge status={om.status} />
                    <div className="flex items-center gap-1">
                      {isBusy ? (
                        <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
                      ) : (
                        <>
                          {om.status !== 'accepted' && (
                            <button title="Accept" onClick={() => handleAccept(om.id)} className="rounded-sm p-1 text-emerald-600 hover:bg-emerald-50 dark:text-emerald-400 dark:hover:bg-emerald-500/15 dark:shadow-none">
                              <Check className="h-3.5 w-3.5" />
                            </button>
                          )}
                          {om.status !== 'rejected' && (
                            <button title="Reject" onClick={() => handleReject(om.id)} className="rounded-sm p-1 text-rose-500 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-500/15 dark:shadow-none">
                              <X className="h-3.5 w-3.5" />
                            </button>
                          )}
                          <button
                            title="Edit term"
                            onClick={() => setEditState({ id: om.id, term: term ?? '', ontId: oid ?? '', raw: om.raw_value })}
                            className="rounded-sm p-1 text-blue-500 hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-blue-500/15 dark:shadow-none"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                        </>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    )
  );
}
