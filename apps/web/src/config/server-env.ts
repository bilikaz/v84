// [v84-1-4][front-nextjs:pages]
// Server-only environment variables.
//
// This file is the single place that reads `process.env` for variables that
// the BFF + server code need. Importing it from a client component is a build
// error by design — it's marked `server-only` to make accidental leaks loud.
//
// Mirror of apps/api/src/config/* — every consumer reads from here, never
// from `process.env` directly.

import 'server-only';

function required(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(
      `Missing required env var ${name}. Set it in docker/dev/.env (or your prod secrets).`,
    );
  }
  return value;
}

function int(name: string, value: string | undefined, fallback: number): number {
  if (value === undefined || value === '') return fallback;
  const n = parseInt(value, 10);
  if (Number.isNaN(n)) {
    throw new Error(`Env var ${name} must be an integer (got "${value}")`);
  }
  return n;
}

export const serverEnv = {
  /** Upstream NestJS api base, including the /api/v1 prefix. Used by BFF route handlers. */
  apiUrl: required('API_URL', process.env.API_URL),

  /** Cookie name the BFF uses for the opaque session id. */
  sessionCookie: process.env.SESSION_COOKIE ?? 'session',

  /** Session cookie lifetime in seconds. Independent of the upstream JWT TTLs. */
  sessionCookieMaxAge: int(
    'SESSION_COOKIE_MAX_AGE',
    process.env.SESSION_COOKIE_MAX_AGE,
    60 * 60 * 24 * 30, // 30 days
  ),

  /** Refresh the upstream access token this many seconds before it expires. */
  sessionRefreshThreshold: int(
    'SESSION_REFRESH_THRESHOLD',
    process.env.SESSION_REFRESH_THRESHOLD,
    15,
  ),

  /** Whether we're running in production — drives `secure: true` on cookies. */
  isProduction: process.env.NODE_ENV === 'production',
} as const;
