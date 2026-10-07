import * as Tooltip from '@radix-ui/react-tooltip';
import { Info, RotateCcw } from 'lucide-react';
import Badge from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import type { SharedLearnedDecision } from '../../api/auth';

export function SharedLearnedTable({
  rows,
  selected,
  allSelected,
  busy,
  onToggle,
  onToggleAll,
  onUnpromote,
}: {
  rows: SharedLearnedDecision[];
  selected: Set<string>;
  allSelected: boolean;
  busy: boolean;
  onToggle: (key: string) => void;
  onToggleAll: () => void;
  onUnpromote: (items: SharedLearnedDecision[]) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-400 dark:border-slate-800">
            <th className="w-10 px-2 py-2">
              <input
                type="checkbox"
                className="checkbox"
                checked={allSelected}
                onChange={onToggleAll}
                aria-label="Select all globally promoted decisions"
              />
            </th>
            <th className="px-2 py-2">
              <LearnedHeader label="Kind" help="Schema means a column-to-field mapping. Ontology means a raw value-to-standard-term mapping." />
            </th>
            <th className="px-2 py-2">
              <LearnedHeader label="Source" help="The normalized source this global rule matches on future studies." />
            </th>
            <th className="px-2 py-2">
              <LearnedHeader label="Effect / target" help="The global decision effect first, followed by its field or ontology target when accepted." />
            </th>
            <th className="px-2 py-2">
              <LearnedHeader label="Promoted" help="When this decision most recently became a global rule." />
            </th>
            <th className="px-2 py-2 text-right">Action</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const selectionKey = `shared:${row.id}`;
            return (
              <tr
                key={row.id}
                className={`border-b border-slate-50 dark:border-slate-800/60 ${selected.has(selectionKey) ? 'bg-amber-50/60 dark:bg-amber-500/10' : ''}`}
              >
                <td className="px-2 py-2">
                  <input
                    type="checkbox"
                    className="checkbox"
                    checked={selected.has(selectionKey)}
                    onChange={() => onToggle(selectionKey)}
                    aria-label={`Select ${row.source_key}`}
                  />
                </td>
                <td className="px-2 py-2">
                  <Badge tone={row.kind === 'schema' ? 'primary' : 'slate'}>{row.kind}</Badge>
                </td>
                <td className="px-2 py-2 font-mono text-xs text-slate-600 dark:text-slate-300">{row.source_key}</td>
                <td className="px-2 py-2 text-slate-700 dark:text-slate-300">
                  <span className="flex items-center gap-2">
                    <Badge tone={row.decision === 'accept' ? 'green' : 'rose'}>
                      {row.decision === 'accept' ? 'Accepted' : 'Rejected'}
                    </Badge>
                    {row.decision === 'accept' && (
                      <span>{`${row.target_field ?? row.target_term ?? ''}${row.target_id ? ` (${row.target_id})` : ''}`}</span>
                    )}
                  </span>
                </td>
                <td className="px-2 py-2 text-xs text-slate-500 dark:text-slate-400">
                  {new Date(row.updated_at).toLocaleDateString()}
                </td>
                <td className="px-2 py-2 text-right">
                  <Button
                    size="sm"
                    variant="danger"
                    loading={busy}
                    icon={<RotateCcw className="h-3.5 w-3.5" />}
                    onClick={() => onUnpromote([row])}
                    title="Stop applying this rule globally to future studies"
                  >
                    Stop sharing
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function LearnedHeader({ label, help, centered = false }: { label: string; help: string; centered?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 normal-case ${centered ? 'justify-center' : ''}`}>
      <span className="uppercase">{label}</span>
      <Tooltip.Provider delayDuration={180}>
        <Tooltip.Root>
          <Tooltip.Trigger asChild>
            <button
              type="button"
              aria-label={`About ${label}`}
              className="rounded-full text-slate-400 transition hover:text-primary-600 focus-visible:text-primary-600 dark:text-slate-500 dark:hover:text-primary-300 dark:focus-visible:text-primary-300"
            >
              <Info className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </Tooltip.Trigger>
          <Tooltip.Portal>
            <Tooltip.Content
              side="top"
              sideOffset={8}
              collisionPadding={12}
              className="z-50 max-w-72 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-left text-xs font-normal leading-relaxed tracking-normal text-slate-600 shadow-pop data-[state=delayed-open]:animate-fade-in dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
            >
              <span className="mb-0.5 block font-semibold text-slate-900 dark:text-slate-100">{label}</span>
              {help}
              <Tooltip.Arrow className="fill-white dark:fill-slate-900" />
            </Tooltip.Content>
          </Tooltip.Portal>
        </Tooltip.Root>
      </Tooltip.Provider>
    </span>
  );
}
