// [v84-3-1-1][front-nextjs:api]
import { NextRequest } from 'next/server';
import { proxyPublic } from '@/lib/proxy';

// POST /api/auth/register — step 1, just an email. Sends verification mail.
export async function POST(request: NextRequest) {
  const body = await request.json();
  return proxyPublic({ to: '/auth/register', method: 'POST', body }, request);
}
