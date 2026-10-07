import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowRightLeft, Columns3, Download, Rows3, Sparkles } from 'lucide-react';
import type { ExportPreviewSummary } from '../../api/types';
import { Card, CardBody } from '../../components/ui/Card';
import { formatPercent, pluralize } from './presentation';

const TILE_TONE = {
  slate: 'bg-slate-100 text-slate-600 dark:bg-slate-800/70 dark:text-slate-300',
  primary: 'bg-primary-50 text-primary-700 dark:bg-primary-500/15 dark:text-primary-300',
  teal: 'bg-accent-50 text-accent-700 dark:bg-accent-500/15 dark:text-accent-300',
} as const;

function SummaryTile({
  icon,
  label,
  value,
  hint,
  tone,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  hint: string;
  tone: keyof typeof TILE_TONE;
}) {
  return (
    <Card>
      <CardBody className="flex items-start gap-3 py-4">
        <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${TILE_TONE[tone]}`}>{icon}</span>
        <div className="min-w-0">
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</div>
          <div className="mt-0.5 text-lg font-bold tabular-nums text-slate-900 dark:text-slate-100">{value}</div>
          <div className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400" title={hint}>
            {hint}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

export function PreviewSummary({
  studyId,
  summary,
  downloading,
  onDownload,
}: {
  studyId: string;
  summary: ExportPreviewSummary;
  downloading: boolean;
  onDownload: () => void;
}) {
  const n = (value: number) => value.toLocaleString();

  return (
    <section aria-label="Summary of changes" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-slate-600 dark:text-slate-300">
          Your original upload compared with the{' '}
          <span className="font-semibold text-slate-900 dark:text-slate-100">Harmonized CSV</span>. Previewing
          doesn&apos;t export anything.
        </p>
        <button
          type="button"
          onClick={onDownload}
          disabled={downloading}
          className="btn-primary btn-sm disabled:cursor-wait disabled:opacity-60"
        >
          <Download className="h-4 w-4" />
          {downloading ? 'Preparing…' : 'Download harmonized CSV'}
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryTile
          icon={<Rows3 className="h-4 w-4" />}
          label="Rows"
          value={n(summary.rows)}
          hint="Same rows, in the same order"
          tone="slate"
        />
        <SummaryTile
          icon={<Columns3 className="h-4 w-4" />}
          label="Columns"
          value={`${n(summary.columns_before)} → ${n(summary.columns_after)}`}
          hint={summary.dropped ? `${n(summary.dropped)} not exported` : 'Every column is exported'}
          tone="primary"
        />
        <SummaryTile
          icon={<ArrowRightLeft className="h-4 w-4" />}
          label="Renamed"
          value={n(summary.renamed)}
          hint={`${n(summary.matched)} already ${summary.matched === 1 ? 'matches' : 'match'} the schema`}
          tone="primary"
        />
        <SummaryTile
          icon={<Sparkles className="h-4 w-4" />}
          label="Values changed"
          value={n(summary.changed_cells)}
          hint={`${pluralize(summary.changed_rows, 'row')} · ${formatPercent(summary.changed_cells, summary.compared_cells)} of cells`}
          tone="teal"
        />
      </div>

      {summary.pending > 0 && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100"
        >
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-300" aria-hidden="true" />
          <p className="min-w-0 flex-1">
            <span className="font-semibold">{pluralize(summary.pending, 'exported column')}</span>{' '}
            {summary.pending === 1 ? 'uses' : 'use'} an unreviewed mapping suggestion. Review{' '}
            {summary.pending === 1 ? 'it' : 'them'} before exporting to be sure the field names are right.
          </p>
          <Link to={`/review/${encodeURIComponent(studyId)}`} className="btn-secondary btn-sm">
            Review mappings
          </Link>
        </div>
      )}
    </section>
  );
}
