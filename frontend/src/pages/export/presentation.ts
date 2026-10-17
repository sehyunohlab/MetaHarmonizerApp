import type { ExportCellChange, ExportChangeReason, ExportColumnChange, ExportPreviewRow } from '../../api/types';

export const PAGE_SIZE = 50;

/** Separates the values of columns merged into one (see the backend exporter). */
export const MULTI_VALUE_DELIMITER = '<;>';

export const REASON_META: Record<ExportChangeReason, { label: string; hint: string }> = {
  ontology: { label: 'Ontology term', hint: 'Rewritten to its confirmed ontology term.' },
  escaped: {
    label: 'Spreadsheet-safe',
    hint: 'Prefixed with an apostrophe so spreadsheets show it as text, not a formula.',
  },
  other: {
    label: 'Changed',
    hint: 'Differs from the uploaded value. A value without a confirmed term is left out of its curated column and kept in its original_…_value column.',
  },
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

/** Indexes of the grid columns to display: every column when ``selected`` is
 *  null, otherwise the chosen ones in export order. */
export function visibleColumnIndexes(columns: string[], selected: readonly string[] | null): number[] {
  if (selected === null) return columns.map((_, index) => index);
  const chosen = new Set(selected);
  return columns.flatMap((name, index) => (chosen.has(name) ? [index] : []));
}

/** A column choice in export order, or null when it covers every column. */
export function normalizeSelection(columns: string[], picked: Iterable<string>): string[] | null {
  const chosen = new Set(picked);
  const ordered = columns.filter((name) => chosen.has(name));
  return ordered.length === columns.length ? null : ordered;
}

/** What the column picker shows: "All", "None", the one column, or "3 of 21". */
export function selectionLabel(selected: readonly string[] | null, total: number): string {
  if (selected === null || (total > 0 && selected.length >= total)) return 'All';
  if (selected.length === 0) return 'None';
  if (selected.length === 1) return selected[0];
  return `${selected.length.toLocaleString()} of ${total.toLocaleString()}`;
}

/** Uploaded names shown before a long merge is summarized as "and N more". */
const SHOWN_MERGED_NAMES = 2;

/** The columns merged into one, short enough for a column header:
 *  "a + b + c", or "a + b + 16 more" past three. */
export function mergedLabel(names: readonly string[]): string {
  if (names.length <= SHOWN_MERGED_NAMES + 1) return names.join(' + ');
  return `${names.slice(0, SHOWN_MERGED_NAMES).join(' + ')} + ${names.length - SHOWN_MERGED_NAMES} more`;
}

/** The columns merged into one, as words: "a and b", "a, b and c", or
 *  "18 columns: a, b and 16 more". */
export function mergedPhrase(names: readonly string[]): string {
  if (names.length <= SHOWN_MERGED_NAMES + 1) {
    return names.length < 2 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
  }
  const shown = names.slice(0, SHOWN_MERGED_NAMES).join(', ');
  return `${names.length.toLocaleString()} columns: ${shown} and ${names.length - SHOWN_MERGED_NAMES} more`;
}

/** How an export column differs from the upload, for the column picker. */
export function describeColumnChange(
  renamedFrom: string | undefined,
  changedCells: number,
  mergedFrom: readonly string[] = [],
): string {
  const parts = [
    ...(renamedFrom ? [`renamed from ${renamedFrom}`] : []),
    ...(mergedFrom.length > 0 ? [`merged from ${mergedPhrase(mergedFrom)}`] : []),
    ...(changedCells > 0 ? [`${pluralize(changedCells, 'value')} changed`] : []),
  ];
  return parts.length > 0 ? parts.join(' · ') : 'unchanged';
}

/** The summary's column hint: merges and columns left out, if any. */
export function columnsHint(merged: number, mergedInto: number, dropped: number): string {
  const parts = [
    ...(merged > 0 ? [`${merged.toLocaleString()} merged into ${pluralize(mergedInto, 'column')}`] : []),
    ...(dropped > 0 ? [`${dropped.toLocaleString()} not exported`] : []),
  ];
  return parts.length > 0 ? parts.join(' · ') : 'Every column is exported';
}

/** Export columns that differ from the upload: renamed or merged by their
 *  mapping, or holding at least one changed value. */
export function changedColumnNames(columns: ExportColumnChange[]): Set<string> {
  const names = new Set<string>();
  for (const column of columns) {
    if (column.target && (column.action === 'renamed' || column.action === 'merged' || column.changed_cells > 0)) {
      names.add(column.target);
    }
  }
  return names;
}

/** Export column → original column name, for renamed columns only. */
export function renamedFrom(columns: ExportColumnChange[]): Record<string, string> {
  const sources: Record<string, string> = {};
  for (const column of columns) {
    if (column.target && column.action === 'renamed') sources[column.target] = column.source;
  }
  return sources;
}

/** Export column → the uploaded columns merged into it, in upload order. */
export function mergedFrom(columns: ExportColumnChange[]): Record<string, string[]> {
  const sources: Record<string, string[]> = {};
  for (const column of columns) {
    if (column.target && column.action === 'merged') (sources[column.target] ??= []).push(column.source);
  }
  return sources;
}

/** What each companion column of a curated field holds, keyed by export name.
 *  A field mapped to ontology terms is exported as the lab's four columns (see
 *  the backend exporter): ``curated_<f>`` with its ``original_<f>_value``,
 *  ``curated_<f>_ontology_term_id`` and ``curated_<f>_source``. */
export function companionColumns(columns: ExportColumnChange[], exported: readonly string[]): Record<string, string> {
  const present = new Set(exported);
  const described: Record<string, string> = {};
  for (const column of columns) {
    const curated = column.target;
    if (!curated?.startsWith('curated_')) continue;
    const field = curated.slice('curated_'.length);
    const companions: [string, string][] = [
      [`original_${field}_value`, `uploaded values of ${curated}`],
      [`curated_${field}_ontology_term_id`, `ontology term ids of ${curated}`],
      [`curated_${field}_source`, `uploaded columns of ${curated}`],
    ];
    if (!companions.every(([name]) => present.has(name))) continue;
    for (const [name, text] of companions) described[name] = text;
  }
  return described;
}

/** Changed-cell counts keyed by export column name (a merged column's on its first source). */
export function changedCellsByTarget(columns: ExportColumnChange[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const column of columns) {
    if (column.target) counts[column.target] = (counts[column.target] ?? 0) + column.changed_cells;
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
