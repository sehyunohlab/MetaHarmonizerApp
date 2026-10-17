import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getExportPreview } from './client';
import { DEMO_STUDY_ID, guestFixture } from './guestFixtures';
import { setGuestMode } from './http';
import type { ExportPreview, ExportPreviewQuery } from './types';

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
  setGuestMode(true);
});

afterEach(() => {
  setGuestMode(false);
  fetchMock.mockReset();
  vi.unstubAllGlobals();
});

const preview = (query: Partial<ExportPreviewQuery> = {}): Promise<ExportPreview> =>
  getExportPreview(DEMO_STUDY_ID, { offset: 0, limit: 50, changedOnly: false, columns: null, ...query });

describe('guest export preview', () => {
  it('is served from the fixture without touching the network', async () => {
    const data = await preview();
    expect(data.study_id).toBe(DEMO_STUDY_ID);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('has a summary consistent with its columns', async () => {
    const { summary, columns, rows } = await preview();
    const exported = columns.filter((c) => c.target !== null);

    expect(summary.columns_before).toBe(columns.length);
    expect(summary.columns_after).toBe(exported.length);
    expect(rows.columns).toEqual(exported.map((c) => c.target));
    expect(summary.renamed + summary.matched + summary.kept + summary.dropped).toBe(columns.length);
    expect(summary.pending).toBe(exported.filter((c) => c.mapping_status === 'pending').length);
    expect(summary.compared_cells).toBe(summary.rows * summary.columns_after);
    expect(summary.changed_cells).toBe(columns.reduce((sum, c) => sum + c.changed_cells, 0));
    for (const column of columns) {
      expect(column.value_changes.reduce((sum, v) => sum + v.count, 0)).toBe(column.changed_cells);
      expect(column.drop_reason === null).toBe(column.target !== null);
    }
  });

  it('lists only changed rows when changed_only is on, with valid change cells', async () => {
    const { summary, rows } = await preview({ changedOnly: true, limit: 200 });
    expect(rows.total).toBe(summary.changed_rows);
    expect(rows.changed_total).toBe(summary.changed_rows);
    expect(rows.items).toHaveLength(Math.min(200, rows.total));
    for (const row of rows.items) {
      expect(row.values).toHaveLength(rows.columns.length);
      expect(row.changes.length).toBeGreaterThan(0);
      for (const change of row.changes) {
        expect(change.column).toBeLessThan(rows.columns.length);
        expect(row.values[change.column]).not.toBe(change.before);
      }
    }
  });

  it('lists every row by default', async () => {
    const { summary, rows } = await preview({ limit: 5 });
    expect(rows.total).toBe(summary.rows);
    expect(rows.items.map((row) => row.line)).toEqual([1, 2, 3, 4, 5]);
  });

  it('keeps rows changed in any of the chosen columns', async () => {
    const all = await preview({ limit: 200 });
    const changedIn = (name: string) => all.columns.find((c) => c.target === name)?.changed_cells ?? 0;
    const valued = all.rows.columns.filter((name) => changedIn(name) > 0);
    expect(valued.length).toBeGreaterThan(0);

    const one = await preview({ columns: [valued[0]], changedOnly: true, limit: 200 });
    const index = one.rows.columns.indexOf(valued[0]);
    expect(one.rows.total).toBe(changedIn(valued[0]));
    expect(one.rows.changed_total).toBe(one.rows.total);
    for (const row of one.rows.items) {
      expect(row.changes.some((change) => change.column === index)).toBe(true);
    }

    // An unchanged column adds no rows; every column with changes gives every changed row.
    const unchanged = all.rows.columns.filter((name) => changedIn(name) === 0);
    const withUnchanged = await preview({ columns: [valued[0], ...unchanged], changedOnly: true, limit: 200 });
    expect(withUnchanged.rows.total).toBe(one.rows.total);
    const everyChanged = await preview({ columns: valued, changedOnly: true, limit: 200 });
    expect(everyChanged.rows.total).toBe(all.summary.changed_rows);

    // Without changed_only every row is kept but the count still follows the columns.
    const counted = await preview({ columns: [valued[0]], limit: 5 });
    expect(counted.rows.total).toBe(all.summary.rows);
    expect(counted.rows.changed_total).toBe(one.rows.total);
    const none = await preview({ columns: unchanged, changedOnly: true });
    expect(none.rows.total).toBe(0);
    expect(none.rows.changed_total).toBe(0);
  });

  it('pages through rows', async () => {
    const first = await preview({ limit: 50 });
    const second = await preview({ offset: 50, limit: 50 });
    expect(second.rows.offset).toBe(50);
    expect(second.rows.items[0].line).toBeGreaterThan(first.rows.items[first.rows.items.length - 1].line);
    const past = await preview({ offset: first.rows.total, limit: 50 });
    expect(past.rows.items).toEqual([]);
  });

  it('has no fixture for writes', () => {
    expect(guestFixture(`/export/${DEMO_STUDY_ID}/preview`, 'POST')).toBeNull();
  });
});
