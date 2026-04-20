'use client';
// [v84-2-4-2][front-nextjs:pages]

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { ReactNode } from 'react';
import { useAuth } from '@/common/hooks';
import { RequireAuth, RequireRole } from '@/common/guards';
import { copy } from '@/config';
import { Button } from '@/ui/primitives';

const navItems = [
  { href: '/admin', label: 'Dashboard' },
  { href: '/admin/users', label: 'Users' },
];

export function AdminShell({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <RequireRole role="admin">
        <AdminShellInner>{children}</AdminShellInner>
      </RequireRole>
    </RequireAuth>
  );
}

function AdminShellInner({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.push('/auth/login');
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="hidden w-64 flex-shrink-0 border-r border-gray-200 bg-white md:block">
        <div className="flex h-16 items-center gap-3 border-b border-gray-200 px-6">
          <Link href="/admin" className="flex items-center gap-3">
            <img src="/brand/logo.svg" alt={copy.appName} className="h-10 w-10" />
            <span className="text-lg font-bold text-gray-900">Admin</span>
          </Link>
        </div>
        <nav className="mt-4 space-y-1 px-3">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block rounded-md px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-gray-900"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      {/* Main area */}
      <div className="flex flex-1 flex-col">
        {/* Top bar */}
        <header className="flex h-16 items-center justify-between border-b border-gray-200 bg-white px-4 sm:px-6">
          {/* Mobile nav */}
          <div className="flex items-center gap-4 md:hidden">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="text-sm font-medium text-gray-700 hover:text-gray-900"
              >
                {item.label}
              </Link>
            ))}
          </div>
          <div className="hidden md:block" />

          <div className="flex items-center gap-3">
            <Link href="/dashboard/settings">
              <Button size="sm" variant="secondary">Settings</Button>
            </Link>
            <span className="hidden text-sm text-textMuted sm:inline">{user?.username}</span>
            <Button size="sm" variant="secondary" onClick={handleLogout}>
              Logout
            </Button>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
