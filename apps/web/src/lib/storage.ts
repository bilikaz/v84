// [v84-2-3-1][front-nextjs:api]
// Pluggable session storage for the BFF.
//
// Dev uses an in-memory Map keyed off `globalThis` so it survives Next.js HMR
// reloads inside a single dev process. Sessions are lost when the Next process
// itself restarts — that's intentional and acceptable for dev.
//
// For prod, swap the implementation here for a Redis-backed one (the
// `StorageService` interface stays the same, so nothing else needs to change).

export interface StorageService {
  get<T>(key: string): Promise<T | null>;
  set<T>(key: string, value: T, ttlSeconds?: number): Promise<void>;
  delete(key: string): Promise<void>;
  clear(): Promise<void>;
}

interface Entry<T> {
  value: T;
  expiresAt?: number;
}

class InMemoryStorage implements StorageService {
  private store = new Map<string, Entry<unknown>>();

  async get<T>(key: string): Promise<T | null> {
    const entry = this.store.get(key) as Entry<T> | undefined;
    if (!entry) return null;
    if (entry.expiresAt && Date.now() > entry.expiresAt) {
      this.store.delete(key);
      return null;
    }
    return entry.value;
  }

  async set<T>(key: string, value: T, ttlSeconds?: number): Promise<void> {
    this.store.set(key, {
      value,
      expiresAt: ttlSeconds ? Date.now() + ttlSeconds * 1000 : undefined,
    });
  }

  async delete(key: string): Promise<void> {
    this.store.delete(key);
  }

  async clear(): Promise<void> {
    this.store.clear();
  }
}

declare global {
  // eslint-disable-next-line no-var
  var __sessionStorage: StorageService | undefined;
}

export const storage: StorageService =
  globalThis.__sessionStorage ?? (globalThis.__sessionStorage = new InMemoryStorage());
