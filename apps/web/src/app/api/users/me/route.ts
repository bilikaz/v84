import { NextRequest } from 'next/server';
import { proxyAuthed } from '@/lib/proxy';

// GET /api/users/me — current user profile.
// [v84-2-3-1][front-nextjs:api]
export async function GET(request: NextRequest) {
  return proxyAuthed({ to: '/users/me', method: 'GET' }, request);
}

// PATCH /api/users/me — update username / password.
export async function PATCH(request: NextRequest) {
  const body = await request.json();
  return proxyAuthed({ to: '/users/me', method: 'PATCH', body }, request);
}
