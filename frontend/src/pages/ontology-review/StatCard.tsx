import type { ReactNode } from 'react';
import { Card, CardBody } from '../../components/ui/Card';

interface StatCardProps {
  icon: ReactNode;
  label: string;
  value: number;
  tone: 'primary' | 'amber' | 'emerald' | 'slate';
}

export function StatCard({
  icon,
  label,
  value,
  tone,
}: StatCardProps) {
  const tones: Record<string, string> = {
    primary: 'bg-primary-50 text-primary-700 dark:bg-primary-500/15 dark:text-primary-300',
    amber: 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
    emerald: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
    slate: 'bg-slate-100 dark:bg-slate-800/70 text-slate-600 dark:text-slate-300',
  };
  return (
    <Card>
      <CardBody className="flex items-center gap-3 py-3">
        <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${tones[tone]}`}>{icon}</span>
        <div className="min-w-0">
          <div className="text-lg font-bold text-slate-900 dark:text-slate-100">{value.toLocaleString()}</div>
          <div className="truncate text-xs text-slate-500">{label}</div>
        </div>
      </CardBody>
    </Card>
  );
}
