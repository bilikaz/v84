'use client';
// [v84-2-4-2][front-nextjs:pages]

import { useAuth } from '@/common/hooks';

export function DashboardPage() {
  const { user } = useAuth();

  return (
    <div>
      <h1 className="text-2xl font-bold">Welcome, {user?.username}</h1>
      <p className="mt-2 text-gray-600">This is your admin dashboard.</p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-gray-500">Total Users</p>
          <p className="mt-1 text-3xl font-bold text-gray-900">&mdash;</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-gray-500">Active Sessions</p>
          <p className="mt-1 text-3xl font-bold text-gray-900">&mdash;</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-gray-500">System Status</p>
          <p className="mt-1 text-3xl font-bold text-green-600">OK</p>
        </div>
      </div>
    </div>
  );
}
