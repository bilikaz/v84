'use client';

import { useEffect, useState } from 'react';
import { ApiError } from '@/lib';
import { Button } from '@/ui/primitives';
import { Modal } from '@/ui/feedback';
import {
  listSessions,
  revokeSession,
  revokeAllSessions,
  type Session,
} from '../api';

// [v84-4-3-1][front-nextjs:forms]
export function SessionsList() {
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [revokeAllOpen, setRevokeAllOpen] = useState(false);
  const [revokingAll, setRevokingAll] = useState(false);

  async function refresh() {
    try {
      const list = await listSessions();
      setSessions(list);
      setError('');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load sessions');
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleRevoke(id: string) {
    setBusyId(id);
    try {
      await revokeSession(id);
      setSessions((prev) => prev?.filter((s) => s.id !== id) ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not revoke session');
    } finally {
      setBusyId(null);
    }
  }

  async function handleRevokeAll() {
    setRevokingAll(true);
    try {
      await revokeAllSessions();
      await refresh();
      setRevokeAllOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not revoke sessions');
    } finally {
      setRevokingAll(false);
    }
  }

  if (sessions === null && !error) {
    return <p className="text-sm text-textMuted">Loading sessions…</p>;
  }

  const others = sessions?.filter((s) => !s.current) ?? [];

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-danger">{error}</div>
      )}

      <ul className="divide-y divide-border rounded-lg border border-border">
        {sessions?.map((session) => (
          <li key={session.id} className="flex items-center justify-between gap-4 p-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <p className="truncate text-sm font-medium text-text">
                  {session.deviceName ?? 'Unknown device'}
                  {session.deviceOs ? ` · ${session.deviceOs}` : ''}
                </p>
                {session.current && (
                  <span className="inline-flex items-center rounded-full bg-success px-2 py-0.5 text-xs font-medium text-textInverse">
                    This device
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-textMuted">
                {session.ipAddress ?? 'unknown ip'} · last seen{' '}
                {new Date(session.lastSeenAt).toLocaleString()}
              </p>
            </div>
            {!session.current && (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => handleRevoke(session.id)}
                disabled={busyId === session.id}
              >
                {busyId === session.id ? 'Revoking…' : 'Revoke'}
              </Button>
            )}
          </li>
        ))}
        {sessions && sessions.length === 0 && (
          <li className="p-4 text-sm text-textMuted">No active sessions.</li>
        )}
      </ul>

      {others.length > 0 && (
        <Button variant="danger" size="sm" onClick={() => setRevokeAllOpen(true)}>
          Sign out all other sessions
        </Button>
      )}

      <Modal
        open={revokeAllOpen}
        title="Sign out all other sessions?"
        confirmLabel="Sign out everywhere else"
        confirmVariant="danger"
        loading={revokingAll}
        onCancel={() => setRevokeAllOpen(false)}
        onConfirm={handleRevokeAll}
      >
        This revokes every session except the one you&apos;re using right now. You&apos;ll
        need to sign in again on those devices.
      </Modal>
    </div>
  );
}
