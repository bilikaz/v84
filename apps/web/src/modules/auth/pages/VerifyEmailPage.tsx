'use client';
// [v84-3-1-2][front-nextjs:pages]

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/common/hooks';
import { ApiError } from '@/lib';
import { landingPathForUser } from '@/config';
import { Button } from '@/ui/primitives';
import { checkRegistrationToken } from '../api';
import { completeRegistrationSchema } from '../schemas';

type State =
  | { status: 'checking' }
  | { status: 'invalid'; message: string }
  | { status: 'ready'; email: string };

export function VerifyEmailPage() {
  const router = useRouter();
  const params = useParams<{ token: string }>();
  const token = params?.token ?? '';
  const { completeRegistration } = useAuth();

  const [state, setState] = useState<State>({ status: 'checking' });
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!token) {
      setState({ status: 'invalid', message: 'No verification token in the URL.' });
      return;
    }
    let cancelled = false;
    checkRegistrationToken(token)
      .then((res) => {
        if (cancelled) return;
        setState({ status: 'ready', email: res.email });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: 'invalid',
          message:
            err instanceof ApiError
              ? err.message
              : 'This link is invalid or has expired.',
        });
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setFieldErrors({});

    const result = completeRegistrationSchema.safeParse({ username, password });
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
      const u = await completeRegistration(token, username, password);
      router.push(landingPathForUser(u));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not complete registration');
      setSubmitting(false);
    }
  }

  if (state.status === 'checking') {
    return (
      <main className="flex min-h-screen items-center justify-center px-4">
        <p className="text-textMuted">Checking verification link…</p>
      </main>
    );
  }

  if (state.status === 'invalid') {
    return (
      <main className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-sm space-y-4 text-center">
          <h1 className="text-2xl font-bold text-text">Link not valid</h1>
          <p className="text-textMuted">{state.message}</p>
          <p className="text-sm text-textSubtle">
            Verification links expire after 24 hours.
          </p>
          <div className="pt-2">
            <Link href="/auth/register" className="text-sm text-brand hover:underline">
              Start over
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-6">
        <h1 className="text-center text-2xl font-bold text-text">Finish setting up</h1>
        <p className="text-center text-sm text-textMuted">
          Choose a username and password to finish creating your account.
        </p>

        {error && (
          <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text">Email</label>
            <input
              type="email"
              value={state.email}
              readOnly
              className="mt-1 block w-full rounded-md border border-border bg-surfaceMuted px-3 py-2 text-textMuted shadow-sm"
            />
          </div>

          <div>
            <label htmlFor="username" className="block text-sm font-medium text-text">
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="mt-1 block w-full rounded-md border border-border px-3 py-2 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
              autoComplete="username"
            />
            {fieldErrors.username && (
              <p className="mt-1 text-sm text-danger">{fieldErrors.username}</p>
            )}
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-text">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 block w-full rounded-md border border-border px-3 py-2 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
              autoComplete="new-password"
            />
            {fieldErrors.password && (
              <p className="mt-1 text-sm text-danger">{fieldErrors.password}</p>
            )}
          </div>

          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? 'Creating account...' : 'Create account'}
          </Button>
        </form>
      </div>
    </main>
  );
}
