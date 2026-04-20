// [v84-2-3-1][front-nextjs:api]
// Generic helpers used by every BFF route handler in `apps/web/src/app/api/*`.
//
// `proxyAuthed`  — forwards the request to the upstream api with the bearer token attached.
// `proxyPublic` — forwards the request without auth (for /auth/login etc.).
//
// Security:
//   - CSRF: state-changing methods (POST/PATCH/DELETE) require a same-origin
//     Origin/Referer header. Cookies are SameSite=Lax so cross-site forms can't
//     send them; the Origin check defends against credentialed cross-site fetch.
//   - 401 auto-refresh: if upstream returns 401 for an authed call, we try a
//     forced token refresh and retry the request once before surfacing the 401.
//
// Both copy the upstream status code and JSON body verbatim so client-side error
// handling stays consistent regardless of which route was hit.

import { NextRequest, NextResponse } from 'next/server';
import { apiBase, forceRefreshAccessToken, getAccessToken } from './server-auth';

type Method = 'GET' | 'POST' | 'PATCH' | 'DELETE';

interface ProxyOptions {
  /** Upstream path beginning with `/` (e.g. `/users/me`). The api base URL is prepended. */
  to: string;
  method: Method;
  /** If true, attach the session's access token; if false, forward without auth. */
  authed: boolean;
  /** If set, forwards the request body as JSON. */
  body?: unknown;
  /** Optional query string already URL-encoded (no leading `?`). */
  query?: string;
}

const STATE_CHANGING: ReadonlySet<Method> = new Set(['POST', 'PATCH', 'DELETE']);

function forbidden(message = 'Forbidden'): NextResponse {
  return NextResponse.json({ message, statusCode: 403 }, { status: 403 });
}

/**
 * Verify that a state-changing request came from the same origin as the BFF.
 * Returns null if OK, or a 403 response to return as-is.
 */
function assertSameOrigin(request: NextRequest, method: Method): NextResponse | null {
  if (!STATE_CHANGING.has(method)) return null;

  const origin = request.headers.get('origin');
  const referer = request.headers.get('referer');
  const host = request.headers.get('host');
  if (!host) return forbidden('Missing host header');

  const expected = `${request.nextUrl.protocol}//${host}`;
  if (origin) {
    return origin === expected ? null : forbidden('Cross-origin request blocked');
  }
  if (referer) {
    try {
      const refOrigin = new URL(referer).origin;
      return refOrigin === expected ? null : forbidden('Cross-origin request blocked');
    } catch {
      return forbidden('Invalid referer');
    }
  }
  return forbidden('Missing origin header');
}

async function callUpstream(
  to: string,
  method: Method,
  token: string | null,
  body: unknown,
  query: string | undefined,
): Promise<Response> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const url = `${apiBase()}${to}${query ? `?${query}` : ''}`;
  return fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

async function forward({ to, method, authed, body, query }: ProxyOptions, request: NextRequest) {
  const csrf = assertSameOrigin(request, method);
  if (csrf) return csrf;

  let token: string | null = null;
  if (authed) {
    const resolved = await getAccessToken(request);
    if (resolved instanceof NextResponse) return resolved;
    token = resolved;
  }

  let upstream: Response;
  try {
    upstream = await callUpstream(to, method, token, body, query);
  } catch {
    return NextResponse.json(
      { message: 'Upstream api unreachable', statusCode: 502 },
      { status: 502 },
    );
  }

  // 401 auto-refresh: if authed and upstream rejected, refresh token and retry once.
  if (authed && upstream.status === 401) {
    const refreshed = await forceRefreshAccessToken(request);
    if (refreshed instanceof NextResponse) return refreshed;
    try {
      upstream = await callUpstream(to, method, refreshed, body, query);
    } catch {
      return NextResponse.json(
        { message: 'Upstream api unreachable', statusCode: 502 },
        { status: 502 },
      );
    }
  }

  if (upstream.status === 204) {
    return new NextResponse(null, { status: 204 });
  }

  const text = await upstream.text();
  const data = text ? JSON.parse(text) : null;
  return NextResponse.json(data, { status: upstream.status });
}

/** Forward an authenticated request to the upstream api. */
export function proxyAuthed(opts: Omit<ProxyOptions, 'authed'>, request: NextRequest) {
  return forward({ ...opts, authed: true }, request);
}

/** Forward a public (unauthenticated) request to the upstream api. */
export function proxyPublic(opts: Omit<ProxyOptions, 'authed'>, request: NextRequest) {
  return forward({ ...opts, authed: false }, request);
}
