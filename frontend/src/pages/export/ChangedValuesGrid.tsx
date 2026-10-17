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
import { ColumnPicker } from './ColumnPicker';
import {
  MULTI_VALUE_DELIMITER,
  REASON_META,
  changedCellsByTarget,
  changedColumnNames,
  changesByColumn,
  clampOffset,
  mergedFrom,
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

function FilterCount({ value }: { value: number }) {
  return (
    <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-slate-600 dark:bg-slate-800 dark:text-slate-300">
      {value.toLocaleString()}
    </span>
  );
}

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
  const changedCells = changedCellsByTarget(columns);
  const changedColumns = changedColumnNames(columns);
  const sources = renamedFrom(columns);
  const merges = mergedFrom(columns);
  const hasMerged = rows.columns.some((name) => merges[name]);
  const selection = query.columns;
  const visible = visibleColumnIndexes(rows.columns, selection);
  const noneChosen = selection !== null && selection.length === 0;
  const hasOtherChanges = rows.items.some((row) => row.changes.some((change) => change.reason === 'other'));
  const pageEnd = rows.offset + rows.items.length;
  const refine = (patch: Partial<ExportPreviewQuery>) => onQueryChange({ ...query, offset: 0, ...patch });
  // Hiding columns only re-pages when it also changes which rows are kept.
  const chooseColumns = (next: string[] | null) =>
    onQueryChange({ ...query, columns: next, offset: query.changedOnly ? 0 : query.offset });

  return (
    <Card>
      <CardHeader
        icon={<Rows3 className="h-4 w-4" />}
        title="Harmonized metadata"
        description={`Every exported value next to your upload. Renamed columns and changed cells show the uploaded name or value struck through; merged columns list each row's values separated by ${MULTI_VALUE_DELIMITER}.`}
        action={fetching ? <Spinner className="h-4 w-4 text-slate-400" /> : undefined}
      />

      <div className="flex flex-wrap items-center gap-x-5 gap-y-3 border-b border-slate-100 px-5 py-3 text-sm dark:border-slate-800">
        <label
          className="inline-flex cursor-pointer items-center gap-2 text-slate-700 dark:text-slate-200"
          title="Rows with a changed value in the shown columns"
        >
          <input
            type="checkbox"
            className="checkbox"
            checked={query.changedOnly}
            onChange={(event) => refine({ changedOnly: event.target.checked })}
          />
          Changed rows only
          <FilterCount value={noneChosen ? 0 : rows.changed_total} />
        </label>
        <div className="flex items-center gap-2">
          <ColumnPicker
            columns={rows.columns}
            selected={selection}
            changed={changedColumns}
            renamedFrom={sources}
            mergedFrom={merges}
            changedCells={changedCells}
            onChange={chooseColumns}
          />
          {selection !== null && (
            <button type="button" onClick={() => chooseColumns(null)} className="btn-ghost btn-sm">
              <X className="h-3.5 w-3.5" />
              Show all columns
            </button>
          )}
        </div>
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

      {rows.columns.length === 0 ? (
        <div className="p-5">
          <EmptyState
            icon={<Rows3 className="h-6 w-6" />}
            title="No exported columns"
            description="No uploaded column is mapped to a schema field yet, so the harmonized CSV has no columns."
          />
        </div>
      ) : visible.length === 0 ? (
        <div className="p-5">
          <EmptyState
            icon={<Rows3 className="h-6 w-6" />}
            title="No columns selected"
            description="Choose the columns to show from the Columns list."
            action={
              <button type="button" className="btn-secondary btn-sm" onClick={() => chooseColumns(null)}>
                Show all columns
              </button>
            }
          />
        </div>
      ) : rows.total === 0 ? (
        <div className="p-5">
          <EmptyState
            icon={<Rows3 className="h-6 w-6" />}
            title={query.changedOnly ? 'No changed values' : 'No rows'}
            description={
              query.changedOnly
                ? `Every exported cell${selection ? ' in the shown columns' : ''} matches your upload.`
                : 'This study has no data rows.'
            }
            action={
              query.changedOnly ? (
                <button type="button" className="btn-secondary btn-sm" onClick={() => refine({ changedOnly: false })}>
                  Show all rows
                </button>
              ) : undefined
            }
          />
        </div>
      ) : (
        <div
          tabIndex={0}
          role="region"
          aria-label="Harmonized metadata table"
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
                  const from = sources[name];
                  const merged = merges[name];
                  return (
                    <th
                      key={name}
                      scope="col"
                      title={
                        from
                          ? `Renamed from ${from}`
                          : merged
                            ? `Merged from ${merged.join(', ')}; values separated by ${MULTI_VALUE_DELIMITER}`
                            : undefined
                      }
                      className={cn(
                        'sticky top-0 z-20 whitespace-nowrap border-b px-3 py-2 text-left align-bottom',
                        from
                          ? 'border-primary-200 bg-primary-50 dark:border-primary-800 dark:bg-primary-950'
                          : merged
                            ? 'border-violet-200 bg-violet-50 dark:border-violet-800 dark:bg-violet-950'
                            : 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800',
                      )}
                    >
                      <span
                        className={cn(
                          'block font-mono text-[11px] font-semibold',
                          from
                            ? 'text-primary-900 dark:text-primary-100'
                            : merged
                              ? 'text-violet-900 dark:text-violet-100'
                              : 'text-slate-800 dark:text-slate-100',
                        )}
                      >
                        {name}
                      </span>
                      {from && (
                        <>
                          <span className="sr-only">{`, renamed from ${from}`}</span>
                          <span
                            aria-hidden="true"
                            className="block font-mono text-[10px] font-normal text-rose-700 line-through decoration-rose-400/70 dark:text-rose-300"
                          >
                            {from}
                          </span>
                        </>
                      )}
                      {merged && (
                        <>
                          <span className="sr-only">{`, merged from ${merged.join(' and ')}`}</span>
                          <span
                            aria-hidden="true"
                            className="block font-mono text-[10px] font-normal text-violet-700 dark:text-violet-300"
                          >
                            {merged.join(' + ')}
                          </span>
                        </>
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
          <span className="h-3 w-3 rounded-sm bg-primary-100 ring-1 ring-primary-300 dark:bg-primary-500/20 dark:ring-primary-500/40" />
          Renamed column
        </span>
        {hasMerged && (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-sm bg-violet-100 ring-1 ring-violet-300 dark:bg-violet-500/20 dark:ring-violet-500/40" />
            Merged column
          </span>
        )}
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
          Uploaded value or name
        </span>
      </div>
    </Card>
  );
}
