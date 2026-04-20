import { NextRequest } from 'next/server';
import { proxyAuthed } from '@/lib/proxy';

// DELETE /api/users/me/sessions/all — revoke every session for the current user.
// [v84-4-3-2][front-nextjs:api]
export async function DELETE(request: NextRequest) {
  return proxyAuthed({ to: '/users/me/sessions/all', method: 'DELETE' }, request);
}
