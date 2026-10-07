import { Fragment, useId, useState } from 'react';
import { ArrowRight, ChevronDown, Columns3, Search } from 'lucide-react';
import type { ExportColumnChange } from '../../api/types';
import Badge from '../../components/ui/Badge';
import { Card, CardHeader } from '../../components/ui/Card';
import SegmentedControl from '../../components/ui/SegmentedControl';
import { Table, TBody, Td, Th, THead } from '../../components/ui/Table';
import { cn } from '../../lib/cn';
import {
  ACTION_META,
  DROP_REASON_HINT,
  MAPPING_META,
  columnFilterCounts,
  dropExplanation,
  filterColumns,
  pluralize,
  type ColumnFilter,
} from './presentation';
import { ValueChangeList } from './ValueChangeList';

export function ColumnChangesCard({
  columns,
  onShowRows,
}: {
  columns: ExportColumnChange[];
  onShowRows: (target: string) => void;
}) {
  const [filter, setFilter] = useState<ColumnFilter>('all');
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const idPrefix = useId();
  const counts = columnFilterCounts(columns);
  const shown = filterColumns(columns, filter, search);

  return (
    <Card>
      <CardHeader
        icon={<Columns3 className="h-4 w-4" />}
        title="Column changes"
        description="How each original column appears in the harmonized CSV."
      />
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3 dark:border-slate-800">
        <div className="max-w-full overflow-x-auto">
          <SegmentedControl<ColumnFilter>
            size="sm"
            value={filter}
            onChange={setFilter}
            className="whitespace-nowrap"
            segments={[
              { value: 'all', label: 'All', count: counts.all, tone: 'slate' },
              { value: 'renamed', label: 'Renamed', count: counts.renamed },
              { value: 'unchanged', label: 'Same name', count: counts.unchanged, tone: 'emerald' },
              { value: 'dropped', label: 'Not exported', count: counts.dropped, tone: 'rose' },
            ]}
          />
        </div>
        <label className="relative block w-full sm:w-64">
          <span className="sr-only">Search columns</span>
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
            aria-hidden="true"
          />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search columns…"
            className="field py-2 pl-9"
          />
        </label>
      </div>

      <div
        tabIndex={0}
        role="region"
        aria-label="Column changes table"
        className="relative max-h-[30rem] overflow-auto focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary-500/40"
      >
        <Table className="min-w-[44rem]">
          <caption className="sr-only">Original columns and how they appear in the harmonized CSV</caption>
          <THead className="sticky top-0 z-10 bg-slate-50 dark:bg-slate-800">
            <tr>
              <Th scope="col">Original column</Th>
              <Th scope="col">Export column</Th>
              <Th scope="col">Change</Th>
              <Th scope="col">Mapping</Th>
              <Th scope="col" className="text-right">
                Values changed
              </Th>
            </tr>
          </THead>
          <TBody>
            {shown.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-10 text-center text-sm text-slate-500 dark:text-slate-400">
                  No columns match.
                </td>
              </tr>
            )}
            {shown.map((column, index) => {
              const open = expanded === column.source;
              const panelId = `${idPrefix}-values-${index}`;
              const action = ACTION_META[column.action];
              const mapping = MAPPING_META[column.mapping_status];
              return (
                <Fragment key={column.source}>
                  <tr className={cn('transition-colors', open && 'bg-slate-50/80 dark:bg-slate-800/40')}>
                    <Td>
                      <code className="font-mono text-xs text-slate-800 dark:text-slate-200">{column.source}</code>
                    </Td>
                    <Td>
                      {column.target ? (
                        <span className="inline-flex items-center gap-1.5">
                          <ArrowRight className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden="true" />
                          <code className="font-mono text-xs font-semibold text-slate-900 dark:text-slate-100">
                            {column.target}
                          </code>
                        </span>
                      ) : (
                        <span className="text-xs text-slate-500 dark:text-slate-400">
                          <span aria-hidden="true">—</span>
                          <span className="sr-only">Not exported</span>
                        </span>
                      )}
                    </Td>
                    <Td>
                      <span title={action.hint}>
                        <Badge tone={action.tone}>{action.label}</Badge>
                      </span>
                      {column.drop_reason && (
                        <p
                          className="mt-1 text-[11px] text-slate-500 dark:text-slate-400"
                          title={DROP_REASON_HINT[column.drop_reason]}
                        >
                          {dropExplanation(column, columns)}
                        </p>
                      )}
                    </Td>
                    <Td>
                      <Badge tone={mapping.tone}>{mapping.label}</Badge>
                    </Td>
                    <Td className="text-right">
                      {column.changed_cells > 0 ? (
                        <button
                          type="button"
                          aria-expanded={open}
                          aria-controls={panelId}
                          onClick={() => setExpanded(open ? null : column.source)}
                          className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-primary-700 transition hover:bg-primary-50 dark:text-primary-300 dark:hover:bg-primary-500/10"
                        >
                          {pluralize(column.changed_cells, 'cell')}
                          <ChevronDown
                            className={cn('h-3.5 w-3.5 transition-transform', open && 'rotate-180')}
                            aria-hidden="true"
                          />
                        </button>
                      ) : (
                        <span className="text-xs text-slate-500 dark:text-slate-400">
                          <span aria-hidden="true">—</span>
                          <span className="sr-only">No changes</span>
                        </span>
                      )}
                    </Td>
                  </tr>
                  {open && column.target && (
                    <tr>
                      <td id={panelId} colSpan={5} className="bg-slate-50/80 px-5 pb-4 pt-1 dark:bg-slate-800/40">
                        <ValueChangeList column={column} onShowRows={() => onShowRows(column.target!)} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </TBody>
        </Table>
      </div>
    </Card>
  );
}
