import { NextRequest } from 'next/server';
import { proxyPublic } from '@/lib/proxy';

// GET /api/auth/register/check?token=... — step 1.5, returns the email tied to the token.
// [v84-3-1-2][front-nextjs:api]
export async function GET(request: NextRequest) {
  const token = request.nextUrl.searchParams.get('token') ?? '';
  return proxyPublic(
    {
      to: '/auth/register/check',
      method: 'GET',
      query: `token=${encodeURIComponent(token)}`,
    },
    request,
  );
}
