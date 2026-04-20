// [v84-2-3-1][front-nextjs:api]
// Client-side fetch wrapper.
//
// All calls go to the same-origin BFF (Next.js route handlers under /api/*),
// which proxies to the upstream NestJS api server-side. Auth tokens never
// touch the browser — they live in the BFF's session storage and are
// attached to the upstream call by `lib/server-auth.ts`. The browser only
// holds an opaque session cookie (httpOnly + sameSite=lax + secure in prod).
//
// Therefore: no token logic here, no Authorization header, no NEXT_PUBLIC_API_URL.

import { ApiError } from './types';

const BFF_BASE = '/api';

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  const res = await fetch(`${BFF_BASE}${path}`, {
    ...options,
    headers,
    credentials: 'same-origin', // explicit: send the session cookie
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ message: res.statusText }));
    throw new ApiError(res.status, body.message ?? res.statusText);
  }

  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}
