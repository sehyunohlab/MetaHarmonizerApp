import { useEffect, useId, useRef, useState } from 'react';
import { ChevronDown, Columns3, Search } from 'lucide-react';
import { cn } from '../../lib/cn';
import { describeColumnChange, normalizeSelection, selectionLabel } from './presentation';

function Count({ value }: { value: number }) {
  return (
    <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-slate-600 dark:bg-slate-800 dark:text-slate-300">
      {value.toLocaleString()}
    </span>
  );
}

/** A checklist of the exported columns: show any combination of them, every
 *  column, only the changed ones, or none. ``selected`` is null for all. */
export function ColumnPicker({
  columns,
  selected,
  changed,
  renamedFrom,
  changedCells,
  onChange,
}: {
  columns: string[];
  selected: string[] | null;
  changed: ReadonlySet<string>;
  renamedFrom: Record<string, string>;
  changedCells: Record<string, number>;
  onChange: (next: string[] | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const panelId = useId();

  const chosen = new Set(selected ?? columns);
  const changedList = columns.filter((name) => changed.has(name));
  const needle = search.trim().toLowerCase();
  const shown = needle
    ? columns.filter(
        (name) => name.toLowerCase().includes(needle) || (renamedFrom[name] ?? '').toLowerCase().includes(needle),
      )
    : columns;

  useEffect(() => {
    if (!open) return;
    searchRef.current?.focus();
    const closeOnOutsidePointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', closeOnOutsidePointer);
    return () => document.removeEventListener('pointerdown', closeOnOutsidePointer);
  }, [open]);

  const choose = (names: Iterable<string>) => onChange(normalizeSelection(columns, names));
  const toggle = (name: string, on: boolean) => {
    const next = new Set(chosen);
    if (on) next.add(name);
    else next.delete(name);
    choose(next);
  };

  return (
    <div
      ref={rootRef}
      className="relative"
      onKeyDown={(event) => {
        if (event.key === 'Escape' && open) {
          event.stopPropagation();
          setOpen(false);
          buttonRef.current?.focus();
        }
      }}
      onBlur={(event) => {
        // Tabbing out closes the list; clicks inside it keep it open.
        const next = event.relatedTarget as Node | null;
        if (next && !rootRef.current?.contains(next)) setOpen(false);
      }}
    >
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 shadow-xs transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
      >
        <Columns3 className="h-4 w-4 text-slate-500 dark:text-slate-400" aria-hidden="true" />
        Columns
        <span className="max-w-[12rem] truncate rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold tabular-nums text-slate-700 dark:bg-slate-800 dark:text-slate-200">
          {selectionLabel(selected, columns.length)}
        </span>
        <ChevronDown
          className={cn('h-4 w-4 text-slate-500 transition-transform dark:text-slate-400', open && 'rotate-180')}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div
          id={panelId}
          className="absolute left-0 top-full z-40 mt-2 w-80 max-w-[calc(100vw-2.5rem)] rounded-xl border border-slate-200 bg-white p-2 shadow-xl dark:border-slate-700 dark:bg-slate-900"
        >
          <label className="relative block">
            <span className="sr-only">Search columns</span>
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
              aria-hidden="true"
            />
            <input
              ref={searchRef}
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search columns…"
              className="field py-1.5 pl-8 text-xs"
            />
          </label>

          <div className="mt-2 flex flex-wrap items-center gap-1" role="group" aria-label="Quick picks">
            <button type="button" className="btn-ghost btn-sm px-2" onClick={() => onChange(null)}>
              All <Count value={columns.length} />
            </button>
            <button
              type="button"
              className="btn-ghost btn-sm px-2"
              disabled={changedList.length === 0}
              title="Columns that were renamed or have changed values"
              onClick={() => choose(changedList)}
            >
              Changed <Count value={changedList.length} />
            </button>
            <button type="button" className="btn-ghost btn-sm px-2" onClick={() => onChange([])}>
              None
            </button>
          </div>

          <fieldset className="mt-1 border-t border-slate-100 pt-1 dark:border-slate-800">
            <legend className="sr-only">Columns to show</legend>
            {shown.length === 0 ? (
              <p className="px-2 py-6 text-center text-xs text-slate-500 dark:text-slate-400">No columns match.</p>
            ) : (
              <ul className="max-h-72 overflow-y-auto">
                {shown.map((name) => {
                  const index = columns.indexOf(name);
                  const inputId = `${panelId}-column-${index}`;
                  return (
                    <li
                      key={name}
                      className="flex items-start gap-2.5 rounded-lg px-2 py-1.5 hover:bg-slate-50 dark:hover:bg-slate-800"
                    >
                      <input
                        id={inputId}
                        type="checkbox"
                        className="checkbox mt-0.5"
                        checked={chosen.has(name)}
                        aria-describedby={`${inputId}-change`}
                        onChange={(event) => toggle(name, event.target.checked)}
                      />
                      <span className="min-w-0">
                        <label
                          htmlFor={inputId}
                          className="block cursor-pointer truncate font-mono text-xs font-semibold text-slate-800 dark:text-slate-100"
                        >
                          {name}
                        </label>
                        <span
                          id={`${inputId}-change`}
                          className="block truncate text-[11px] text-slate-500 dark:text-slate-400"
                        >
                          {describeColumnChange(renamedFrom[name], changedCells[name] ?? 0)}
                        </span>
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </fieldset>

          <p className="mt-1 border-t border-slate-100 px-2 pt-2 text-[11px] text-slate-500 dark:border-slate-800 dark:text-slate-400">
            {`${chosen.size.toLocaleString()} of ${columns.length.toLocaleString()} columns shown`}
          </p>
        </div>
      )}
    </div>
  );
}
