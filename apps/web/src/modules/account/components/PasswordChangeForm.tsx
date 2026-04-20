'use client';

import { useState } from 'react';
import { ApiError } from '@/lib';
import { Button } from '@/ui/primitives';
import { changePassword } from '../api';
import { changePasswordSchema } from '../schemas';

// [v84-4-2-1][front-nextjs:forms]
export function PasswordChangeForm() {
  const [currentPassword, setCurrentPassword] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setSuccess('');
    setFieldErrors({});

    const result = changePasswordSchema.safeParse({
      currentPassword,
      password,
      confirmPassword,
    });
    if (!result.success) {
      const errs: Record<string, string> = {};
      result.error.issues.forEach((i) => {
        errs[i.path[0] as string] = i.message;
      });
      setFieldErrors(errs);
      return;
    }

    setSubmitting(true);
    try {
      await changePassword(currentPassword, password);
      setCurrentPassword('');
      setPassword('');
      setConfirmPassword('');
      setSuccess('Password updated.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not update password');
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

      <Field
        id="currentPassword"
        label="Current password"
        type="password"
        value={currentPassword}
        onChange={setCurrentPassword}
        error={fieldErrors.currentPassword}
        autoComplete="current-password"
      />
      <Field
        id="password"
        label="New password"
        type="password"
        value={password}
        onChange={setPassword}
        error={fieldErrors.password}
        autoComplete="new-password"
      />
      <Field
        id="confirmPassword"
        label="Confirm new password"
        type="password"
        value={confirmPassword}
        onChange={setConfirmPassword}
        error={fieldErrors.confirmPassword}
        autoComplete="new-password"
      />

      <Button type="submit" disabled={submitting}>
        {submitting ? 'Saving…' : 'Update password'}
      </Button>
    </form>
  );
}

// Tiny private field component to keep the form readable.
function Field({
  id,
  label,
  type,
  value,
  onChange,
  error,
  autoComplete,
}: {
  id: string;
  label: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
  error?: string;
  autoComplete?: string;
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-text">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        className="mt-1 block w-full rounded-md border border-border px-3 py-2 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
      />
      {error && <p className="mt-1 text-sm text-danger">{error}</p>}
    </div>
  );
}
