// [v84-3-2-1][front-nextjs:api]
import { NextRequest } from 'next/server';
import { proxyPublic } from '@/lib/proxy';

// POST /api/auth/forgot-password — sends a password reset email upstream.
export async function POST(request: NextRequest) {
  const body = await request.json();
  return proxyPublic({ to: '/auth/forgot-password', method: 'POST', body }, request);
}
