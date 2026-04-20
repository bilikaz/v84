'use client';
// [v84-3-1-1][front-nextjs:pages]

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { GoogleLogin } from '@react-oauth/google';
import { useAuth } from '@/common/hooks';
import { ApiError } from '@/lib';
import { landingPathForUser, isGoogleEnabled } from '@/config';
import { RegistrationForm } from '../components';

export function RegisterPage() {
  const router = useRouter();
  const { loginWithGoogle } = useAuth();
  const googleEnabled = isGoogleEnabled();

  const [error, setError] = useState('');
  const [submittedEmail, setSubmittedEmail] = useState<string | null>(null);

  if (submittedEmail) {
    return (
      <main className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-sm space-y-4 text-center">
          <h1 className="text-2xl font-bold text-text">Check your email</h1>
          <p className="text-textMuted">
            We sent a verification link to <strong>{submittedEmail}</strong>. Open it to
            finish creating your account.
          </p>
          <p className="text-sm text-textSubtle">
            The link expires in 24 hours. You can close this tab and continue from your
            email.
          </p>
          <div className="pt-2">
            <Link href="/auth/login" className="text-sm text-brand hover:underline">
              Back to sign in
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-6">
        <h1 className="text-center text-2xl font-bold">Create Account</h1>
        <p className="text-center text-sm text-textMuted">
          Enter your email and we&apos;ll send you a link to finish setting up.
        </p>

        <RegistrationForm onSuccess={setSubmittedEmail} />

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
            {error && (
              <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>
            )}
            <div className="flex justify-center">
              <GoogleLogin
                onSuccess={async (credentialResponse) => {
                  const idToken = credentialResponse.credential;
                  if (!idToken) {
                    setError('Google sign-up did not return a credential');
                    return;
                  }
                  try {
                    const u = await loginWithGoogle(idToken);
                    router.push(landingPathForUser(u));
                  } catch (err) {
                    setError(err instanceof ApiError ? err.message : 'Google sign-up failed');
                  }
                }}
                onError={() => setError('Google sign-up failed')}
                text="signup_with"
                theme="outline"
                size="large"
                width="280"
              />
            </div>
          </>
        )}

        <p className="text-center text-sm text-textMuted">
          Already have an account?{' '}
          <Link href="/auth/login" className="text-brand hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
