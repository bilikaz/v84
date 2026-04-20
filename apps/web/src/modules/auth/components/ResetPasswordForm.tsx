'use client';
// [v84-3-2-2][front-nextjs:forms]

import { useState } from 'react';
import { ApiError } from '@/lib';
import { resetPasswordSchema } from '../schemas';
import { resetPassword } from '../api';

export interface ResetPasswordFormProps {
  token: string;
  onSuccess: () => void;
}

export function ResetPasswordForm({ token, onSuccess }: ResetPasswordFormProps) {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setFieldErrors({});

    const result = resetPasswordSchema.safeParse({ password, confirmPassword });
    if (!result.success) {
      const errs: Record<string, string> = {};
      result.error.issues.forEach((i) => {
        errs[i.path[0] as string] = i.message;
      });
      setFieldErrors(errs);
      return;
    }

    if (!token) {
      setError('Missing reset token');
      return;
    }

    setSubmitting(true);
    try {
      await resetPassword(token, password);
      onSuccess();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Reset failed');
      setSubmitting(false);
    }
  }

  return (
    <>
      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="password" className="block text-sm font-medium text-gray-700">
            New Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
          />
          {fieldErrors.password && (
            <p className="mt-1 text-sm text-red-600">{fieldErrors.password}</p>
          )}
        </div>

        <div>
          <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700">
            Confirm Password
          </label>
          <input
            id="confirmPassword"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
          />
          {fieldErrors.confirmPassword && (
            <p className="mt-1 text-sm text-red-600">{fieldErrors.confirmPassword}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white shadow hover:bg-brandHover disabled:opacity-50"
        >
          {submitting ? 'Resetting...' : 'Reset Password'}
        </button>
      </form>
    </>
  );
}
