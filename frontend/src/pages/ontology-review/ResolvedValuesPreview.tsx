import type { Dispatch, SetStateAction } from 'react';
import { ArrowRight, ChevronDown, ChevronRight, Eye } from 'lucide-react';
import { Card, CardBody } from '../../components/ui/Card';
import type { RewritePreviewRow } from './types';

interface ResolvedValuesPreviewProps {
  showPreview: boolean;
  setShowPreview: Dispatch<SetStateAction<boolean>>;
  rewritePreview: Record<string, RewritePreviewRow[]>;
  previewFieldCount: number;
  previewValueCount: number;
}

export function ResolvedValuesPreview({
  showPreview,
  setShowPreview,
  rewritePreview,
  previewFieldCount,
  previewValueCount,
}: ResolvedValuesPreviewProps) {
  return (
    <Card>
      <CardBody className="py-3">
        <button
          type="button"
          onClick={() => setShowPreview((v) => !v)}
          className="flex w-full items-center justify-between gap-3 text-left"
        >
          <span className="flex items-center gap-2">
            <Eye className="h-4 w-4 text-primary-500" />
            <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">Resolved values preview</span>
            <span className="text-xs text-slate-500">
              {previewValueCount} value{previewValueCount !== 1 ? 's' : ''} across {previewFieldCount} field{previewFieldCount !== 1 ? 's' : ''} will be rewritten on export
            </span>
          </span>
          {showPreview ? <ChevronDown className="h-4 w-4 text-slate-400" /> : <ChevronRight className="h-4 w-4 text-slate-400" />}
        </button>

        {showPreview && (
          previewValueCount === 0 ? (
            <p className="mt-3 text-xs text-slate-400">
              Accept ontology terms to see how your data values will be rewritten. The raw upload is never changed — these rewrites are applied to the table you export.
            </p>
          ) : (
            <div className="mt-3 space-y-3">
              {Object.entries(rewritePreview).map(([field, rows]) => (
                <div key={field} className="rounded-lg border border-slate-200 dark:border-slate-800">
                  <div className="border-b border-slate-100 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-300 dark:border-slate-800 dark:bg-slate-800/50">
                    {field} <span className="font-normal text-slate-400">· {rows.length} value{rows.length !== 1 ? 's' : ''}</span>
                  </div>
                  <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                    {rows.map((r, i) => (
                      <li key={`${r.raw}-${i}`} className="flex flex-wrap items-center gap-2 px-3 py-1.5 text-xs">
                        <span className="rounded bg-slate-100 dark:bg-slate-800/70 px-1.5 py-0.5 font-mono text-slate-500 line-through">{r.raw}</span>
                        <ArrowRight className="h-3 w-3 text-slate-400" />
                        <span className="rounded bg-green-50 px-1.5 py-0.5 font-mono font-semibold text-green-700 dark:bg-green-500/15 dark:text-green-300">{r.term}</span>
                        {r.ontId && <span className="text-[10px] text-slate-400">{r.ontId}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )
        )}
      </CardBody>
    </Card>
  );
}
