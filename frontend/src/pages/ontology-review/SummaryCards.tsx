import { CircleCheck, Clock, HelpCircle, Tags } from 'lucide-react';
import type { OntologyStats } from './types';
import { StatCard } from './StatCard';

interface SummaryCardsProps {
  stats: OntologyStats;
}

export function SummaryCards({ stats }: SummaryCardsProps) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <StatCard icon={<Tags className="h-4 w-4" />} label="Mapped values" value={stats.mapped} tone="primary" />
      <StatCard icon={<Clock className="h-4 w-4" />} label="Pending review" value={stats.pending} tone="amber" />
      <StatCard icon={<CircleCheck className="h-4 w-4" />} label="Accepted" value={stats.accepted} tone="emerald" />
      <StatCard icon={<HelpCircle className="h-4 w-4" />} label="No ontology match" value={stats.unmatched} tone="slate" />
    </div>
  );
}
