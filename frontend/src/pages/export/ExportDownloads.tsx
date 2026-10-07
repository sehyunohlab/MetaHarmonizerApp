import { Database, Download, FileJson, FileText, FolderArchive, Tags } from 'lucide-react';
import { downloadExport, downloadLabeledExport } from '../../api/client';
import { Card, CardBody } from '../../components/ui/Card';
import CompleteStudyButton from '../../components/CompleteStudyButton';
import { useExportDownload } from './useExportDownload';

const EXPORTS = [
  {
    icon: FileText,
    title: 'Harmonized CSV',
    desc: 'Data with columns renamed to curated schema fields and ontology IDs added.',
    format: 'harmonized' as const,
    tone: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400',
  },
  {
    icon: Database,
    title: 'cBioPortal Format',
    desc: 'Tab-separated file with cBioPortal clinical header lines, ready for the importer.',
    format: 'cbioportal' as const,
    tone: 'bg-primary-50 text-primary-600 dark:bg-primary-500/15 dark:text-primary-300',
  },
  {
    icon: FolderArchive,
    title: 'cBioPortal Study Folder (ZIP)',
    desc: 'Full study folder (meta + clinical data files), ready to run through validateData.py.',
    format: 'cbioportal-study' as const,
    tone: 'bg-indigo-50 text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-300',
  },
  {
    icon: FileJson,
    title: 'Mapping Report (JSON)',
    desc: 'Full audit trail of mapping decisions, curator edits, and metadata.',
    format: 'report' as const,
    tone: 'bg-purple-50 text-purple-600 dark:bg-purple-500/15 dark:text-purple-300',
  },
];

export function ExportDownloads({ studyId, studyName }: { studyId: string; studyName?: string }) {
  const { downloading, run } = useExportDownload();

  return (
    <>
      <div className="grid gap-4">
        {EXPORTS.map(({ icon: Icon, title, desc, format, tone }) => (
          <Card key={format} className="transition hover:shadow-card">
            <CardBody className="flex items-center justify-between gap-4">
              <div className="flex items-start gap-4">
                <div className={`grid h-12 w-12 place-items-center rounded-2xl ${tone}`}>
                  <Icon className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
                  <p className="mt-1 max-w-md text-xs text-slate-500">{desc}</p>
                </div>
              </div>
              <button
                type="button"
                aria-label={`Download ${title}`}
                disabled={downloading !== null}
                onClick={() => run(format, () => downloadExport(studyId, format))}
                className="btn-primary btn-sm shrink-0 disabled:cursor-wait disabled:opacity-60"
              >
                <Download className="h-4 w-4" />
                {downloading === format ? 'Preparing…' : 'Download'}
              </button>
            </CardBody>
          </Card>
        ))}

        {/* Labeled dataset (G9) — confirmed mappings as a training corpus */}
        <Card className="transition hover:shadow-card">
          <CardBody className="flex items-center justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="grid h-12 w-12 place-items-center rounded-2xl bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300">
                <Tags className="h-6 w-6" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Labeled Dataset</h3>
                <p className="mt-1 max-w-md text-xs text-slate-500">
                  Curator-confirmed mappings only — a labeled corpus for engine training/evaluation.
                </p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <button
                type="button"
                aria-label="Download Labeled Dataset CSV"
                disabled={downloading !== null}
                onClick={() => run('labeled-csv', () => downloadLabeledExport(studyId, 'csv'))}
                className="btn-secondary btn-sm disabled:cursor-wait disabled:opacity-60"
              >
                <Download className="h-4 w-4" />
                {downloading === 'labeled-csv' ? 'Preparing…' : 'CSV'}
              </button>
              <button
                type="button"
                aria-label="Download Labeled Dataset JSONL"
                disabled={downloading !== null}
                onClick={() => run('labeled-jsonl', () => downloadLabeledExport(studyId, 'jsonl'))}
                className="btn-secondary btn-sm disabled:cursor-wait disabled:opacity-60"
              >
                <Download className="h-4 w-4" />
                {downloading === 'labeled-jsonl' ? 'Preparing…' : 'JSONL'}
              </button>
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Study lifecycle action — completing files the study away */}
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-800/40">
        <p className="text-xs text-slate-500">
          Completing files this study away and clears it from your work list.
          Studies left incomplete are auto-removed after a week.
        </p>
        <CompleteStudyButton studyId={studyId} studyName={studyName} redirectTo="/export" />
      </div>
    </>
  );
}
