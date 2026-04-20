// [v84-2-3-1][front-nextjs:api]
// Server-side auth helpers for the BFF route handlers.
//
// Browser holds only an opaque session id in an httpOnly cookie. The actual
// access + refresh tokens live in `storage` (in-memory in dev). This file is
// the single place that:
//
//   1. Creates a session from a successful login / oauth / register-complete
//      response (`createSession`)
//   2. Resolves the access token for an outgoing upstream call, refreshing it
//      transparently if it's near expiry (`getAccessToken` / `getServerAccessToken`)
//   3. Tears down the session on logout (`destroySession`)
//
// Route handlers should never reach into `storage` directly; they go through
// these helpers so token rotation, cookie hygiene, and unauthorized handling
// stay in one place.

import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { randomUUID } from 'crypto';
import { serverEnv } from '@/config/server-env';
import { storage } from './storage';

export interface UpstreamAuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  tokenType: 'Bearer';
}

interface Session {
  accessToken: string;
  refreshToken: string;
  /** Unix timestamp (ms) when the access token expires. */
  expiresAt: number;
}

export const SESSION_COOKIE = serverEnv.sessionCookie;

function apiBase(): string {
  return serverEnv.apiUrl;
}

/**
 * Persist an upstream token pair as a session and return the cookie value
 * (the opaque session id) the route handler should set on the response.
 */
export async function createSession(tokens: UpstreamAuthTokens): Promise<string> {
  const id = randomUUID();
  await storage.set<Session>(
    id,
    {
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
      expiresAt: Date.now() + tokens.expiresIn * 1000,
    },
    serverEnv.sessionCookieMaxAge,
  );
  return id;
}

/** Set the session cookie on a NextResponse. */
export function setSessionCookie(response: NextResponse, sessionId: string): NextResponse {
  response.cookies.set(SESSION_COOKIE, sessionId, {
    httpOnly: true,
    secure: serverEnv.isProduction,
    sameSite: 'lax',
    maxAge: serverEnv.sessionCookieMaxAge,
    path: '/',
  });
  return response;
}

/** Clear the session cookie + drop the session from storage. */
export async function destroySession(request: NextRequest): Promise<NextResponse> {
  const id = request.cookies.get(SESSION_COOKIE)?.value;
  if (id) await storage.delete(id);

  const response = NextResponse.json({ ok: true });
  response.cookies.set(SESSION_COOKIE, '', {
    httpOnly: true,
    secure: serverEnv.isProduction,
    sameSite: 'lax',
    maxAge: 0,
    path: '/',
  });
  return response;
}

/**
 * Resolve a usable access token for the current session, refreshing the upstream
 * token transparently if it's near expiry. Returns either the bearer string or a
 * 401 response that the caller should return as-is.
 */
export type AccessTokenResult = string | NextResponse;

async function resolveAccessToken(
  cookieGetter: { get(name: string): { value?: string } | undefined },
): Promise<AccessTokenResult> {
  const id = cookieGetter.get(SESSION_COOKIE)?.value;
  if (!id) return unauthorized();

  const session = await storage.get<Session>(id);
  if (!session) return unauthorized();

  // Token still good — use it.
  if (Date.now() <= session.expiresAt - serverEnv.sessionRefreshThreshold * 1000) {
    return session.accessToken;
  }

  // Near expiry — refresh upstream.
  let res: Response;
  try {
    res = await fetch(`${apiBase()}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refreshToken: session.refreshToken }),
    });
  } catch {
    await storage.delete(id);
    return unauthorized();
  }

  if (!res.ok) {
    await storage.delete(id);
    return unauthorized();
  }

  const tokens = (await res.json()) as UpstreamAuthTokens;
  await storage.set<Session>(
    id,
    {
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
      expiresAt: Date.now() + tokens.expiresIn * 1000,
    },
    serverEnv.sessionCookieMaxAge,
  );

  return tokens.accessToken;
}

/** Use inside route handlers (`/app/api/.../route.ts`). */
export async function getAccessToken(request: NextRequest): Promise<AccessTokenResult> {
  return resolveAccessToken(request.cookies);
}

/** Use inside React Server Components / server actions. */
export async function getServerAccessToken(): Promise<AccessTokenResult> {
  const cookieStore = await cookies();
  return resolveAccessToken(cookieStore);
}

/**
 * Force-refresh the upstream access token for the current session — used when
 * upstream rejects with 401 despite a client-side-valid token (clock skew,
 * rotated server secret, revoked session).
 */
export async function forceRefreshAccessToken(
  request: NextRequest,
): Promise<AccessTokenResult> {
  const id = request.cookies.get(SESSION_COOKIE)?.value;
  if (!id) return unauthorized();

  const session = await storage.get<Session>(id);
  if (!session) return unauthorized();

  let res: Response;
  try {
    res = await fetch(`${apiBase()}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refreshToken: session.refreshToken }),
    });
  } catch {
    await storage.delete(id);
    return unauthorized();
  }

  if (!res.ok) {
    await storage.delete(id);
    return unauthorized();
  }

  const tokens = (await res.json()) as UpstreamAuthTokens;
  await storage.set<Session>(
    id,
    {
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
      expiresAt: Date.now() + tokens.expiresIn * 1000,
    },
    serverEnv.sessionCookieMaxAge,
  );
  return tokens.accessToken;
}

export function unauthorized(): NextResponse {
  return NextResponse.json({ message: 'Unauthorized', statusCode: 401 }, { status: 401 });
}

export { apiBase };
