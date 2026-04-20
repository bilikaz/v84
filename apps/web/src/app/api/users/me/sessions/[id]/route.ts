import { NextRequest } from 'next/server';
import { proxyAuthed } from '@/lib/proxy';

// DELETE /api/users/me/sessions/:id — revoke a single session by id.
// [v84-4-3-2][front-nextjs:api]
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return proxyAuthed(
    { to: `/users/me/sessions/${encodeURIComponent(id)}`, method: 'DELETE' },
    request,
  );
}
