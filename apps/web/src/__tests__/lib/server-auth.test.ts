// [v84-2-3-2][ops:testing]
// server-auth holds every load-bearing piece of the BFF auth model:
//   - opaque session creation
//   - cookie hygiene
//   - access token resolution with transparent refresh
//   - logout teardown
//
// A bug in any of these silently breaks login or, worse, leaks one user's
// session to the next request. We test the real `storage` (in-memory) and
// mock only `fetch` for the upstream refresh call.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';


function makeRequest(cookieValue?: string): NextRequest {
  const headers = new Headers();
  if (cookieValue) headers.set('cookie', `session=${cookieValue}`);
  return new NextRequest('http://localhost/api/test', { headers });
}

const FRESH_TOKENS = {
  accessToken: 'access-1',
  refreshToken: 'refresh-1',
  expiresIn: 900, // 15 min
  tokenType: 'Bearer' as const,
};

const REFRESHED_TOKENS = {
  accessToken: 'access-2',
  refreshToken: 'refresh-2',
  expiresIn: 900,
  tokenType: 'Bearer' as const,
};

describe('server-auth', () => {
  beforeEach(() => {
    // Wipe the storage singleton between tests so sessions don't leak.
    vi.resetModules();
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T12:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe('createSession', () => {
    it('stashes the tokens and returns an opaque id', async () => {
      const { createSession } = await import('@/lib/server-auth');
      const { storage } = await import('@/lib/storage');

      const id = await createSession(FRESH_TOKENS);

      expect(id).toMatch(/^[0-9a-f-]{36}$/i); // uuid v4
      const stored = await storage.get<{
        accessToken: string;
        refreshToken: string;
        expiresAt: number;
      }>(id);
      expect(stored).toEqual({
        accessToken: 'access-1',
        refreshToken: 'refresh-1',
        expiresAt: Date.now() + 900_000,
      });
    });
  });

  describe('setSessionCookie', () => {
    it('sets an httpOnly, sameSite=lax cookie with the expected name and value', async () => {
      const { setSessionCookie } = await import('@/lib/server-auth');
      const { NextResponse } = await import('next/server');

      const res = setSessionCookie(NextResponse.json({ ok: true }), 'opaque-id');
      const cookie = res.cookies.get('session');

      expect(cookie?.value).toBe('opaque-id');
      expect(cookie?.httpOnly).toBe(true);
      expect(cookie?.sameSite).toBe('lax');
      expect(cookie?.path).toBe('/');
      // NODE_ENV=test → secure stays false
      expect(cookie?.secure).toBe(false);
    });
  });

  describe('destroySession', () => {
    it('drops the session from storage and clears the cookie', async () => {
      const { createSession, destroySession } = await import('@/lib/server-auth');
      const { storage } = await import('@/lib/storage');

      const id = await createSession(FRESH_TOKENS);
      expect(await storage.get(id)).not.toBeNull();

      const response = await destroySession(makeRequest(id));

      expect(await storage.get(id)).toBeNull();
      const cookie = response.cookies.get('session');
      expect(cookie?.value).toBe('');
      expect(cookie?.maxAge).toBe(0);
    });

    it('still clears the cookie even when there is no session id', async () => {
      const { destroySession } = await import('@/lib/server-auth');
      const response = await destroySession(makeRequest());
      const cookie = response.cookies.get('session');
      expect(cookie?.value).toBe('');
    });
  });

  describe('getAccessToken', () => {
    it('returns the cached token when it is not near expiry', async () => {
      const { createSession, getAccessToken } = await import('@/lib/server-auth');
      const id = await createSession(FRESH_TOKENS);

      const token = await getAccessToken(makeRequest(id));
      expect(token).toBe('access-1');
    });

    it('returns 401 when no cookie is present', async () => {
      const { getAccessToken } = await import('@/lib/server-auth');
      const result = await getAccessToken(makeRequest());

      expect(typeof result).not.toBe('string');
      const res = result as Response;
      expect(res.status).toBe(401);
    });

    it('returns 401 when the cookie points at an unknown session', async () => {
      const { getAccessToken } = await import('@/lib/server-auth');
      const result = await getAccessToken(makeRequest('does-not-exist'));
      expect((result as Response).status).toBe(401);
    });

    it('refreshes the upstream access token transparently when near expiry', async () => {
      const { createSession, getAccessToken } = await import('@/lib/server-auth');
      const { storage } = await import('@/lib/storage');

      const id = await createSession(FRESH_TOKENS);

      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify(REFRESHED_TOKENS), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      );

      // Jump to 1 second before expiry — well inside the 15s refresh window.
      vi.setSystemTime(new Date('2026-04-11T12:14:59Z'));

      const token = await getAccessToken(makeRequest(id));
      expect(token).toBe('access-2');

      // Storage was rotated to the new pair.
      const stored = await storage.get<{ accessToken: string; refreshToken: string }>(id);
      expect(stored?.accessToken).toBe('access-2');
      expect(stored?.refreshToken).toBe('refresh-2');
    });

    it('drops the session and returns 401 if upstream refresh fails', async () => {
      const { createSession, getAccessToken } = await import('@/lib/server-auth');
      const { storage } = await import('@/lib/storage');

      const id = await createSession(FRESH_TOKENS);

      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ message: 'Unauthorized' }), { status: 401 }),
      );

      vi.setSystemTime(new Date('2026-04-11T12:14:59Z'));

      const result = await getAccessToken(makeRequest(id));
      expect((result as Response).status).toBe(401);
      expect(await storage.get(id)).toBeNull();
    });

    it('drops the session and returns 401 if the upstream call throws', async () => {
      const { createSession, getAccessToken } = await import('@/lib/server-auth');
      const { storage } = await import('@/lib/storage');

      const id = await createSession(FRESH_TOKENS);

      vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('ECONNREFUSED'));
      vi.setSystemTime(new Date('2026-04-11T12:14:59Z'));

      const result = await getAccessToken(makeRequest(id));
      expect((result as Response).status).toBe(401);
      expect(await storage.get(id)).toBeNull();
    });
  });
});
