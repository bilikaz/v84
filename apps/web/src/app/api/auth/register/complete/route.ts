import { NextRequest, NextResponse } from 'next/server';
import { apiBase, createSession, setSessionCookie, type UpstreamAuthTokens } from '@/lib/server-auth';

// POST /api/auth/register/complete
//
// User followed the verification link, picked a username + password, and we
// finalize the account. The upstream returns tokens — we stash them and set
// the session cookie just like login does.
// [v84-3-1-1][front-nextjs:api]
export async function POST(request: NextRequest) {
  const body = await request.json();

  let upstream: Response;
  try {
    upstream = await fetch(`${apiBase()}/auth/register/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch {
    return NextResponse.json(
      { message: 'Authentication service unavailable', statusCode: 503 },
      { status: 503 },
    );
  }

  if (!upstream.ok) {
    const data = await upstream.json().catch(() => ({ message: 'Registration failed' }));
    return NextResponse.json(data, { status: upstream.status });
  }

  const tokens = (await upstream.json()) as UpstreamAuthTokens;
  const sessionId = await createSession(tokens);
  return setSessionCookie(NextResponse.json({ ok: true }), sessionId);
}
