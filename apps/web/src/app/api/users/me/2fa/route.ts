import { NextRequest } from 'next/server';
import { proxyAuthed } from '@/lib/proxy';

// DELETE /api/users/me/2fa — disable 2FA (requires password + current TOTP).
// [v84-4-1-1][front-nextjs:api]
export async function DELETE(request: NextRequest) {
  const body = await request.json();
  return proxyAuthed({ to: '/users/me/2fa', method: 'DELETE', body }, request);
}
