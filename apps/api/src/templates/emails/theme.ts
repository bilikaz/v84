// Local re-export of brand tokens and copy for ergonomic imports inside the api.
// The actual source of truth is brand/ at the repo root. Importing via the
// package.json main+exports makes tsc treat it as a pre-built module,
// sidestepping the rootDir restriction that would otherwise reject a .ts
// source file outside apps/api/src.
// [v84-1-6][back-nestjs:api]
export { colors, radii, spacing, typography } from '../../../../../brand';
export { copy } from '../../../../../brand/copy';
