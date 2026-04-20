'use client';
// [v84-2-4-2][front-nextjs:forms]

import { useState } from 'react';
import type { UserRole } from '../types';

export interface UserFormValues {
  username: string;
  email?: string;
  password: string;
  role: UserRole;
}

interface UserFormProps {
  mode: 'create' | 'edit';
  initial?: Partial<UserFormValues>;
  submitting?: boolean;
  submitLabel: string;
  fieldErrors?: Record<string, string>;
  onSubmit: (values: UserFormValues) => void;
}

export function UserForm({
  mode,
  initial,
  submitting = false,
  submitLabel,
  fieldErrors = {},
  onSubmit,
}: UserFormProps) {
  const [username, setUsername] = useState(initial?.username ?? '');
  const [email, setEmail] = useState(initial?.email ?? '');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<UserRole>(initial?.role ?? 'user');

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      username,
      email: mode === 'create' ? email : undefined,
      password,
      role,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="username" className="block text-sm font-medium text-gray-700">
          Username
        </label>
        <input
          id="username"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
        />
        {fieldErrors.username && (
          <p className="mt-1 text-sm text-red-600">{fieldErrors.username}</p>
        )}
      </div>

      {mode === 'create' && (
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-gray-700">
            Email
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
          />
          {fieldErrors.email && (
            <p className="mt-1 text-sm text-red-600">{fieldErrors.email}</p>
          )}
        </div>
      )}

      <div>
        <label htmlFor="password" className="block text-sm font-medium text-gray-700">
          Password
          {mode === 'edit' && (
            <span className="font-normal text-gray-400"> (leave blank to keep current)</span>
          )}
        </label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
        />
        {fieldErrors.password && (
          <p className="mt-1 text-sm text-red-600">{fieldErrors.password}</p>
        )}
      </div>

      <div>
        <label htmlFor="role" className="block text-sm font-medium text-gray-700">
          Role
        </label>
        <select
          id="role"
          value={role}
          onChange={(e) => setRole(e.target.value as UserRole)}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
        >
          <option value="user">User</option>
          <option value="admin">Admin</option>
        </select>
      </div>

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white shadow hover:bg-brandHover disabled:opacity-50"
      >
        {submitting ? `${submitLabel}...` : submitLabel}
      </button>
    </form>
  );
}
