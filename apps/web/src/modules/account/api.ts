import { apiFetch } from '@/lib';
import type { User } from '@/modules/users/types';

export interface Session {
  id: string;
  deviceName: string | null;
  deviceOs: string | null;
  ipAddress: string | null;
  lastSeenAt: string;
  createdAt: string;
  current: boolean;
}

export function listSessions(): Promise<Session[]> {
  return apiFetch<Session[]>('/users/me/sessions');
}

export function revokeSession(id: string): Promise<void> {
  return apiFetch(`/users/me/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export function revokeAllSessions(): Promise<void> {
  return apiFetch('/users/me/sessions/all', { method: 'DELETE' });
}

// [v84-4-2-1][front-nextjs:api]
export function changePassword(currentPassword: string, password: string): Promise<User> {
  return apiFetch<User>('/users/me', {
    method: 'PATCH',
    body: JSON.stringify({ currentPassword, password }),
  });
}

export function changeUsername(currentPassword: string, username: string): Promise<User> {
  return apiFetch<User>('/users/me', {
    method: 'PATCH',
    body: JSON.stringify({ currentPassword, username }),
  });
}

// [v84-4-2-2][front-nextjs:api]
export function requestEmailChange(newEmail: string, currentPassword: string): Promise<void> {
  return apiFetch('/users/me/email', {
    method: 'POST',
    body: JSON.stringify({ newEmail, currentPassword }),
  });
}

export function confirmEmailChange(token: string): Promise<User> {
  return apiFetch<User>('/users/me/email/confirm', {
    method: 'POST',
    body: JSON.stringify({ token }),
  });
}

// [v84-4-1-1][front-nextjs:api]
export function enableTwoFactor(): Promise<{ secret: string }> {
  return apiFetch<{ secret: string }>('/users/me/2fa/enable', { method: 'POST' });
}

export function verifyTwoFactor(code: string): Promise<void> {
  return apiFetch('/users/me/2fa/verify', {
    method: 'POST',
    body: JSON.stringify({ code }),
  });
}

export function disableTwoFactor(password: string, code: string): Promise<void> {
  return apiFetch('/users/me/2fa', {
    method: 'DELETE',
    body: JSON.stringify({ password, code }),
  });
}
