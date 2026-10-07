import { Ban, CheckCircle2, LogOut, MailWarning, ShieldCheck, Users, X } from 'lucide-react';
import Badge from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { EmptyState, LoadingBlock } from '../../components/ui/Feedback';
import type { Role, User } from '../../api/types';
import type { AdminUserStats } from './utils';

const ROLES: Role[] = ['curator', 'admin'];

type UsersAccessSectionProps = {
  stats: AdminUserStats;
  pendingRequests: User[];
  pendingApprovals: User[];
  users: User[];
  isLoading: boolean;
  currentUserId?: number;
  rolePending: boolean;
  activePendingId?: number;
  logoutPendingId?: number;
  approveAdminPendingId?: number;
  rejectAdminPendingId?: number;
  approveAccountPendingId?: number;
  rejectAccountPendingId?: number;
  onSetRole: (id: number, role: Role) => void;
  onSetActive: (id: number, isActive: boolean) => void;
  onForceLogout: (id: number) => void;
  onApproveAdmin: (id: number) => void;
  onRejectAdmin: (id: number) => void;
  onApproveAccount: (id: number) => void;
  onRejectAccount: (id: number) => void;
};

export function UsersAccessSection({
  stats,
  pendingRequests,
  pendingApprovals,
  users,
  isLoading,
  currentUserId,
  rolePending,
  activePendingId,
  logoutPendingId,
  approveAdminPendingId,
  rejectAdminPendingId,
  approveAccountPendingId,
  rejectAccountPendingId,
  onSetRole,
  onSetActive,
  onForceLogout,
  onApproveAdmin,
  onRejectAdmin,
  onApproveAccount,
  onRejectAccount,
}: UsersAccessSectionProps) {
  return (
    <>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Total users" value={stats.total} />
        <Stat label="Admins" value={stats.admin} tone="text-primary-600" />
        <Stat label="Curators" value={stats.curator} tone="text-accent-600" />
        <Stat label="Disabled" value={stats.disabled} tone="text-rose-600" />
      </div>

      {/* Pending admin-access requests */}
      {pendingRequests.length > 0 && (
        <Card className="overflow-hidden border-amber-200 dark:border-amber-500/30">
          <div className="flex items-center gap-2 border-b border-amber-100 bg-amber-50/70 px-5 py-3 dark:border-amber-500/20 dark:bg-amber-500/10">
            <ShieldCheck className="h-4 w-4 text-amber-600 dark:text-amber-400" />
            <h3 className="text-sm font-semibold text-amber-800 dark:text-amber-300">
              Admin access requests
              <span className="ml-1.5 font-normal text-amber-600 dark:text-amber-400">({pendingRequests.length})</span>
            </h3>
          </div>
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {pendingRequests.map((u) => (
              <li key={u.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">{u.name || u.email}</p>
                  <p className="truncate text-xs text-slate-500">{u.email}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    icon={<CheckCircle2 className="h-3.5 w-3.5" />}
                    loading={approveAdminPendingId === u.id}
                    onClick={() => onApproveAdmin(u.id)}
                  >
                    Approve
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-500/10"
                    icon={<X className="h-3.5 w-3.5" />}
                    loading={rejectAdminPendingId === u.id}
                    onClick={() => onRejectAdmin(u.id)}
                  >
                    Decline
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Pending account approvals (untrusted-domain signups) */}
      {pendingApprovals.length > 0 && (
        <Card className="overflow-hidden border-sky-200 dark:border-sky-500/30">
          <div className="flex items-center gap-2 border-b border-sky-100 bg-sky-50/70 px-5 py-3 dark:border-sky-500/20 dark:bg-sky-500/10">
            <ShieldCheck className="h-4 w-4 text-sky-600 dark:text-sky-400" />
            <h3 className="text-sm font-semibold text-sky-800 dark:text-sky-300">
              Pending approvals
              <span className="ml-1.5 font-normal text-sky-600 dark:text-sky-400">({pendingApprovals.length})</span>
            </h3>
          </div>
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {pendingApprovals.map((u) => (
              <li key={u.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">{u.name || u.email}</p>
                  <p className="flex items-center gap-1.5 truncate text-xs text-slate-500">
                    {u.email}
                    {u.admin_requested && (
                      <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-500/20 dark:text-amber-300">
                        also requested admin
                      </span>
                    )}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    icon={<CheckCircle2 className="h-3.5 w-3.5" />}
                    loading={approveAccountPendingId === u.id}
                    onClick={() => onApproveAccount(u.id)}
                  >
                    Approve
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-500/10"
                    icon={<X className="h-3.5 w-3.5" />}
                    loading={rejectAccountPendingId === u.id}
                    onClick={() => onRejectAccount(u.id)}
                  >
                    Reject
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card className="overflow-hidden">
        {isLoading ? (
          <LoadingBlock label="Loading users…" />
        ) : !users?.length ? (
          <EmptyState icon={<Users className="h-6 w-6" />} title="No users found" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/80 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:bg-slate-800/50">
                  <th className="px-5 py-3">User</th>
                  <th className="px-5 py-3">Role</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {users.map((u) => {
                  const isSelf = u.id === currentUserId;
                  return (
                    <tr key={u.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-3">
                          <span className="grid h-9 w-9 place-items-center rounded-xl bg-slate-100 text-xs font-bold text-slate-600 dark:bg-slate-700/60 dark:text-slate-300">
                            {(u.name || u.email).slice(0, 2).toUpperCase()}
                          </span>
                          <div className="min-w-0">
                            <p className="truncate font-medium text-slate-800 dark:text-slate-200">
                              {u.name || '—'}
                              {isSelf && <span className="ml-1.5 text-xs text-slate-400">(you)</span>}
                            </p>
                            <p className="truncate text-xs text-slate-500">{u.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3">
                        <select
                          value={u.role}
                          disabled={isSelf || rolePending}
                          onChange={(e) => onSetRole(u.id, e.target.value as Role)}
                          className="field !w-auto !py-1.5 text-xs disabled:opacity-60"
                        >
                          {ROLES.map((r) => (
                            <option key={r} value={r}>
                              {r}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-5 py-3">
                        {!u.is_active ? (
                          <Badge tone="rose">
                            <Ban className="h-3.5 w-3.5" />
                            Disabled
                          </Badge>
                        ) : !u.email_verified ? (
                          <Badge tone="amber">
                            <MailWarning className="h-3.5 w-3.5" />
                            Unverified
                          </Badge>
                        ) : (
                          <Badge tone="green">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            Active
                          </Badge>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            icon={<LogOut className="h-3.5 w-3.5" />}
                            loading={logoutPendingId === u.id}
                            onClick={() => onForceLogout(u.id)}
                          >
                            Force sign-out
                          </Button>
                          <Button
                            variant={u.is_active ? 'ghost' : 'secondary'}
                            size="sm"
                            disabled={isSelf}
                            icon={u.is_active ? <Ban className="h-3.5 w-3.5" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                            className={u.is_active ? 'text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-500/10' : ''}
                            loading={activePendingId === u.id}
                            onClick={() => onSetActive(u.id, !u.is_active)}
                          >
                            {u.is_active ? 'Disable' : 'Enable'}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${tone ?? 'text-slate-900 dark:text-slate-100'}`}>{value}</p>
    </Card>
  );
}
