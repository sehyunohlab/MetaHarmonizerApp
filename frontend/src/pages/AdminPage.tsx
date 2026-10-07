import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { BrainCircuit, Layers, Network, Search, Shield, Users } from 'lucide-react';
import { toast } from 'sonner';
import PageHeader from '../components/ui/PageHeader';
import Badge from '../components/ui/Badge';
import SegmentedControl from '../components/ui/SegmentedControl';
import { useAuth } from '../context/AuthContext';
import {
  adminApproveAccount,
  adminApproveAdmin,
  adminForceLogout,
  adminListUsers,
  adminRejectAccount,
  adminRejectAdmin,
  adminSetActive,
  adminSetRole,
} from '../api/auth';
import type { Role } from '../api/types';
import { AliasDictCard } from './admin/AliasDictCard';
import { FederationCard } from './admin/FederationCard';
import { LearnedDecisionsCard } from './admin/LearnedDecisionsCard';
import { SchemaVersionsCard } from './admin/SchemaVersionsCard';
import { UsersAccessSection } from './admin/UsersAccessSection';
import { computeStats } from './admin/utils';

type AdminTab = 'users' | 'schemas' | 'aliases' | 'knowledge' | 'federation';
const ADMIN_TABS: AdminTab[] = ['users', 'schemas', 'aliases', 'knowledge', 'federation'];

export default function AdminPage() {
  const { user: me } = useAuth();
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get('tab') as AdminTab | null;
  const activeTab = requestedTab && ADMIN_TABS.includes(requestedTab) ? requestedTab : 'users';

  const users = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: adminListUsers,
    enabled: activeTab === 'users',
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ['admin', 'users'] });

  const roleM = useMutation({
    mutationFn: ({ id, role }: { id: number; role: Role }) => adminSetRole(id, role),
    onSuccess: (u) => {
      invalidate();
      toast.success(`${u.email} is now ${u.role}`);
    },
    onError: (e: any) => toast.error(e?.message ?? 'Could not change role'),
  });

  const activeM = useMutation({
    mutationFn: ({ id, isActive }: { id: number; isActive: boolean }) => adminSetActive(id, isActive),
    onSuccess: (u) => {
      invalidate();
      toast.success(`${u.email} ${u.is_active ? 'enabled' : 'disabled'}`);
    },
    onError: (e: any) => toast.error(e?.message ?? 'Could not update account'),
  });

  const logoutM = useMutation({
    mutationFn: adminForceLogout,
    onSuccess: () => toast.success('All sessions revoked'),
    onError: () => toast.error('Could not force sign-out'),
  });

  const approveM = useMutation({
    mutationFn: adminApproveAdmin,
    onSuccess: (u) => {
      invalidate();
      toast.success(`${u.email} is now an admin`);
    },
    onError: (e: any) => toast.error(e?.message ?? 'Could not approve request'),
  });

  const rejectM = useMutation({
    mutationFn: adminRejectAdmin,
    onSuccess: (u) => {
      invalidate();
      toast(`Admin request for ${u.email} declined`);
    },
    onError: (e: any) => toast.error(e?.message ?? 'Could not decline request'),
  });

  const approveAccountM = useMutation({
    mutationFn: adminApproveAccount,
    onSuccess: (u) => {
      invalidate();
      toast.success(`${u.email} approved — they can now sign in`);
    },
    onError: (e: any) => toast.error(e?.message ?? 'Could not approve account'),
  });

  const rejectAccountM = useMutation({
    mutationFn: adminRejectAccount,
    onSuccess: (u) => {
      invalidate();
      toast(`${u.email} rejected`);
    },
    onError: (e: any) => toast.error(e?.message ?? 'Could not reject account'),
  });

  const userRows = users.data ?? [];
  const stats = computeStats(userRows);
  const pendingRequests = userRows.filter((u) => u.admin_requested && u.role !== 'admin');
  const pendingApprovals = userRows.filter((u) => !u.approved && u.is_active);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader
        title="Admin console"
        description="Manage team members, roles, and access."
        icon={<Shield className="h-6 w-6" />}
        actions={
          <Badge tone="primary">
            <Shield className="h-3.5 w-3.5" />
            Admin only
          </Badge>
        }
      />

      <SegmentedControl<AdminTab>
        value={activeTab}
        onChange={(tab) => {
          const next = new URLSearchParams(searchParams);
          if (tab === 'users') next.delete('tab');
          else next.set('tab', tab);
          setSearchParams(next);
        }}
        className="mt-6 w-full overflow-x-auto"
        segments={[
          {
            value: 'users',
            label: 'Users & access',
            icon: <Users className="h-4 w-4" />,
            count: pendingRequests.length + pendingApprovals.length || undefined,
          },
          { value: 'schemas', label: 'Schema versions', icon: <Layers className="h-4 w-4" /> },
          { value: 'aliases', label: 'Aliases', icon: <Search className="h-4 w-4" /> },
          { value: 'knowledge', label: 'Knowledge', icon: <BrainCircuit className="h-4 w-4" /> },
          { value: 'federation', label: 'Federation', icon: <Network className="h-4 w-4" /> },
        ]}
      />

      {activeTab === 'users' && (
        <UsersAccessSection
          stats={stats}
          pendingRequests={pendingRequests}
          pendingApprovals={pendingApprovals}
          users={userRows}
          isLoading={users.isLoading}
          currentUserId={me?.id}
          rolePending={roleM.isPending}
          activePendingId={activeM.isPending ? activeM.variables?.id : undefined}
          logoutPendingId={logoutM.isPending ? logoutM.variables : undefined}
          approveAdminPendingId={approveM.isPending ? approveM.variables : undefined}
          rejectAdminPendingId={rejectM.isPending ? rejectM.variables : undefined}
          approveAccountPendingId={approveAccountM.isPending ? approveAccountM.variables : undefined}
          rejectAccountPendingId={rejectAccountM.isPending ? rejectAccountM.variables : undefined}
          onSetRole={(id, role) => roleM.mutate({ id, role })}
          onSetActive={(id, isActive) => activeM.mutate({ id, isActive })}
          onForceLogout={(id) => logoutM.mutate(id)}
          onApproveAdmin={(id) => approveM.mutate(id)}
          onRejectAdmin={(id) => rejectM.mutate(id)}
          onApproveAccount={(id) => approveAccountM.mutate(id)}
          onRejectAccount={(id) => rejectAccountM.mutate(id)}
        />
      )}

      {activeTab === 'schemas' && <SchemaVersionsCard />}
      {activeTab === 'aliases' && <AliasDictCard />}
      {activeTab === 'knowledge' && <LearnedDecisionsCard />}
      {activeTab === 'federation' && <FederationCard />}
    </div>
  );
}
