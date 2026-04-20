'use client';

import { useAuth } from '@/common/hooks';
import { Card } from '@/ui/feedback';
import { PasswordChangeForm } from '../components/PasswordChangeForm';
import { EmailChangeForm } from '../components/EmailChangeForm';
import { TwoFactorSetup } from '../components/TwoFactorSetup';
import { SessionsList } from '../components/SessionsList';

// [v84-4-1-1][front-nextjs:pages]
export function AccountSettingsPage() {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold text-text sm:text-4xl">Account settings</h1>
        <p className="mt-2 text-textMuted">Manage your sign-in and security details.</p>
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Profile">
          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-textMuted">Username</dt>
              <dd className="text-text">{user.username}</dd>
            </div>
            <div>
              <dt className="text-textMuted">Email</dt>
              <dd className="text-text">{user.email}</dd>
            </div>
            <div>
              <dt className="text-textMuted">Role</dt>
              <dd className="text-text capitalize">{user.role}</dd>
            </div>
          </dl>
        </Card>

        <Card title="Email">
          <EmailChangeForm />
        </Card>

        <Card title="Password">
          <PasswordChangeForm />
        </Card>

        <Card title="Two-factor authentication" className="lg:col-span-2">
          <TwoFactorSetup initiallyEnabled={user.twoFactorEnabled} />
        </Card>

        <Card title="Active sessions" className="lg:col-span-2">
          <SessionsList />
        </Card>
      </div>
    </div>
  );
}
