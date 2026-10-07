import type { Dispatch, SetStateAction } from 'react';
import { CircleCheck, Clock, XCircle } from 'lucide-react';
import type { OntologyMapping } from '../../api/types';
import SegmentedControl from '../../components/ui/SegmentedControl';
import type { StatusFilter } from './types';

interface StatusFilterControlProps {
  statusFilter: StatusFilter;
  setStatusFilter: Dispatch<SetStateAction<StatusFilter>>;
  matched: OntologyMapping[];
}

export function StatusFilterControl({
  statusFilter,
  setStatusFilter,
  matched,
}: StatusFilterControlProps) {
  return (
    <SegmentedControl<StatusFilter>
      value={statusFilter}
      onChange={setStatusFilter}
      segments={[
        {
          value: 'pending',
          label: 'Pending',
          icon: <Clock className="h-3.5 w-3.5" />,
          tone: 'amber',
          count: matched.filter((m) => m.status === 'pending').length,
        },
        {
          value: 'accepted',
          label: 'Accepted',
          icon: <CircleCheck className="h-3.5 w-3.5" />,
          tone: 'emerald',
          count: matched.filter((m) => m.status === 'accepted').length,
        },
        {
          value: 'rejected',
          label: 'Rejected',
          icon: <XCircle className="h-3.5 w-3.5" />,
          tone: 'rose',
          count: matched.filter((m) => m.status === 'rejected').length,
        },
        { value: 'all', label: 'All', tone: 'slate', count: matched.length },
      ]}
    />
  );
}
