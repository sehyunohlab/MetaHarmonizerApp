import { useState } from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';
import { downloadExport } from '../../api/client';
import type { ExportPreviewQuery } from '../../api/types';
import { EmptyState, Skeleton } from '../../components/ui/Feedback';
import { useExportPreview } from '../../hooks/queries';
import { ChangedValuesGrid } from './ChangedValuesGrid';
import { PAGE_SIZE } from './presentation';
import { PreviewSummary } from './PreviewSummary';
import { useExportDownload } from './useExportDownload';

// Everything by default (changes are highlighted); the Columns list narrows what is shown.
const INITIAL_QUERY: ExportPreviewQuery = { offset: 0, limit: PAGE_SIZE, changedOnly: false, columns: null };

/** Harmonized CSV vs. original upload: a summary, then every harmonized value. */
export function ChangePreview({ studyId }: { studyId: string }) {
  const [query, setQuery] = useState<ExportPreviewQuery>(INITIAL_QUERY);
  const preview = useExportPreview(studyId, query);
  const { downloading, run } = useExportDownload();

  if (preview.isPending) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading the export preview">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((key) => (
            <Skeleton key={key} className="h-24 rounded-2xl" />
          ))}
        </div>
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    );
  }

  if (preview.isError) {
    return (
      <EmptyState
        icon={<AlertTriangle className="h-6 w-6" />}
        title="Couldn't build the preview"
        description={preview.error instanceof Error ? preview.error.message : 'Please try again.'}
        action={
          <button type="button" className="btn-secondary btn-sm" onClick={() => preview.refetch()}>
            <RotateCcw className="h-4 w-4" />
            Try again
          </button>
        }
      />
    );
  }

  const { summary, columns, rows } = preview.data;

  return (
    <div className="space-y-6">
      <PreviewSummary
        studyId={studyId}
        summary={summary}
        downloading={downloading === 'harmonized'}
        onDownload={() => run('harmonized', () => downloadExport(studyId, 'harmonized'))}
      />
      <ChangedValuesGrid
        rows={rows}
        columns={columns}
        query={query}
        fetching={preview.isFetching}
        onQueryChange={setQuery}
      />
    </div>
  );
}
