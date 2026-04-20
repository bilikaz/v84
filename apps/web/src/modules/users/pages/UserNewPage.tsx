'use client';
// [v84-2-4-2][front-nextjs:forms]

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ApiError } from '@/lib';
import { Button } from '@/ui/primitives';
import { createUserSchema } from '../schemas';
import { createUser } from '../api';
import { UserForm, type UserFormValues } from '../components';

export function UserNewPage() {
  const router = useRouter();
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(values: UserFormValues) {
    setError('');
    setFieldErrors({});

    const result = createUserSchema.safeParse(values);
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
      await createUser({
        username: values.username,
        email: values.email!,
        password: values.password,
        role: values.role,
      });
      router.push('/admin/users');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create user');
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Create User</h1>
        <Link href="/admin/users">
          <Button size="sm" variant="secondary">← Back to users</Button>
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      <UserForm
        mode="create"
        submitting={submitting}
        submitLabel="Create User"
        fieldErrors={fieldErrors}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
