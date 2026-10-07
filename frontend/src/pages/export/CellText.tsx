import { cn } from '../../lib/cn';

/** A cell value: blank values are shown explicitly, long ones truncate with a
 *  tooltip carrying the full text. */
export function CellText({ value, className }: { value: string; className?: string }) {
  if (value === '') {
    return <span className={cn('italic text-slate-500 dark:text-slate-400', className)}>(blank)</span>;
  }
  return (
    <span className={cn('inline-block max-w-[18rem] truncate align-bottom', className)} title={value}>
      {value}
    </span>
  );
}
