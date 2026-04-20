// [v84-2-3-1][front-nextjs:api]
import { NextRequest } from 'next/server';
import { destroySession, getAccessToken, apiBase } from '@/lib/server-auth';

// POST /api/auth/logout
//
// Calls the upstream /auth/logout to revoke the session server-side, then
// clears the local cookie + drops the session from BFF storage. We swallow
// upstream errors here — the user-facing logout should always succeed.
export async function POST(request: NextRequest) {
  const token = await getAccessToken(request);
  if (typeof token === 'string') {
    try {
      await fetch(`${apiBase()}/auth/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      });
    } catch {
      // ignore — we still want to drop the local session
    }
  }
  return destroySession(request);
}
