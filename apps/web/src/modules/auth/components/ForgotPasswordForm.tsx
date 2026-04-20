'use client';
// [v84-3-2-1][front-nextjs:forms]

import { useState } from 'react';
import { ApiError } from '@/lib';
import { forgotPasswordSchema } from '../schemas';
import { requestPasswordReset } from '../api';

export interface ForgotPasswordFormProps {
  onSuccess: (email: string) => void;
}

export function ForgotPasswordForm({ onSuccess }: ForgotPasswordFormProps) {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setFieldErrors({});

    const result = forgotPasswordSchema.safeParse({ email });
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
      await requestPasswordReset(email);
      onSuccess(email);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong');
    } finally {
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
          <label htmlFor="email" className="block text-sm font-medium text-gray-700">
            Email
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
          />
          {fieldErrors.email && (
            <p className="mt-1 text-sm text-red-600">{fieldErrors.email}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white shadow hover:bg-brandHover disabled:opacity-50"
        >
          {submitting ? 'Sending...' : 'Send Reset Link'}
        </button>
      </form>
    </>
  );
}
