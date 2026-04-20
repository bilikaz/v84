// [v84-2-3-1][front-nextjs:api]
import { apiFetch } from '@/lib';
import type { Paginated, ListQuery } from '@/lib';
import type { User, UserRole } from './types';

export interface ListUsersQuery extends ListQuery {
  role?: UserRole;
  search?: string;
}

export function listUsers(query: ListUsersQuery = {}): Promise<Paginated<User>> {
  const params = new URLSearchParams();
  if (query.page) params.set('page', String(query.page));
  if (query.limit) params.set('limit', String(query.limit));
  if (query.role) params.set('role', query.role);
  if (query.search) params.set('search', query.search);
  const qs = params.toString();
  return apiFetch<Paginated<User>>(`/users${qs ? `?${qs}` : ''}`);
}

export function getUser(id: string): Promise<User> {
  return apiFetch<User>(`/users/${id}`);
}

export function createUser(data: {
  username: string;
  email: string;
  password: string;
  role: UserRole;
}): Promise<User> {
  return apiFetch<User>('/users', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateUser(
  id: string,
  data: { username?: string; password?: string; role?: UserRole },
): Promise<User> {
  return apiFetch<User>(`/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteUser(id: string): Promise<void> {
  return apiFetch(`/users/${id}`, { method: 'DELETE' });
}
