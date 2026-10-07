import type { User } from '../../api/types';

export type AdminUserStats = {
  total: number;
  admin: number;
  curator: number;
  disabled: number;
};

export function computeStats(users: User[]): AdminUserStats {
  return {
    total: users.length,
    admin: users.filter((u) => u.role === 'admin').length,
    curator: users.filter((u) => u.role === 'curator').length,
    disabled: users.filter((u) => !u.is_active).length,
  };
}
