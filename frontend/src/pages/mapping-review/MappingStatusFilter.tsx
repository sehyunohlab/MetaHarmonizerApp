import { CheckCircle2, Clock, XCircle } from 'lucide-react';
import SegmentedControl from '../../components/ui/SegmentedControl';
import type { Mapping } from '../../api/types';
import type { FilterStatus } from './types';

type MappingStatusFilterProps = {
  filterStatus: FilterStatus;
  mappings: Mapping[];
  onChange: (status: FilterStatus) => void;
};

export function MappingStatusFilter({
  filterStatus,
  mappings,
  onChange,
}: MappingStatusFilterProps) {
  return (
    <SegmentedControl<FilterStatus>
      value={filterStatus}
      onChange={onChange}
      className="mt-4"
      segments={[
        {
          value: 'pending',
          label: 'Pending',
          icon: <Clock className="h-3.5 w-3.5" />,
          tone: 'amber',
          count: mappings.filter((m) => m.status === 'pending').length,
        },
        {
          value: 'accepted',
          label: 'Accepted',
          icon: <CheckCircle2 className="h-3.5 w-3.5" />,
          tone: 'emerald',
          count: mappings.filter((m) => m.status === 'accepted').length,
        },
        {
          value: 'rejected',
          label: 'Rejected',
          icon: <XCircle className="h-3.5 w-3.5" />,
          tone: 'rose',
          count: mappings.filter((m) => m.status === 'rejected').length,
        },
        { value: 'all', label: 'All', tone: 'slate', count: mappings.length },
      ]}
    />
  );
}
