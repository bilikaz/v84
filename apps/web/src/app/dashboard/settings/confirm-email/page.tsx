'use client';

import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { ApiError } from '@/lib';
import { useAuth } from '@/common/hooks';
import { confirmEmailChange } from '@/modules/account/api';

// [v84-4-2-2][front-nextjs:pages]
export default function ConfirmEmailChangePage() {
  const params = useSearchParams();
  const router = useRouter();
  const { refreshUser } = useAuth();
  const token = params.get('token');

  const [status, setStatus] = useState<'confirming' | 'success' | 'error'>('confirming');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setError('Missing confirmation token');
      return;
    }

    confirmEmailChange(token)
      .then(() => {
        setStatus('success');
        refreshUser();
      })
      .catch((err) => {
        setStatus('error');
        setError(err instanceof ApiError ? err.message : 'Could not confirm email change');
      });
  }, [token, refreshUser]);

  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <div className="max-w-md text-center">
        {status === 'confirming' && (
          <p className="text-textMuted">Confirming your new email address…</p>
        )}
        {status === 'success' && (
          <>
            <h1 className="text-2xl font-bold text-text">Email updated</h1>
            <p className="mt-2 text-textMuted">
              Your email address has been changed successfully.
            </p>
            <button
              onClick={() => router.push('/dashboard/settings')}
              className="mt-4 rounded-md bg-brand px-4 py-2 text-sm font-medium text-textInverse hover:bg-brandHover"
            >
              Back to settings
            </button>
          </>
        )}
        {status === 'error' && (
          <>
            <h1 className="text-2xl font-bold text-danger">Confirmation failed</h1>
            <p className="mt-2 text-textMuted">{error}</p>
            <button
              onClick={() => router.push('/dashboard/settings')}
              className="mt-4 rounded-md bg-brand px-4 py-2 text-sm font-medium text-textInverse hover:bg-brandHover"
            >
              Back to settings
            </button>
          </>
        )}
      </div>
    </div>
  );
}
