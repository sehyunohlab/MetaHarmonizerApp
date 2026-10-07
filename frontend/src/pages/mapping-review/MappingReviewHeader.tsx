import { Check, Table2, X } from 'lucide-react';
import PageHeader from '../../components/ui/PageHeader';
import RadialProgress from '../../components/ui/RadialProgress';

type MappingReviewHeaderProps = {
  mappingsCount: number;
  reviewedCount: number;
  selectedCount: number;
  onBatch: (action: 'accepted' | 'rejected') => void;
};

export function MappingReviewHeader({
  mappingsCount,
  reviewedCount,
  selectedCount,
  onBatch,
}: MappingReviewHeaderProps) {
  return (
    <PageHeader
      title="Schema mapping review"
      icon={<Table2 className="h-6 w-6" />}
      actions={
        <div className="flex items-center gap-2">
          {mappingsCount > 0 && (
            <div className="mr-1 hidden items-center gap-2 sm:flex" title={`${reviewedCount} of ${mappingsCount} columns reviewed`}>
              <RadialProgress
                value={reviewedCount / mappingsCount}
                size={38}
                stroke={5}
                tone="#2986e2"
                hideValue
              />
              <span className="text-xs font-medium text-slate-500">
                {reviewedCount}/{mappingsCount} reviewed
              </span>
            </div>
          )}
          {selectedCount > 0 ? (
            <>
              <span className="text-sm font-medium text-slate-600 dark:text-slate-300">{selectedCount} selected</span>
              <button onClick={() => onBatch('accepted')} className="btn bg-emerald-600 text-white btn-sm hover:bg-emerald-700">
                <Check className="h-3.5 w-3.5" />
                Accept all
              </button>
              <button onClick={() => onBatch('rejected')} className="btn-danger btn-sm">
                <X className="h-3.5 w-3.5" />
                Reject all
              </button>
            </>
          ) : null}
        </div>
      }
    />
  );
}
