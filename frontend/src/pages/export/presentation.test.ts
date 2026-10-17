import { describe, expect, it } from 'vitest';
import type { ExportColumnChange } from '../../api/types';
import {
  changedCellsByTarget,
  changedColumnNames,
  changesByColumn,
  clampOffset,
  describeColumnChange,
  formatPercent,
  normalizeSelection,
  pluralize,
  renamedFrom,
  rowRangeLabel,
  selectionLabel,
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

  it('shows every column, or the chosen ones in export order', () => {
    expect(visibleColumnIndexes(gridColumns, null)).toEqual([0, 1, 2]);
    expect(visibleColumnIndexes(gridColumns, ['age', 'sample_id'])).toEqual([0, 2]);
    expect(visibleColumnIndexes(gridColumns, ['age', 'missing'])).toEqual([2]);
    expect(visibleColumnIndexes(gridColumns, [])).toEqual([]);
  });

  it('keeps a column choice in export order, and all of them as no filter', () => {
    expect(normalizeSelection(gridColumns, ['age', 'sample_id'])).toEqual(['sample_id', 'age']);
    expect(normalizeSelection(gridColumns, new Set(['sex', 'missing']))).toEqual(['sex']);
    expect(normalizeSelection(gridColumns, [])).toEqual([]);
    expect(normalizeSelection(gridColumns, ['age', 'sex', 'sample_id'])).toBeNull();
  });

  it('labels the column choice', () => {
    expect(selectionLabel(null, 59)).toBe('All');
    expect(selectionLabel([], 59)).toBe('None');
    expect(selectionLabel(['disease'], 59)).toBe('disease');
    expect(selectionLabel(['disease', 'sex', 'age'], 59)).toBe('3 of 59');
    expect(selectionLabel(['a', 'b'], 2)).toBe('All');
  });

  it('describes how each column changed', () => {
    expect(describeColumnChange('study_name', 0)).toBe('renamed from study_name');
    expect(describeColumnChange(undefined, 681)).toBe(`${(681).toLocaleString()} values changed`);
    expect(describeColumnChange('Gender', 1)).toBe('renamed from Gender · 1 value changed');
    expect(describeColumnChange(undefined, 0)).toBe('unchanged');
  });

  it('counts a renamed column as changed even when its values are not', () => {
    const study = [
      column({ source: 'subject_id', target: 'PATIENT_ID' }),
      column({ source: 'disease', target: 'disease', action: 'matched', changed_cells: 681 }),
      column({ source: 'country', target: 'country', action: 'matched' }),
      column({ source: 'bmi', target: 'bmi', action: 'kept', mapping_status: 'rejected' }),
      column({ source: 'notes', target: null, action: 'dropped', drop_reason: 'no_target' }),
    ];
    expect(changedColumnNames(study)).toEqual(new Set(['PATIENT_ID', 'disease']));
  });

  it('picks every renamed column and every column with changed values as "Changed"', () => {
    // 19 schema renames and one column whose values became ontology terms.
    const renamed = Array.from({ length: 19 }, (_, i) => column({ source: `col_${i}`, target: `field_${i}` }));
    const site = column({ source: 'site', target: 'site', action: 'matched', changed_cells: 60 });
    const same = column({ source: 'country', target: 'country', action: 'matched' });
    const study = [...renamed, site, same];
    const gridNames = study.map((c) => c.target!);

    const shown = visibleColumnIndexes(gridNames, normalizeSelection(gridNames, changedColumnNames(study)));

    expect(shown.map((index) => gridNames[index])).toEqual([...renamed.map((c) => c.target), 'site']);
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
