'use client';
// [v84-2-4-2][front-nextjs:pages]

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { GoogleLogin } from '@react-oauth/google';
import { useAuth } from '@/common/hooks';
import { ApiError } from '@/lib';
import { landingPathForUser, isGoogleEnabled } from '@/config';
import { loginSchema } from '../schemas';

export function LoginPage() {
  const router = useRouter();
  const { login, loginWithGoogle } = useAuth();
  const googleEnabled = isGoogleEnabled();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [showTotp, setShowTotp] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setFieldErrors({});

    const result = loginSchema.safeParse({ email, password, totpCode: totpCode || undefined });
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
      const res = await login(email, password, totpCode || undefined);
      if ('requiresTwoFactor' in res) {
        setShowTotp(true);
        setSubmitting(false);
        return;
      }
      router.push(landingPathForUser(res.user));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Login failed');
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-6">
        <h1 className="text-center text-2xl font-bold">Sign In</h1>

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

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700">
              Password
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

          {showTotp && (
            <div>
              <label htmlFor="totpCode" className="block text-sm font-medium text-gray-700">
                Two-Factor Code
              </label>
              <input
                id="totpCode"
                type="text"
                inputMode="numeric"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
              />
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white shadow hover:bg-brandHover disabled:opacity-50"
          >
            {submitting ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        {googleEnabled && (
          <>
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-border" />
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="bg-surface px-2 uppercase text-textMuted">or</span>
              </div>
            </div>
            <div className="flex justify-center">
              <GoogleLogin
                onSuccess={async (credentialResponse) => {
                  const idToken = credentialResponse.credential;
                  if (!idToken) {
                    setError('Google sign-in did not return a credential');
                    return;
                  }
                  try {
                    const u = await loginWithGoogle(idToken);
                    router.push(landingPathForUser(u));
                  } catch (err) {
                    setError(err instanceof ApiError ? err.message : 'Google sign-in failed');
                  }
                }}
                onError={() => setError('Google sign-in failed')}
                theme="outline"
                size="large"
                width="280"
              />
            </div>
          </>
        )}

        <p className="text-center text-sm text-gray-600">
          <Link href="/auth/forgot-password" className="text-brand hover:underline">
            Forgot password?
          </Link>
          {' · '}
          <Link href="/auth/register" className="text-brand hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </main>
  );
}
