// [v84-2-3-1][front-nextjs:api]
export type UserRole = 'user' | 'admin';

export interface User {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  twoFactorEnabled: boolean;
  createdAt: string;
}
