'use client';
// [v84-3-1-2][front-nextjs:pages]

import { useAuth } from '@/common/hooks';
import { Card } from '@/ui/feedback';

export function UserDashboardPage() {
  const { user } = useAuth();

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold text-text sm:text-4xl">
          Welcome back, {user?.username}
        </h1>
        <p className="mt-2 text-textMuted">
          Here&apos;s a quick look at your account.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card title="Account">
          <dl className="space-y-2 text-sm">
            <div>
              <dt className="text-textMuted">Username</dt>
              <dd className="text-text">{user?.username}</dd>
            </div>
            <div>
              <dt className="text-textMuted">Email</dt>
              <dd className="text-text">{user?.email}</dd>
            </div>
            <div>
              <dt className="text-textMuted">Role</dt>
              <dd className="text-text capitalize">{user?.role}</dd>
            </div>
          </dl>
        </Card>

        <Card title="Security">
          <p className="text-sm text-textMuted">
            Two-factor authentication and password settings will live here.
          </p>
        </Card>

        <Card title="Activity">
          <p className="text-sm text-textMuted">
            Recent sessions and notifications will appear here.
          </p>
        </Card>
      </div>
    </div>
  );
}
