'use client';
// [v84-3-1-1][front-nextjs:forms]

import { useState } from 'react';
import { ApiError } from '@/lib';
import { Button } from '@/ui/primitives';
import { registerSchema } from '../schemas';
import { useAuth } from '@/common/hooks';

export interface RegistrationFormProps {
  onSuccess: (email: string) => void;
}

export function RegistrationForm({ onSuccess }: RegistrationFormProps) {
  const { startRegistration } = useAuth();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setFieldErrors({});

    const result = registerSchema.safeParse({ email });
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
      await startRegistration(email);
      onSuccess(email);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not start registration');
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
          <label htmlFor="email" className="block text-sm font-medium text-text">
            Email
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 block w-full rounded-md border border-border px-3 py-2 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
            autoComplete="email"
          />
          {fieldErrors.email && (
            <p className="mt-1 text-sm text-danger">{fieldErrors.email}</p>
          )}
        </div>

        <Button type="submit" disabled={submitting} className="w-full">
          {submitting ? 'Sending link...' : 'Continue'}
        </Button>
      </form>
    </>
  );
}
