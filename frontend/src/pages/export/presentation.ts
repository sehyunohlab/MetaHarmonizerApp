import type { ExportCellChange, ExportChangeReason, ExportColumnChange, ExportPreviewRow } from '../../api/types';

export const PAGE_SIZE = 50;

export const REASON_META: Record<ExportChangeReason, { label: string; hint: string }> = {
  ontology: { label: 'Ontology term', hint: 'Rewritten to its confirmed ontology term.' },
  escaped: {
    label: 'Spreadsheet-safe',
    hint: 'Prefixed with an apostrophe so spreadsheets show it as text, not a formula.',
  },
  other: { label: 'Changed', hint: 'Differs from the uploaded value.' },
};

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
