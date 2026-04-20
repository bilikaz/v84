'use client';
// [v84-2-4-2][front-nextjs:forms]

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { ApiError } from '@/lib';
import { Button } from '@/ui/primitives';
import { editUserSchema } from '../schemas';
import { getUser, updateUser } from '../api';
import { UserForm, type UserFormValues } from '../components';
import type { UserRole } from '../types';

export function UserEditPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();

  const [initial, setInitial] = useState<{ username: string; role: UserRole } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const user = await getUser(params.id);
        setInitial({ username: user.username, role: user.role });
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Failed to load user');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [params.id]);

  async function handleSubmit(values: UserFormValues) {
    setError('');
    setFieldErrors({});

    const result = editUserSchema.safeParse({
      username: values.username,
      password: values.password,
      role: values.role,
    });
    if (!result.success) {
      const errs: Record<string, string> = {};
      result.error.issues.forEach((i) => {
        errs[i.path[0] as string] = i.message;
      });
      setFieldErrors(errs);
      return;
    }

    setSubmitting(true);
    try {
      const data: { username: string; role: UserRole; password?: string } = {
        username: values.username,
        role: values.role,
      };
      if (values.password) data.password = values.password;
      await updateUser(params.id, data);
      router.push('/admin/users');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to update user');
      setSubmitting(false);
    }
  }

  if (loading) {
    return <p className="text-gray-500">Loading user...</p>;
  }

  return (
    <div className="mx-auto max-w-lg">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Edit User</h1>
        <Link href="/admin/users">
          <Button size="sm" variant="secondary">← Back to users</Button>
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      <UserForm
        mode="edit"
        initial={initial ?? undefined}
        submitting={submitting}
        submitLabel="Save Changes"
        fieldErrors={fieldErrors}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
