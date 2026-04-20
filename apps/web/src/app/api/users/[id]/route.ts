// [v84-2-3-1][front-nextjs:api]
import { NextRequest } from 'next/server';
import { proxyAuthed } from '@/lib/proxy';

// GET /api/users/:id — admin: read one user.
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return proxyAuthed({ to: `/users/${encodeURIComponent(id)}`, method: 'GET' }, request);
}

// PATCH /api/users/:id — admin: update one user.
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const body = await request.json();
  return proxyAuthed(
    { to: `/users/${encodeURIComponent(id)}`, method: 'PATCH', body },
    request,
  );
}

// DELETE /api/users/:id — admin: delete one user.
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return proxyAuthed({ to: `/users/${encodeURIComponent(id)}`, method: 'DELETE' }, request);
}
