'use client';
// [v84-3-2-1][front-nextjs:pages]

import { useState } from 'react';
import Link from 'next/link';
import { ForgotPasswordForm } from '../components';

export function ForgotPasswordPage() {
  const [submittedEmail, setSubmittedEmail] = useState<string | null>(null);

  if (submittedEmail) {
    return (
      <main className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-sm space-y-4 text-center">
          <h1 className="text-2xl font-bold">Check Your Email</h1>
          <p className="text-gray-600">
            If an account exists for {submittedEmail}, we sent a password reset link.
          </p>
          <Link href="/auth/login" className="text-sm text-brand hover:underline">
            Back to login
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-6">
        <h1 className="text-center text-2xl font-bold">Forgot Password</h1>

        <ForgotPasswordForm onSuccess={setSubmittedEmail} />

        <p className="text-center text-sm text-gray-600">
          <Link href="/auth/login" className="text-brand hover:underline">
            Back to login
          </Link>
        </p>
      </div>
    </main>
  );
}
