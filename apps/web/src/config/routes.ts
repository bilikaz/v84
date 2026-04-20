// [v84-1-4][front-nextjs:pages]
import type { User } from '@/modules/users/types';

export const routes = {
  home: '/',
  auth: {
    login: '/auth/login',
    register: '/auth/register',
    forgotPassword: '/auth/forgot-password',
    resetPassword: '/auth/reset-password',
  },
  dashboard: '/dashboard',
  settings: '/dashboard/settings',
  admin: {
    home: '/admin',
    users: '/admin/users',
    userNew: '/admin/users/new',
    userEdit: (id: string) => `/admin/users/${id}/edit`,
  },
} as const;

// Where should this user land after a successful login / register / oauth flow?
// Admins go to the admin shell; everyone else goes to the user dashboard.
export function landingPathForUser(user: Pick<User, 'role'>): string {
  return user.role === 'admin' ? routes.admin.home : routes.dashboard;
}
