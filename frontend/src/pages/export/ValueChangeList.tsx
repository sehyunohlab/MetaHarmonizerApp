import { ArrowRight, Rows3 } from 'lucide-react';
import type { ExportColumnChange } from '../../api/types';
import Badge from '../../components/ui/Badge';
import { CellText } from './CellText';
import { REASON_META, distinctValueChanges, pluralize } from './presentation';

export function ValueChangeList({
  column,
  onShowRows,
}: {
  column: ExportColumnChange;
  onShowRows: () => void;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">
          Value changes in <code className="font-mono">{column.target}</code>
          <span className="ml-1.5 font-normal text-slate-500 dark:text-slate-400">
            · {pluralize(distinctValueChanges(column), 'distinct value')}
          </span>
        </p>
        <button type="button" onClick={onShowRows} className="btn-ghost btn-sm">
          <Rows3 className="h-3.5 w-3.5" />
          Show rows
        </button>
      </div>
      <ul className="divide-y divide-slate-100 dark:divide-slate-800">
        {column.value_changes.map((change) => {
          const reason = REASON_META[change.reason];
          return (
            <li
              key={`${change.reason}:${change.before}\u0000${change.after}`}
              className="flex flex-wrap items-center gap-x-3 gap-y-1 py-1.5 text-xs"
            >
              <span className="min-w-0 rounded-md bg-rose-50 px-1.5 py-0.5 font-mono text-rose-700 dark:bg-rose-500/10 dark:text-rose-300">
                <CellText value={change.before} className="max-w-[14rem] line-through decoration-rose-400/70" />
              </span>
              <ArrowRight className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden="true" />
              <span className="sr-only">becomes</span>
              <span className="min-w-0 rounded-md bg-emerald-50 px-1.5 py-0.5 font-mono font-semibold text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-200">
                <CellText value={change.after} className="max-w-[14rem]" />
              </span>
              <span className="ml-auto inline-flex items-center gap-3" title={reason.hint}>
                <Badge tone={reason.tone}>{reason.label}</Badge>
                <span className="w-20 text-right tabular-nums text-slate-500 dark:text-slate-400">
                  {pluralize(change.count, 'cell')}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
      {column.more_value_changes > 0 && (
        <p className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
          {pluralize(column.more_value_changes, 'more distinct change')} not listed (every ontology change is). Use
          Show rows to browse every changed cell.
        </p>
      )}
    </div>
  );
}
