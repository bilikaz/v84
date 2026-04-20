import { apiFetch } from '@/lib';
import type { Session } from './types';

// [v84-4-3-1][front-nextjs:api]
export function listSessions(): Promise<Session[]> {
  return apiFetch<Session[]>('/users/me/sessions');
}

// [v84-4-3-2][front-nextjs:api]
export function revokeSession(sessionId: string): Promise<void> {
  return apiFetch(`/users/me/sessions/${sessionId}`, { method: 'DELETE' });
}

// [v84-4-3-2][front-nextjs:api]
export function revokeAllSessions(): Promise<void> {
  return apiFetch('/users/me/sessions/all', { method: 'DELETE' });
}
