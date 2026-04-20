import { NextRequest } from 'next/server';
import { proxyAuthed } from '@/lib/proxy';

// POST /api/users/me/2fa/enable — generate TOTP secret for setup.
// [v84-4-1-1][front-nextjs:api]
export async function POST(request: NextRequest) {
  return proxyAuthed({ to: '/users/me/2fa/enable', method: 'POST' }, request);
}
