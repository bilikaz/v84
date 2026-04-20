// [v84-1-4][front-nextjs:pages]
// Public environment variables — safe to bundle into the browser.
//
// Only `NEXT_PUBLIC_*` env vars belong here. Next.js statically replaces these
// at build time so they're inlined into both the server bundle and the client
// bundle.
//
// This file is the single place that reads `process.env.NEXT_PUBLIC_*`.
// Components and providers should import from `@/config`, never from
// `process.env` directly.

export const publicEnv = {
  /** Google OAuth client id. Empty/undefined means Google login is disabled. */
  googleClientId: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? '',
} as const;

export const isGoogleEnabled = (): boolean => Boolean(publicEnv.googleClientId);
