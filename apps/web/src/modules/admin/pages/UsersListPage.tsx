'use client';
// [v84-2-4-2][front-nextjs:pages]

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ApiError } from '@/lib';
import { Button } from '@/ui/primitives';
import { Modal } from '@/ui/feedback';
import { listUsers, deleteUser } from '../../users/api';
import type { User } from '../../users/types';

export function UsersListPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function fetchUsers(nextPage = page) {
    try {
      const data = await listUsers({ page: nextPage, limit: 20 });
      setUsers(data.items);
      setTotalPages(data.pages);
      setPage(data.page);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchUsers(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function confirmDelete() {
    if (!userToDelete) return;
    setDeleting(true);
    try {
      await deleteUser(userToDelete.id);
      setUserToDelete(null);
      await fetchUsers(users.length === 1 && page > 1 ? page - 1 : page);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to delete user');
    } finally {
      setDeleting(false);
    }
  }

  if (loading) {
    return <p className="text-textMuted">Loading users...</p>;
  }

  if (error) {
    return <div className="rounded-md border border-danger/20 bg-danger/10 p-3 text-sm text-danger">{error}</div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text">Users</h1>
        <Link href="/admin/users/new">
          <Button variant="primary">Create User</Button>
        </Link>
      </div>

      <div className="mt-6 overflow-x-auto">
        <table className="w-full min-w-[600px] text-left text-sm">
          <thead className="border-b border-border text-xs font-medium uppercase text-textMuted">
            <tr>
              <th className="px-4 py-3">Username</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Created</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-text">
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-surfaceMuted">
                <td className="px-4 py-3 font-medium">{u.username}</td>
                <td className="px-4 py-3 text-textMuted">{u.email}</td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                      u.role === 'admin'
                        ? 'bg-brand text-textInverse'
                        : 'bg-surfaceMuted text-textMuted border border-border'
                    }`}
                  >
                    {u.role}
                  </span>
                </td>
                <td className="px-4 py-3 text-textMuted">
                  {new Date(u.createdAt).toLocaleDateString()}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => router.push(`/admin/users/${u.id}/edit`)}
                    >
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => setUserToDelete(u)}
                    >
                      Delete
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-textMuted">
                  No users found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-end gap-2 text-sm text-textMuted">
          <Button
            size="sm"
            variant="secondary"
            disabled={page <= 1 || loading}
            onClick={() => fetchUsers(page - 1)}
          >
            Previous
          </Button>
          <span>
            Page {page} of {totalPages}
          </span>
          <Button
            size="sm"
            variant="secondary"
            disabled={page >= totalPages || loading}
            onClick={() => fetchUsers(page + 1)}
          >
            Next
          </Button>
        </div>
      )}

      <Modal
        open={userToDelete !== null}
        title="Delete user"
        confirmLabel="Delete"
        cancelLabel="Cancel"
        confirmVariant="danger"
        loading={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setUserToDelete(null)}
      >
        Are you sure you want to delete <strong>{userToDelete?.username}</strong>? This
        action cannot be undone.
      </Modal>
    </div>
  );
}
