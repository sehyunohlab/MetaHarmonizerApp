import { useState } from 'react';
import { ChevronLeft, ChevronRight, Rows3, X } from 'lucide-react';
import type {
  ExportChangeReason,
  ExportColumnChange,
  ExportPreviewQuery,
  ExportPreviewRows,
} from '../../api/types';
import { Card, CardHeader } from '../../components/ui/Card';
import { EmptyState, Spinner } from '../../components/ui/Feedback';
import { cn } from '../../lib/cn';
import { CellText } from './CellText';
import {
  REASON_META,
  changedCellsByTarget,
  changesByColumn,
  clampOffset,
  renamedFrom,
  rowRangeLabel,
  visibleColumnIndexes,
} from './presentation';

const CHANGED_CELL: Record<ExportChangeReason, string> = {
  ontology: 'bg-emerald-50 dark:bg-emerald-500/10',
  escaped: 'bg-amber-50 dark:bg-amber-500/10',
  other: 'bg-sky-50 dark:bg-sky-500/10',
};

const CHANGED_TEXT: Record<ExportChangeReason, string> = {
  ontology: 'text-emerald-800 dark:text-emerald-200',
  escaped: 'text-amber-800 dark:text-amber-200',
  other: 'text-sky-800 dark:text-sky-200',
};

export function ChangedValuesGrid({
  rows,
  columns,
  query,
  fetching,
  onQueryChange,
}: {
  rows: ExportPreviewRows;
  columns: ExportColumnChange[];
  query: ExportPreviewQuery;
  fetching: boolean;
  onQueryChange: (query: ExportPreviewQuery) => void;
}) {
  const [changedColumnsOnly, setChangedColumnsOnly] = useState(true);
  const changedCells = changedCellsByTarget(columns);
  const sources = renamedFrom(columns);
  const visible = visibleColumnIndexes(rows.columns, changedCells, {
    changedOnly: changedColumnsOnly,
    focus: query.column,
  });
  const changedTargets = rows.columns.filter((name) => (changedCells[name] ?? 0) > 0);
  const hasOtherChanges = rows.items.some((row) => row.changes.some((change) => change.reason === 'other'));
  const pageEnd = rows.offset + rows.items.length;
  const refine = (patch: Partial<ExportPreviewQuery>) => onQueryChange({ ...query, offset: 0, ...patch });

  return (
    <Card>
      <CardHeader
        icon={<Rows3 className="h-4 w-4" />}
        title="Changed values"
        description="Exported values next to your upload. Changed cells show the uploaded value struck through."
        action={fetching ? <Spinner className="h-4 w-4 text-slate-400" /> : undefined}
      />

      <div className="flex flex-wrap items-center gap-x-5 gap-y-3 border-b border-slate-100 px-5 py-3 text-sm dark:border-slate-800">
        <label className="inline-flex cursor-pointer items-center gap-2 text-slate-700 dark:text-slate-200">
          <input
            type="checkbox"
            className="checkbox"
            checked={query.changedOnly}
            onChange={(event) =>
              refine({ changedOnly: event.target.checked, column: event.target.checked ? query.column : null })
            }
          />
          Changed rows only
        </label>
        <label
          className={cn(
            'inline-flex cursor-pointer items-center gap-2 text-slate-700 dark:text-slate-200',
            query.column !== null && 'cursor-not-allowed opacity-50',
          )}
        >
          <input
            type="checkbox"
            className="checkbox"
            checked={changedColumnsOnly}
            disabled={query.column !== null}
            onChange={(event) => setChangedColumnsOnly(event.target.checked)}
          />
          Changed columns only
        </label>
        <label className="inline-flex items-center gap-2 text-slate-700 dark:text-slate-200">
          <span>Column</span>
          <select
            value={query.column ?? ''}
            onChange={(event) => refine({ column: event.target.value || null, changedOnly: true })}
            className="field w-auto py-1.5 pr-8"
          >
            <option value="">All columns</option>
            {changedTargets.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        {query.column !== null && (
          <button type="button" onClick={() => refine({ column: null })} className="btn-ghost btn-sm">
            <X className="h-3.5 w-3.5" />
            Clear focus
          </button>
        )}
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs tabular-nums text-slate-500 dark:text-slate-400" aria-live="polite">
            {rowRangeLabel(rows.offset, rows.items.length, rows.total)}
          </span>
          <button
            type="button"
            aria-label="Previous rows"
            disabled={rows.offset === 0 || fetching}
            onClick={() =>
              onQueryChange({ ...query, offset: clampOffset(rows.offset - rows.limit, rows.total, rows.limit) })
            }
            className="btn-secondary btn-sm px-2"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            aria-label="Next rows"
            disabled={pageEnd >= rows.total || fetching}
            onClick={() => onQueryChange({ ...query, offset: rows.offset + rows.limit })}
            className="btn-secondary btn-sm px-2"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      {rows.total === 0 ? (
        <div className="p-5">
          <EmptyState
            icon={<Rows3 className="h-6 w-6" />}
            title={query.changedOnly ? 'No changed values' : 'No rows'}
            description={
              query.changedOnly
                ? `Every exported cell${query.column ? ` in ${query.column}` : ''} matches your upload.`
                : 'This study has no data rows.'
            }
            action={
              query.changedOnly ? (
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={() => refine({ changedOnly: false, column: null })}
                >
                  Show all rows
                </button>
              ) : undefined
            }
          />
        </div>
      ) : visible.length === 0 ? (
        <div className="p-5">
          <EmptyState
            icon={<Rows3 className="h-6 w-6" />}
            title="No changed columns"
            description="No exported column has changed values."
            action={
              <button type="button" className="btn-secondary btn-sm" onClick={() => setChangedColumnsOnly(false)}>
                Show all columns
              </button>
            }
          />
        </div>
      ) : (
        <div
          tabIndex={0}
          role="region"
          aria-label="Changed values table"
          className={cn(
            'relative max-h-[36rem] overflow-auto transition-opacity focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary-500/40',
            fetching && 'opacity-60',
          )}
        >
          <table className="min-w-full border-separate border-spacing-0 text-xs">
            <caption className="sr-only">Exported rows; changed cells also show the uploaded value</caption>
            <thead>
              <tr>
                <th
                  scope="col"
                  className="sticky left-0 top-0 z-30 border-b border-r border-slate-200 bg-slate-50 px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400"
                >
                  Row
                </th>
                {visible.map((index) => {
                  const name = rows.columns[index];
                  return (
                    <th
                      key={name}
                      scope="col"
                      className="sticky top-0 z-20 whitespace-nowrap border-b border-slate-200 bg-slate-50 px-3 py-2 text-left align-bottom dark:border-slate-700 dark:bg-slate-800"
                    >
                      <span className="block font-mono text-[11px] font-semibold text-slate-800 dark:text-slate-100">
                        {name}
                      </span>
                      {sources[name] && (
                        <span className="block font-mono text-[10px] font-normal text-slate-500 dark:text-slate-400">
                          from {sources[name]}
                        </span>
                      )}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {rows.items.map((row) => {
                const changes = changesByColumn(row);
                return (
                  <tr key={row.line} className="group">
                    <th
                      scope="row"
                      className="sticky left-0 z-10 border-b border-r border-slate-100 bg-white px-3 py-2 text-right font-mono text-[11px] font-medium tabular-nums text-slate-500 group-hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400 dark:group-hover:bg-slate-800"
                    >
                      {row.line}
                    </th>
                    {visible.map((index) => {
                      const value = row.values[index];
                      const change = changes.get(index);
                      if (!change) {
                        return (
                          <td
                            key={index}
                            className="whitespace-nowrap border-b border-slate-100 px-3 py-2 text-slate-700 group-hover:bg-slate-50/80 dark:border-slate-800 dark:text-slate-300 dark:group-hover:bg-slate-800/50"
                          >
                            <CellText value={value} />
                          </td>
                        );
                      }
                      const reason = REASON_META[change.reason];
                      return (
                        <td
                          key={index}
                          className={cn(
                            'whitespace-nowrap border-b border-slate-100 px-3 py-1.5 dark:border-slate-800',
                            CHANGED_CELL[change.reason],
                          )}
                          title={`Uploaded: ${change.before || '(blank)'}\nExported: ${value || '(blank)'}\n${reason.label}: ${reason.hint}`}
                        >
                          <CellText value={value} className={cn('block font-semibold', CHANGED_TEXT[change.reason])} />
                          <span className="sr-only">
                            {`, changed from ${change.before || 'blank'} (${reason.label})`}
                          </span>
                          <span aria-hidden="true">
                            <CellText
                              value={change.before}
                              className="block text-[10px] text-rose-700 line-through decoration-rose-400/70 dark:text-rose-300"
                            />
                          </span>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-slate-100 px-5 py-3 text-[11px] text-slate-500 dark:border-slate-800 dark:text-slate-400">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-sm bg-emerald-100 ring-1 ring-emerald-300 dark:bg-emerald-500/20 dark:ring-emerald-500/40" />
          {REASON_META.ontology.label}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-sm bg-amber-100 ring-1 ring-amber-300 dark:bg-amber-500/20 dark:ring-amber-500/40" />
          {REASON_META.escaped.label}
        </span>
        {hasOtherChanges && (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-sm bg-sky-100 ring-1 ring-sky-300 dark:bg-sky-500/20 dark:ring-sky-500/40" />
            {REASON_META.other.label}
          </span>
        )}
        <span className="inline-flex items-center gap-1.5">
          <span className="font-mono text-rose-700 line-through decoration-rose-400/70 dark:text-rose-300">
            value
          </span>
          Uploaded value
        </span>
      </div>
    </Card>
  );
}
