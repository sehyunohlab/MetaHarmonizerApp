import type { FilterStage } from './types';
import { STAGE_META, STAGE_ORDER } from './utils';

type StageBreakdownProps = {
  filterStage: FilterStage;
  mappingsCount: number;
  stageCounts: Record<string, number>;
  onFilterStageChange: (stage: FilterStage) => void;
};

export function StageBreakdown({
  filterStage,
  mappingsCount,
  stageCounts,
  onFilterStageChange,
}: StageBreakdownProps) {
  if (mappingsCount === 0) return null;

  return (
    <div className="card p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-medium text-slate-500">Stage breakdown</span>
        {filterStage !== 'all' && (
          <button
            onClick={() => onFilterStageChange('all')}
            className="text-xs font-medium text-primary-600 hover:text-primary-700"
          >
            Clear
          </button>
        )}
      </div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        {STAGE_ORDER.map((s) => {
          const count = stageCounts[s] ?? 0;
          if (!count) return null;
          const pct = (count / mappingsCount) * 100;
          return (
            <button
              key={s}
              title={`${STAGE_META[s].label}: ${count}`}
              onClick={() => onFilterStageChange(filterStage === s ? 'all' : (s as FilterStage))}
              className={`${STAGE_META[s].bar} transition-opacity hover:opacity-80 ${
                filterStage !== 'all' && filterStage !== s ? 'opacity-30' : ''
              }`}
              style={{ width: `${pct}%` }}
            />
          );
        })}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {STAGE_ORDER.map((s) => {
          const count = stageCounts[s] ?? 0;
          if (!count) return null;
          return (
            <button
              key={s}
              onClick={() => onFilterStageChange(filterStage === s ? 'all' : (s as FilterStage))}
              className="flex items-center gap-1.5 text-xs text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-slate-100"
            >
              <span className={`h-2 w-2 rounded-full ${STAGE_META[s].bar}`} />
              {STAGE_META[s].label}
              <span className="font-semibold">{count}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
