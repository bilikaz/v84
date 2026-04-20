import { NextRequest, NextResponse } from 'next/server';
import { apiBase, createSession, setSessionCookie, type UpstreamAuthTokens } from '@/lib/server-auth';

// POST /api/auth/google
//
// Browser hands the Google ID token (received from the Google Identity widget)
// to the BFF. We forward it to the upstream /auth/google, which verifies the
// token, auto-provisions the user if needed, and returns app tokens. Same
// session-creation flow as password login.
// [v84-2-3-1][front-nextjs:api]
export async function POST(request: NextRequest) {
  const body = await request.json();

  let upstream: Response;
  try {
    upstream = await fetch(`${apiBase()}/auth/google`, {
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
    const data = await upstream.json().catch(() => ({ message: 'Google sign-in failed' }));
    return NextResponse.json(data, { status: upstream.status });
  }

  const tokens = (await upstream.json()) as UpstreamAuthTokens;
  const sessionId = await createSession(tokens);
  return setSessionCookie(NextResponse.json({ ok: true }), sessionId);
}
