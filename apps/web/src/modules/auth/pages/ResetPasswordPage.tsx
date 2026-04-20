'use client';
// [v84-3-2-2][front-nextjs:pages]

import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { ResetPasswordForm } from '../components';

export function ResetPasswordPage() {
  const router = useRouter();
  const params = useParams<{ token: string }>();
  const token = params?.token ?? '';

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-6">
        <h1 className="text-center text-2xl font-bold">Reset Password</h1>

        <ResetPasswordForm token={token} onSuccess={() => router.push('/auth/login')} />

        <p className="text-center text-sm text-gray-600">
          <Link href="/auth/login" className="text-brand hover:underline">
            Back to login
          </Link>
        </p>
      </div>
    </main>
  );
}
