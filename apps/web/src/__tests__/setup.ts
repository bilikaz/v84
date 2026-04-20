// Vitest setup — runs once before any test module is evaluated.
// Sets the env vars that `src/config/server-env.ts` requires at import time,
// and registers a global beforeEach that clears the BFF session storage so
// tests never leak sessions into each other.

// [v84-1-4][ops:testing]
import { beforeEach } from 'vitest';

process.env.API_URL = process.env.API_URL ?? 'http://api.test/api/v1';
process.env.SESSION_COOKIE = process.env.SESSION_COOKIE ?? 'session';
process.env.SESSION_COOKIE_MAX_AGE = process.env.SESSION_COOKIE_MAX_AGE ?? '2592000';
process.env.SESSION_REFRESH_THRESHOLD = process.env.SESSION_REFRESH_THRESHOLD ?? '15';
(process.env as Record<string, string>).NODE_ENV = process.env.NODE_ENV ?? 'test';

beforeEach(async () => {
  const { storage } = await import('../lib/storage');
  await storage.clear();
});
