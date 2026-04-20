import { NextRequest } from 'next/server';
import { proxyAuthed } from '@/lib/proxy';

// POST /api/users/me/2fa/verify — confirm setup with the 6-digit TOTP code.
// [v84-4-1-1][front-nextjs:api]
export async function POST(request: NextRequest) {
  const body = await request.json();
  return proxyAuthed({ to: '/users/me/2fa/verify', method: 'POST', body }, request);
}
