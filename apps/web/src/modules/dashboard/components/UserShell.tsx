'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { ReactNode } from 'react';
import { useAuth } from '@/common/hooks';
import { RequireAuth } from '@/common/guards';
import { copy } from '@/config';
import { Button } from '@/ui/primitives';

// [v84-1-4][front-nextjs:pages]
export function UserShell({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <UserShellInner>{children}</UserShellInner>
    </RequireAuth>
  );
}

function UserShellInner({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.push('/auth/login');
  }

  return (
    <div className="flex min-h-screen flex-col bg-surfaceMuted">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link href="/dashboard" className="flex items-center gap-3">
            <img src="/brand/logo.svg" alt={copy.appName} className="h-10 w-10" />
            <span className="text-lg font-bold text-text">{copy.appName}</span>
          </Link>

          <div className="flex items-center gap-4">
            {user?.role === 'admin' && (
              <Link href="/admin">
                <Button size="sm" variant="secondary">Admin</Button>
              </Link>
            )}
            <Link href="/dashboard/settings">
              <Button size="sm" variant="secondary">Settings</Button>
            </Link>
            <span className="hidden text-sm text-textMuted sm:inline">{user?.username}</span>
            <Button size="sm" variant="secondary" onClick={handleLogout}>
              Logout
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-12">
        {children}
      </main>

      <footer className="border-t border-border bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-6 text-center text-xs text-textSubtle sm:px-6">
          © V84
        </div>
      </footer>
    </div>
  );
}
