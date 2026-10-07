import { describe, expect, it } from 'vitest';
import type { ExportColumnChange } from '../../api/types';
import {
  changedCellsByTarget,
  changesByColumn,
  clampOffset,
  columnFilterCounts,
  dropExplanation,
  filterColumns,
  formatPercent,
  pluralize,
  renamedFrom,
  rowRangeLabel,
  visibleColumnIndexes,
} from './presentation';

const column = (overrides: Partial<ExportColumnChange>): ExportColumnChange => ({
  source: 'src',
  target: 'dst',
  action: 'renamed',
  mapping_status: 'accepted',
  drop_reason: null,
  conflicts_with: null,
  changed_cells: 0,
  value_changes: [],
  more_value_changes: 0,
  ...overrides,
});

const columns: ExportColumnChange[] = [
  column({ source: 'gender', target: 'sex', changed_cells: 12 }),
  column({ source: 'country', target: 'country', action: 'matched' }),
  column({ source: 'bmi', target: 'bmi', action: 'kept', mapping_status: 'rejected' }),
  column({ source: 'notes', target: null, action: 'dropped', mapping_status: 'unmapped', drop_reason: 'no_target' }),
];

describe('column filters', () => {
  it('counts each tab', () => {
    expect(columnFilterCounts(columns)).toEqual({ all: 4, renamed: 1, unchanged: 2, dropped: 1 });
  });

  it('filters by tab and searches source and export names', () => {
    expect(filterColumns(columns, 'unchanged', '').map((c) => c.source)).toEqual(['country', 'bmi']);
    expect(filterColumns(columns, 'all', 'SEX').map((c) => c.source)).toEqual(['gender']);
    expect(filterColumns(columns, 'dropped', 'note').map((c) => c.source)).toEqual(['notes']);
    expect(filterColumns(columns, 'renamed', 'zzz')).toEqual([]);
  });
});

describe('dropExplanation', () => {
  const gender = column({ source: 'Gender', target: 'sex' });
  const ageAtDx = column({ source: 'Age_at_Dx', target: 'age' });
  const dropped = (overrides: Partial<ExportColumnChange>) =>
    column({ target: null, action: 'dropped', ...overrides });

  it('names the column that took the field', () => {
    const duplicate = dropped({ source: 'Sex_Reported', drop_reason: 'duplicate_target', conflicts_with: 'Gender' });
    expect(dropExplanation(duplicate, [gender, duplicate])).toBe('Gender already maps to sex');
  });

  it('names the column exported under the same name', () => {
    const conflict = dropped({
      source: 'age',
      mapping_status: 'rejected',
      drop_reason: 'name_conflict',
      conflicts_with: 'Age_at_Dx',
    });
    expect(dropExplanation(conflict, [ageAtDx, conflict])).toBe('Age_at_Dx is exported as age');
  });

  it('falls back to the generic reason', () => {
    const unmapped = dropped({ source: 'Notes', mapping_status: 'unmapped', drop_reason: 'no_target' });
    expect(dropExplanation(unmapped, [unmapped])).toBe('Not mapped to a schema field');
    const orphan = dropped({ source: 'x', drop_reason: 'duplicate_target', conflicts_with: 'missing' });
    expect(dropExplanation(orphan, [orphan])).toBe('Another column already maps to the same field');
    expect(dropExplanation(gender, [gender])).toBe('');
  });
});

describe('formatPercent', () => {
  it('formats compact shares', () => {
    expect(formatPercent(0, 10)).toBe('0%');
    expect(formatPercent(5, 0)).toBe('0%');
    expect(formatPercent(1, 5000)).toBe('<0.1%');
    expect(formatPercent(1, 8)).toBe('12.5%');
    expect(formatPercent(1, 3)).toBe('33.3%');
    expect(formatPercent(4, 4)).toBe('100%');
  });
});

describe('rowRangeLabel', () => {
  it('describes the visible window', () => {
    expect(rowRangeLabel(0, 50, 110)).toBe('Rows 1–50 of 110');
    expect(rowRangeLabel(100, 10, 110)).toBe('Rows 101–110 of 110');
    expect(rowRangeLabel(0, 0, 0)).toBe('No rows');
  });
});

describe('grid helpers', () => {
  const gridColumns = ['sample_id', 'sex', 'age'];
  const counts = { sample_id: 0, sex: 3, age: 1 };

  it('shows a focused column on its own', () => {
    expect(visibleColumnIndexes(gridColumns, counts, { changedOnly: true, focus: 'age' })).toEqual([2]);
    expect(visibleColumnIndexes(gridColumns, counts, { changedOnly: false, focus: 'missing' })).toEqual([]);
  });

  it('hides unchanged columns on request', () => {
    expect(visibleColumnIndexes(gridColumns, counts, { changedOnly: true, focus: null })).toEqual([1, 2]);
    expect(visibleColumnIndexes(gridColumns, counts, { changedOnly: false, focus: null })).toEqual([0, 1, 2]);
  });

  it('indexes row changes by column', () => {
    const map = changesByColumn({
      line: 4,
      values: ['S4', 'Female', '7'],
      changes: [{ column: 1, before: 'F', reason: 'ontology' }],
    });
    expect(map.get(1)).toEqual({ column: 1, before: 'F', reason: 'ontology' });
    expect(map.has(0)).toBe(false);
  });

  it('maps export names back to renamed sources and change counts', () => {
    expect(renamedFrom(columns)).toEqual({ sex: 'gender' });
    expect(changedCellsByTarget(columns)).toEqual({ sex: 12, country: 0, bmi: 0 });
  });
});

describe('clampOffset', () => {
  it('keeps the offset on an existing page', () => {
    expect(clampOffset(0, 0, 50)).toBe(0);
    expect(clampOffset(-50, 120, 50)).toBe(0);
    expect(clampOffset(150, 120, 50)).toBe(100);
    expect(clampOffset(50, 120, 50)).toBe(50);
  });
});

describe('pluralize', () => {
  it('picks the singular or plural form', () => {
    expect(pluralize(1, 'column')).toBe('1 column');
    expect(pluralize(3, 'column')).toBe('3 columns');
    expect(pluralize(1200, 'cell')).toBe(`${(1200).toLocaleString()} cells`);
    expect(pluralize(2, 'entry', 'entries')).toBe('2 entries');
  });
});
