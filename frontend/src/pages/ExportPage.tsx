import { useParams, useSearchParams } from 'react-router-dom';
import { Download, FileDiff } from 'lucide-react';
import { useStudies } from '../hooks/queries';
import PageHeader from '../components/ui/PageHeader';
import SegmentedControl from '../components/ui/SegmentedControl';
import StudyPicker from '../components/StudyPicker';
import { cn } from '../lib/cn';
import { ChangePreview } from './export/ChangePreview';
import { ExportDownloads } from './export/ExportDownloads';

type ExportView = 'downloads' | 'preview';

export default function ExportPage() {
  const { studyId } = useParams<{ studyId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: studies, isLoading } = useStudies();

  if (!studyId) {
    return (
      <StudyPicker
        title="Export harmonized data"
        description="Pick a study to download its harmonized outputs."
        icon={<Download className="h-6 w-6" />}
        studies={studies}
        loading={isLoading}
        basePath="/export"
      />
    );
  }

  const study = studies?.find((s) => s.id === studyId);
  const view: ExportView = searchParams.get('view') === 'preview' ? 'preview' : 'downloads';
  const setView = (next: ExportView) => {
    const params = new URLSearchParams(searchParams);
    if (next === 'downloads') params.delete('view');
    else params.set('view', next);
    setSearchParams(params, { replace: true });
  };

  return (
    <div className={cn('mx-auto', view === 'preview' ? 'max-w-6xl' : 'max-w-3xl')}>
      <PageHeader
        title="Export harmonized data"
        icon={<Download className="h-6 w-6" />}
      >
        {study && (
          <p className="mt-1 text-sm text-slate-500">
            {study.row_count} rows · {study.column_count} columns
          </p>
        )}
      </PageHeader>

      <SegmentedControl<ExportView>
        value={view}
        onChange={setView}
        className="mb-6"
        segments={[
          { value: 'downloads', label: 'Downloads', icon: <Download className="h-4 w-4" /> },
          { value: 'preview', label: 'Preview changes', icon: <FileDiff className="h-4 w-4" /> },
        ]}
      />

      {view === 'preview' ? (
        <ChangePreview studyId={studyId} />
      ) : (
        <ExportDownloads studyId={studyId} studyName={study?.name} />
      )}
    </div>
  );
}
