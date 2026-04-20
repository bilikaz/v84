// Test-time stub for the `server-only` package. The real package throws when
// imported in a client bundle; in vitest's `node` environment we don't need
// any of that — an empty module is enough.
// [v84-1-4][ops:testing]
export {};
