// [v84-2-3-1][ops:testing]
// Storage backs every BFF session — if it forgets a key or hands back stale
// data, the user gets silently logged out (or worse, gets someone else's
// session). The class is small but the bugs would be invisible.

import { afterEach, describe, expect, it, vi } from 'vitest';
import { storage } from '@/lib/storage';

describe('storage', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('round-trips a value by key', async () => {
    await storage.set('k', { foo: 'bar' });
    expect(await storage.get('k')).toEqual({ foo: 'bar' });
  });

  it('returns null for unknown keys', async () => {
    expect(await storage.get('missing')).toBeNull();
  });

  it('removes a key on delete', async () => {
    await storage.set('k', 'v');
    await storage.delete('k');
    expect(await storage.get('k')).toBeNull();
  });

  it('expires a key after the TTL passes', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-01-01T00:00:00Z'));

    await storage.set('temp', 'v', 60); // 60 seconds

    // Just before expiry — still there.
    vi.setSystemTime(new Date('2026-01-01T00:00:59Z'));
    expect(await storage.get('temp')).toBe('v');

    // Just after — gone.
    vi.setSystemTime(new Date('2026-01-01T00:01:01Z'));
    expect(await storage.get('temp')).toBeNull();
  });

  it('keeps non-TTL keys forever', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-01-01T00:00:00Z'));

    await storage.set('forever', 'still here');

    vi.setSystemTime(new Date('2030-01-01T00:00:00Z'));
    expect(await storage.get('forever')).toBe('still here');
  });

  it('shares state across imports via the globalThis singleton', async () => {
    await storage.set('shared', 'value');

    // Re-import without destroying globalThis — the new import picks up the
    // same singleton and sees data written by the original import.
    vi.resetModules();
    const reused = await import('@/lib/storage');
    expect(await reused.storage.get('shared')).toBe('value');
  });
});
