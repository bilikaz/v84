// [v84-2-3-1][front-nextjs:api]
import { NextRequest, NextResponse } from 'next/server';
import { apiBase, createSession, setSessionCookie, type UpstreamAuthTokens } from '@/lib/server-auth';

// POST /api/auth/login
//
// Forwards email + password (+ optional totpCode) to the upstream /auth/login.
// If the upstream returns `requiresTwoFactor`, we pass that through unchanged
// without creating a session — the frontend will then re-submit with totpCode.
// Otherwise we stash the tokens server-side and set the opaque session cookie.
export async function POST(request: NextRequest) {
  const body = await request.json();

  let upstream: Response;
  try {
    upstream = await fetch(`${apiBase()}/auth/login`, {
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
    const data = await upstream.json().catch(() => ({ message: 'Login failed' }));
    return NextResponse.json(data, { status: upstream.status });
  }

  const data = (await upstream.json()) as UpstreamAuthTokens | { requiresTwoFactor: true };

  if ('requiresTwoFactor' in data) {
    return NextResponse.json({ requiresTwoFactor: true });
  }

  const sessionId = await createSession(data);
  return setSessionCookie(NextResponse.json({ ok: true }), sessionId);
}
