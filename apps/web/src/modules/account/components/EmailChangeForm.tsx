'use client';

import { useState } from 'react';
import { ApiError } from '@/lib';
import { useAuth } from '@/common/hooks';
import { Button } from '@/ui/primitives';
import { requestEmailChange } from '../api';

// [v84-4-2-2][front-nextjs:forms]
export function EmailChangeForm() {
  const { user } = useAuth();
  const [newEmail, setNewEmail] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!newEmail || !currentPassword) {
      setError('Both fields are required');
      return;
    }

    if (newEmail === user?.email) {
      setError('New email is the same as the current one');
      return;
    }

    setSubmitting(true);
    try {
      await requestEmailChange(newEmail, currentPassword);
      setNewEmail('');
      setCurrentPassword('');
      setSuccess('Confirmation email sent to the new address. Check your inbox.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not request email change');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-danger">{error}</div>
      )}
      {success && (
        <div className="rounded-md bg-green-50 p-3 text-sm text-success">{success}</div>
      )}

      <div>
        <p className="text-sm text-textMuted">Current: {user?.email}</p>
      </div>

      <div>
        <label htmlFor="newEmail" className="block text-sm font-medium text-text">
          New email
        </label>
        <input
          id="newEmail"
          type="email"
          value={newEmail}
          onChange={(e) => setNewEmail(e.target.value)}
          autoComplete="email"
          className="mt-1 block w-full rounded-md border border-border px-3 py-2 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
        />
      </div>

      <div>
        <label htmlFor="emailChangePassword" className="block text-sm font-medium text-text">
          Current password
        </label>
        <input
          id="emailChangePassword"
          type="password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          autoComplete="current-password"
          className="mt-1 block w-full rounded-md border border-border px-3 py-2 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
        />
      </div>

      <Button type="submit" disabled={submitting}>
        {submitting ? 'Sending…' : 'Change email'}
      </Button>
    </form>
  );
}
