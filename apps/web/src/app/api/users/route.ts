// [v84-2-3-1][front-nextjs:api]
import { NextRequest } from 'next/server';
import { proxyAuthed } from '@/lib/proxy';

// GET /api/users — admin: list all users.
export async function GET(request: NextRequest) {
  return proxyAuthed({ to: '/users', method: 'GET' }, request);
}

// POST /api/users — admin: create a user.
export async function POST(request: NextRequest) {
  const body = await request.json();
  return proxyAuthed({ to: '/users', method: 'POST', body }, request);
}
