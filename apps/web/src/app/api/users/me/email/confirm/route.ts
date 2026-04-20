import { NextRequest } from 'next/server';
import { proxyAuthed } from '@/lib/proxy';

// POST /api/users/me/email/confirm — confirm email change with token.
// [v84-4-2-2][front-nextjs:api]
export async function POST(request: NextRequest) {
  const body = await request.json();
  return proxyAuthed({ to: '/users/me/email/confirm', method: 'POST', body }, request);
}
