import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { BrainCircuit, CheckCheck, CheckCircle2, CircleX, Globe2, RefreshCw, RotateCcw, X } from 'lucide-react';
import { toast } from 'sonner';
import Badge from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import { EmptyState, LoadingBlock } from '../../components/ui/Feedback';
import SegmentedControl from '../../components/ui/SegmentedControl';
import {
  adminListLearnedCandidates,
  adminListSharedLearned,
  adminReviewLearned,
  adminUnpromoteLearned,
  type LearnedCandidate,
  type SharedLearnedDecision,
} from '../../api/auth';
import { LearnedHeader, SharedLearnedTable } from './LearnedDecisionTables';

// Two-layer curation KB (ADR-0002): shared promotion queue. All admins see the
// same queue; promoting a personal decision publishes it to the shared layer so
// it applies for every curator. Idempotent, so concurrent admins are safe.
export function LearnedDecisionsCard() {
  const qc = useQueryClient();
  const [decisionTab, setDecisionTab] = useState<'accept' | 'reject' | 'promoted'>('accept');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const candidates = useQuery({
    queryKey: ['admin', 'learned-candidates'],
    queryFn: () => adminListLearnedCandidates(1),
  });
  const shared = useQuery({
    queryKey: ['admin', 'learned-shared'],
    queryFn: adminListSharedLearned,
  });

  const reviewM = useMutation({
    mutationFn: ({ action, items }: { action: 'promote' | 'dismiss'; items: LearnedCandidate[] }) =>
      adminReviewLearned(action, items),
    onSuccess: (result) => {
      setSelected(new Set());
      qc.invalidateQueries({ queryKey: ['admin', 'learned-candidates'] });
      qc.invalidateQueries({ queryKey: ['admin', 'learned-shared'] });
      toast.success(
        result.action === 'promote'
          ? `${result.count} decision${result.count === 1 ? '' : 's'} promoted to the shared knowledge base`
          : `${result.count} candidate${result.count === 1 ? '' : 's'} dismissed from the promotion queue`,
      );
    },
    onError: (e: any) => toast.error(e?.message ?? 'Could not review learned decisions'),
  });

  const unpromoteM = useMutation({
    mutationFn: (items: SharedLearnedDecision[]) => adminUnpromoteLearned(items.map((item) => item.id)),
    onSuccess: (result) => {
      setSelected(new Set());
      qc.invalidateQueries({ queryKey: ['admin', 'learned-candidates'] });
      qc.invalidateQueries({ queryKey: ['admin', 'learned-shared'] });
      toast.success(`${result.count} global decision${result.count === 1 ? '' : 's'} stopped`);
    },
    onError: (e: any) => toast.error(e?.message ?? 'Could not stop sharing decisions'),
  });

  const allRows = candidates.data?.candidates ?? [];
  const sharedRows = shared.data?.shared ?? [];
  const rows = decisionTab === 'promoted' ? [] : allRows.filter((candidate) => candidate.decision === decisionTab);
  const selectedRows = rows.filter((candidate) => selected.has(candidate.candidate_key));
  const selectedShared = sharedRows.filter((item) => selected.has(`shared:${item.id}`));
  const visibleKeys = decisionTab === 'promoted'
    ? sharedRows.map((item) => `shared:${item.id}`)
    : rows.map((candidate) => candidate.candidate_key);
  const allVisibleSelected = visibleKeys.length > 0 && visibleKeys.every((key) => selected.has(key));

  const changeTab = (tab: 'accept' | 'reject' | 'promoted') => {
    setDecisionTab(tab);
    setSelected(new Set());
  };

  const toggleCandidate = (key: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const toggleAllVisible = () => {
    setSelected(allVisibleSelected ? new Set() : new Set(visibleKeys));
  };

  const review = (action: 'promote' | 'dismiss', items: LearnedCandidate[]) => {
    if (items.length) reviewM.mutate({ action, items });
  };

  return (
    <Card>
      <CardHeader
        icon={<BrainCircuit className="h-4 w-4" />}
        title="Learned decisions — promotion queue"
        description="Review personal decision patterns and manage which rules apply globally to future studies."
        action={
          <button
            type="button"
            onClick={() => { candidates.refetch(); shared.refetch(); }}
            disabled={candidates.isFetching || shared.isFetching}
            className="inline-flex items-center gap-1.5 rounded-sm border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            title="Refresh the queue and agreement stats (another admin may have promoted something)"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${candidates.isFetching || shared.isFetching ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        }
      />
      <CardBody>
        {candidates.isLoading || shared.isLoading ? (
          <LoadingBlock />
        ) : allRows.length === 0 && sharedRows.length === 0 ? (
          <EmptyState
            icon={<BrainCircuit className="h-6 w-6" />}
            title="Nothing to promote yet"
            description="Personal decisions curators choose to remember will appear here with agreement analytics."
          />
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <SegmentedControl
                value={decisionTab}
                onChange={changeTab}
                size="sm"
                segments={[
                  {
                    value: 'accept',
                    label: 'Accepted mappings',
                    count: allRows.filter((candidate) => candidate.decision === 'accept').length,
                    icon: <CheckCircle2 className="h-3.5 w-3.5" />,
                    tone: 'emerald',
                  },
                  {
                    value: 'reject',
                    label: 'Rejected mappings',
                    count: allRows.filter((candidate) => candidate.decision === 'reject').length,
                    icon: <CircleX className="h-3.5 w-3.5" />,
                    tone: 'rose',
                  },
                  {
                    value: 'promoted',
                    label: 'Promoted globally',
                    count: sharedRows.length,
                    icon: <Globe2 className="h-3.5 w-3.5" />,
                    tone: 'amber',
                  },
                ]}
              />
              <p className="max-w-xl text-xs text-slate-500 dark:text-slate-400">
                {decisionTab === 'accept'
                  ? 'Curators accepted the displayed target. Promote to reuse that target for everyone.'
                  : decisionTab === 'reject'
                    ? 'Curators rejected the automatic proposal. Promote to automatically reject that source for everyone.'
                    : 'These rules apply globally to future studies. Stop sharing to return a rule to the review queue without changing existing studies.'}
              </p>
            </div>

            {decisionTab !== 'promoted' && selectedRows.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 rounded-xl border border-primary-200 bg-primary-50/70 px-3 py-2 dark:border-primary-500/25 dark:bg-primary-500/10">
                <span className="mr-auto text-xs font-semibold text-primary-800 dark:text-primary-200">
                  {selectedRows.length} selected
                </span>
                <Button
                  size="sm"
                  loading={reviewM.isPending && reviewM.variables?.action === 'promote'}
                  disabled={reviewM.isPending}
                  icon={<CheckCheck className="h-3.5 w-3.5" />}
                  onClick={() => review('promote', selectedRows)}
                >
                  Promote selected
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  loading={reviewM.isPending && reviewM.variables?.action === 'dismiss'}
                  disabled={reviewM.isPending}
                  icon={<X className="h-3.5 w-3.5" />}
                  onClick={() => review('dismiss', selectedRows)}
                >
                  Dismiss selected
                </Button>
              </div>
            )}

            {decisionTab === 'promoted' && selectedShared.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-2 dark:border-amber-500/25 dark:bg-amber-500/10">
                <span className="mr-auto text-xs font-semibold text-amber-800 dark:text-amber-200">
                  {selectedShared.length} selected
                </span>
                <Button
                  size="sm"
                  variant="danger"
                  loading={unpromoteM.isPending}
                  icon={<RotateCcw className="h-3.5 w-3.5" />}
                  onClick={() => unpromoteM.mutate(selectedShared)}
                >
                  Stop sharing selected
                </Button>
              </div>
            )}

            {decisionTab === 'promoted' ? (
              sharedRows.length === 0 ? (
                <EmptyState
                  icon={<Globe2 className="h-6 w-6" />}
                  title="No globally promoted decisions"
                  description="Promoted decisions will appear here and can be reverted later."
                />
              ) : (
                <SharedLearnedTable
                  rows={sharedRows}
                  selected={selected}
                  allSelected={allVisibleSelected}
                  busy={unpromoteM.isPending}
                  onToggle={toggleCandidate}
                  onToggleAll={toggleAllVisible}
                  onUnpromote={(items) => unpromoteM.mutate(items)}
                />
              )
            ) : rows.length === 0 ? (
              <EmptyState
                icon={decisionTab === 'accept' ? <CheckCircle2 className="h-6 w-6" /> : <CircleX className="h-6 w-6" />}
                title={`No ${decisionTab === 'accept' ? 'accepted' : 'rejected'} decisions waiting`}
                description="Switch tabs to review the other decision type."
              />
            ) : <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-400 dark:border-slate-800">
                  <th className="w-10 px-2 py-2">
                    <input
                      type="checkbox"
                      className="checkbox"
                      checked={allVisibleSelected}
                      onChange={toggleAllVisible}
                      aria-label={`Select all ${decisionTab === 'accept' ? 'accepted' : 'rejected'} decisions`}
                    />
                  </th>
                  <th className="px-2 py-2">
                    <LearnedHeader label="Kind" help="Schema means a column-to-field mapping. Ontology means a raw value-to-standard-term mapping." />
                  </th>
                  <th className="px-2 py-2">
                    <LearnedHeader label="Source" help="The normalized column name, or field and raw value, that this learned decision applies to." />
                  </th>
                  <th className="px-2 py-2">
                    <LearnedHeader
                      label="Effect / target"
                      help="The decision effect first, followed by the field or ontology target when the decision was accepted."
                    />
                  </th>
                  <th className="px-2 py-2 text-center">
                    <LearnedHeader label="Curators" help="Number of distinct curators who made this exact same decision." centered />
                  </th>
                  <th className="px-2 py-2 text-center">
                    <LearnedHeader label="Confirmations" help="Total times this exact decision was made across studies. One curator can confirm it more than once." centered />
                  </th>
                  <th className="px-2 py-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.candidate_key} className={`border-b border-slate-50 dark:border-slate-800/60 ${selected.has(c.candidate_key) ? 'bg-primary-50/60 dark:bg-primary-500/10' : ''}`}>
                    <td className="px-2 py-2">
                      <input
                        type="checkbox"
                        className="checkbox"
                        checked={selected.has(c.candidate_key)}
                        onChange={() => toggleCandidate(c.candidate_key)}
                        aria-label={`Select ${c.source_key}`}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <Badge tone={c.kind === 'schema' ? 'primary' : 'slate'}>{c.kind}</Badge>
                    </td>
                    <td className="px-2 py-2 font-mono text-xs text-slate-600 dark:text-slate-300">{c.source_key}</td>
                    <td className="px-2 py-2 text-slate-700 dark:text-slate-300">
                      <span className="flex items-center gap-2">
                        <Badge tone={c.decision === 'accept' ? 'green' : 'rose'}>
                          {c.decision === 'accept' ? 'Accepted' : 'Rejected'}
                        </Badge>
                        {c.decision === 'accept' && (
                          <span>{`${c.target_field ?? c.target_term ?? ''}${c.target_id ? ` (${c.target_id})` : ''}`}</span>
                        )}
                      </span>
                    </td>
                    <td className="px-2 py-2 text-center font-semibold text-slate-700 dark:text-slate-300">{c.curators}</td>
                    <td className="px-2 py-2 text-center text-slate-600 dark:text-slate-300">{c.support}</td>
                    <td className="px-2 py-2 text-right">
                      <div className="inline-flex items-center gap-1.5">
                      <Button
                        size="sm"
                        loading={reviewM.isPending && reviewM.variables?.action === 'promote' && reviewM.variables.items.some((item) => item.candidate_key === c.candidate_key)}
                        disabled={reviewM.isPending}
                        onClick={() => review('promote', [c])}
                        icon={<CheckCheck className="h-3.5 w-3.5" />}
                      >
                        Promote
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-500/15"
                        loading={reviewM.isPending && reviewM.variables?.action === 'dismiss' && reviewM.variables.items.some((item) => item.candidate_key === c.candidate_key)}
                        disabled={reviewM.isPending}
                        onClick={() => review('dismiss', [c])}
                        icon={<X className="h-3.5 w-3.5" />}
                        title="Dismiss this candidate without promoting it"
                      >
                        Dismiss
                      </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
