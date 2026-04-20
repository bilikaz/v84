// [v84-1-4][front-nextjs:pages]
export { routes, landingPathForUser } from './routes';
export { publicEnv, isGoogleEnabled } from './public-env';
export { copy } from './brand';
// `serverEnv` is intentionally NOT re-exported from this barrel — it's gated by
// `server-only` and must be imported from `@/config/server-env` so accidental
// client imports fail loudly at build time, not silently at runtime.
