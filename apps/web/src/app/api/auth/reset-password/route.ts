// [v84-3-2-2][front-nextjs:api]
import { NextRequest } from 'next/server';
import { proxyPublic } from '@/lib/proxy';

// POST /api/auth/reset-password — completes the reset using the emailed token.
export async function POST(request: NextRequest) {
  const body = await request.json();
  return proxyPublic({ to: '/auth/reset-password', method: 'POST', body }, request);
}
