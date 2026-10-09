import type { BadgeTone } from '../../components/ui/Badge';
import type {
  ExportCellChange,
  ExportChangeReason,
  ExportColumnAction,
  ExportColumnChange,
  ExportDropReason,
  ExportMappingStatus,
  ExportPreviewRow,
} from '../../api/types';

export const PAGE_SIZE = 50;

export const ACTION_META: Record<ExportColumnAction, { label: string; tone: BadgeTone; hint: string }> = {
  renamed: { label: 'Renamed', tone: 'primary', hint: 'Exported under its schema field name.' },
  matched: { label: 'Matches schema', tone: 'green', hint: 'Already uses the schema field name.' },
  kept: {
    label: 'Kept as uploaded',
    tone: 'slate',
    hint: 'Mapping rejected, so the column is exported unchanged under its original name.',
  },
  dropped: { label: 'Not exported', tone: 'rose', hint: 'Left out of the harmonized CSV.' },
};

export const MAPPING_META: Record<ExportMappingStatus, { label: string; tone: BadgeTone }> = {
  accepted: { label: 'Accepted', tone: 'green' },
  pending: { label: 'Pending review', tone: 'amber' },
  rejected: { label: 'Rejected', tone: 'rose' },
  unmapped: { label: 'No mapping', tone: 'slate' },
};

export const DROP_REASON_LABEL: Record<ExportDropReason, string> = {
  no_target: 'Not mapped to a schema field',
  duplicate_target: 'Another column already maps to the same field',
  name_conflict: 'Another column is exported under this name',
};

/** Why a column is left out of the export, naming the column that took its
 *  place when there is one ("Gender already maps to sex"). */
export function dropExplanation(column: ExportColumnChange, columns: ExportColumnChange[]): string {
  if (!column.drop_reason) return '';
  const winner = column.conflicts_with ? columns.find((c) => c.source === column.conflicts_with) : undefined;
  if (winner?.target && column.drop_reason === 'duplicate_target') {
    return `${winner.source} already maps to ${winner.target}`;
  }
  if (winner?.target && column.drop_reason === 'name_conflict') {
    return `${winner.source} is exported as ${winner.target}`;
  }
  return DROP_REASON_LABEL[column.drop_reason];
}

/** One-line reason behind each drop rule, for a tooltip. */
export const DROP_REASON_HINT: Record<ExportDropReason, string> = {
  no_target: 'Only columns mapped to a schema field are exported.',
  duplicate_target:
    'A CSV cannot repeat a column name, so one column per field is exported: your accepted or edited mappings first, then ones the engine accepted on its own, then higher confidence, then the first column in your file.',
  name_conflict: 'Its mapping was rejected, but its original name is already used by a mapped column.',
};

export const REASON_META: Record<ExportChangeReason, { label: string; tone: BadgeTone; hint: string }> = {
  ontology: { label: 'Ontology term', tone: 'teal', hint: 'Rewritten to its confirmed ontology term.' },
  escaped: {
    label: 'Spreadsheet-safe',
    tone: 'amber',
    hint: 'Prefixed with an apostrophe so spreadsheets show it as text, not a formula.',
  },
  other: { label: 'Changed', tone: 'slate', hint: 'Differs from the uploaded value.' },
};

export type ColumnFilter = 'all' | 'renamed' | 'unchanged' | 'dropped';

export function matchesColumnFilter(column: ExportColumnChange, filter: ColumnFilter): boolean {
  switch (filter) {
    case 'renamed':
      return column.action === 'renamed';
    case 'unchanged':
      return column.action === 'matched' || column.action === 'kept';
    case 'dropped':
      return column.action === 'dropped';
    default:
      return true;
  }
}

export function columnFilterCounts(columns: ExportColumnChange[]): Record<ColumnFilter, number> {
  const counts: Record<ColumnFilter, number> = { all: columns.length, renamed: 0, unchanged: 0, dropped: 0 };
  for (const column of columns) {
    for (const filter of ['renamed', 'unchanged', 'dropped'] as const) {
      if (matchesColumnFilter(column, filter)) counts[filter] += 1;
    }
  }
  return counts;
}

/** Columns matching a filter tab and a case-insensitive name search. */
export function filterColumns(
  columns: ExportColumnChange[],
  filter: ColumnFilter,
  search: string,
): ExportColumnChange[] {
  const needle = search.trim().toLowerCase();
  return columns.filter(
    (column) =>
      matchesColumnFilter(column, filter) &&
      (!needle ||
        column.source.toLowerCase().includes(needle) ||
        (column.target ?? '').toLowerCase().includes(needle)),
  );
}

/** Share of ``whole`` as a compact percentage ("0%", "<0.1%", "12.5%", "100%"). */
export function formatPercent(part: number, whole: number): string {
  if (whole <= 0 || part <= 0) return '0%';
  const value = (part / whole) * 100;
  if (value < 0.1) return '<0.1%';
  return `${Number(value.toFixed(1))}%`;
}

export function rowRangeLabel(offset: number, shown: number, total: number): string {
  if (total === 0 || shown === 0) return 'No rows';
  return `Rows ${(offset + 1).toLocaleString()}–${(offset + shown).toLocaleString()} of ${total.toLocaleString()}`;
}

/** Changed cells of a row, keyed by column index. */
export function changesByColumn(row: ExportPreviewRow): Map<number, ExportCellChange> {
  return new Map(row.changes.map((change) => [change.column, change]));
}

/** Indexes of the grid columns to display. A focused column wins; otherwise
 *  optionally only the changed columns (see {@link changedColumnNames}). */
export function visibleColumnIndexes(
  columns: string[],
  changed: ReadonlySet<string>,
  options: { changedOnly: boolean; focus: string | null },
): number[] {
  if (options.focus !== null) {
    const index = columns.indexOf(options.focus);
    return index === -1 ? [] : [index];
  }
  const all = columns.map((_, index) => index);
  return options.changedOnly ? all.filter((index) => changed.has(columns[index])) : all;
}

/** Export columns that differ from the upload: renamed by their mapping, or
 *  holding at least one changed value. */
export function changedColumnNames(columns: ExportColumnChange[]): Set<string> {
  const names = new Set<string>();
  for (const column of columns) {
    if (column.target && (column.action === 'renamed' || column.changed_cells > 0)) names.add(column.target);
  }
  return names;
}

/** Distinct before → after changes in a column, listed or not. */
export function distinctValueChanges(column: ExportColumnChange): number {
  return column.value_changes.length + column.more_value_changes;
}

/** Export column → original column name, for renamed columns only. */
export function renamedFrom(columns: ExportColumnChange[]): Record<string, string> {
  const sources: Record<string, string> = {};
  for (const column of columns) {
    if (column.target && column.target !== column.source) sources[column.target] = column.source;
  }
  return sources;
}

/** Changed-cell counts keyed by export column name. */
export function changedCellsByTarget(columns: ExportColumnChange[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const column of columns) {
    if (column.target) counts[column.target] = column.changed_cells;
  }
  return counts;
}

export function clampOffset(offset: number, total: number, pageSize: number): number {
  if (total <= 0) return 0;
  const lastPageStart = Math.floor((total - 1) / pageSize) * pageSize;
  return Math.min(Math.max(0, offset), lastPageStart);
}

/** "1 column" / "3 columns" with locale-formatted counts. */
export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${count.toLocaleString()} ${count === 1 ? singular : plural}`;
}
