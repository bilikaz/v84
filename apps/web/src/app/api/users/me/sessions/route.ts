import { NextRequest } from 'next/server';
import { proxyAuthed } from '@/lib/proxy';

// GET /api/users/me/sessions — list active sessions for the current user.
// [v84-4-3-1][front-nextjs:api]
export async function GET(request: NextRequest) {
  return proxyAuthed({ to: '/users/me/sessions', method: 'GET' }, request);
}
