'use client';
// [v84-2-4-3][front-nextjs:pages]

import Link from 'next/link';
import type { ReactNode } from 'react';
import { useAuth } from '../hooks';
import type { UserRole } from '@/modules/users/types';

export function RequireRole({
  role,
  children,
}: {
  role: UserRole;
  children: ReactNode;
}) {
  const { user } = useAuth();

  if (!user || user.role !== role) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-600">Access Denied</h1>
          <p className="mt-2 text-gray-600">You do not have permission to view this page.</p>
          <Link href="/" className="mt-4 inline-block text-sm text-brand hover:underline">
            Go home
          </Link>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
