// [v84-1-4][ops:testing]
// Vitest config for the web workspace.
//
// Two test categories live in this package:
//
//   1. **lib / route-handler tests** under `src/__tests__/lib/` and
//      `src/__tests__/routes/`. These exercise BFF code (server-only) and
//      need a `node` environment so `next/server`, `next/headers`, and the
//      `server-only` shim resolve correctly.
//   2. **component tests** (none yet) — they will live next to components
//      and opt into jsdom via `// @vitest-environment jsdom` per file.
//
// The setupFile injects the env vars `server-env.ts` requires *before* any
// import chain reaches it. Otherwise the module would throw during evaluation.

import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'node',
    globals: true,
    setupFiles: ['./src/__tests__/setup.ts'],
    include: ['src/__tests__/**/*.test.ts', 'src/**/*.test.{ts,tsx}'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      // `server-only` ships an empty server entry; in tests we make it explicit
      // so an accidental wrong-environment import doesn't throw.
      'server-only': path.resolve(__dirname, './src/__tests__/stubs/server-only.ts'),
    },
  },
});
