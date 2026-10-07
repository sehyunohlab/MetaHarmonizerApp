import { useEffect, useState } from 'react';
import { getColumnContext, type ColumnContext } from '../../api/client';
import { ApiError } from '../../api/http';

// Lazily-loaded sample values for a raw column — context that helps a curator
// decide the correct mapping (Sehyun: "to find the correct term you need context").
export function ColumnContextPanel({ studyId, column }: { studyId: string; column: string }) {
  const [ctx, setCtx] = useState<ColumnContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setErr(null);
    getColumnContext(studyId, column)
      .then((c) => alive && setCtx(c))
      .catch((e) => alive && setErr(e instanceof ApiError ? e.message : 'Failed to load context'))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [studyId, column]);

  if (loading) return <p className="italic text-slate-400 dark:text-slate-500">Loading sample values…</p>;
  if (err) return <p className="italic text-slate-400 dark:text-slate-500">{err}</p>;
  if (!ctx) return null;

  if (ctx.distinct_values === 0) {
    return (
      <p className="italic text-slate-400 dark:text-slate-500">
        This column is empty — no values in any of the {ctx.total_rows.toLocaleString()} rows.
      </p>
    );
  }

  return (
    <div>
      <p className="text-slate-500 dark:text-slate-400">
        <span title="Total number of rows (values) in this column">{ctx.total_rows.toLocaleString()} rows</span>
        {' · '}
        <span title="How many different (unique) values the column has">{ctx.distinct_values.toLocaleString()} distinct</span>
        {ctx.null_count > 0 && (
          <> · <span title="Rows with no value (empty cells)">{ctx.null_count.toLocaleString()} blank</span></>
        )}
      </p>
      <p className="mt-0.5 text-[11px] leading-snug text-slate-400 dark:text-slate-500">
        The values found in this column and how many rows have each (×N). Use it to sanity-check what the column actually holds.
      </p>
      {ctx.samples.length > 0 ? (
        <ul className="mt-1.5 flex flex-wrap gap-1.5">
          {ctx.samples.map((s, i) => (
            <li
              key={`${s.value}-${i}`}
              className="inline-flex items-center gap-1 rounded-md bg-white px-2 py-0.5 ring-1 ring-slate-200 dark:bg-slate-800 dark:ring-slate-700"
              title={`"${s.value}" appears in ${s.count.toLocaleString()} of ${ctx.total_rows.toLocaleString()} rows`}
            >
              <span className="font-mono text-slate-800 dark:text-slate-200">{s.value}</span>
              <span className="text-slate-400 dark:text-slate-500" title={`Appears in ${s.count.toLocaleString()} ${s.count === 1 ? 'row' : 'rows'}`}>×{s.count}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-slate-400 italic">No non-empty values</p>
      )}
    </div>
  );
}
