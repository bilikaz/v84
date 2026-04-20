# Conventions — Frontend (Next.js), {role_tag}: front-nextjs

> Toon tables use `~` as separator.

## Folder Structure

Every path is from repo root. Every `files:` entry MUST use these exact paths — no shortcuts, no abbreviations, no relative paths.

Convention ~ Rule
feature modules ~ live at `apps/web/src/modules/{feature}` (plural naming, `auth` exception defined in shared conventions)
shared infrastructure ~ `app/`, `common/`, `lib/`, `config/`, `ui/` live directly under `apps/web/src/` and are NOT feature modules (they contain subfolders)
barrel exports ~ live ONLY at the lowest level | each sub-folder (`modules/{feature}/pages`, `modules/{feature}/components`, `common/hooks`, `common/guards`, `common/providers`, `ui/primitives`, `ui/layout`, `ui/feedback`, `ui/forms`, `ui/data`, `lib/`, `config/`) has its own `index.ts` re-exporting public symbols | NO top-level barrels at `apps/web/src/modules/{feature}/index.ts`, `apps/web/src/common/index.ts`, or `apps/web/src/ui/index.ts` | import from sub-barrels (`@/common/hooks`, `@/ui/primitives`) or directly from the file to prevent circular imports
route files ~ `apps/web/src/app/{route}/page.tsx` and `apps/web/src/app/{route}/layout.tsx` are thin 2-line re-exports from modules | routes contain NO logic or UI
page components ~ named `{Name}Page` and live at `apps/web/src/modules/{feature}/pages/{Name}Page.tsx`
feature components & hooks ~ live at `apps/web/src/modules/{feature}/components/{Name}.tsx` and `apps/web/src/modules/{feature}/hooks/use{Name}.ts`
feature files ~ each feature owns `apps/web/src/modules/{feature}/api.ts` (thin `apiFetch` wrappers), `apps/web/src/modules/{feature}/schemas.ts` (zod schemas), and `apps/web/src/modules/{feature}/types.ts` (request/response TS types)
providers, hooks, guards ~ ALWAYS live in `common/` regardless of usage: `apps/web/src/common/providers/{Name}Provider.tsx`, `apps/web/src/common/hooks/use{Name}.ts`, `apps/web/src/common/guards/{Name}.tsx` | EXCEPTION: truly feature-specific hooks belong in `modules/{feature}/hooks/` (e.g. `useSessionEvents`)
lib files ~ `apiFetch()` at `apps/web/src/lib/api.ts` | shared types/classes (`Paginated<T>`, `ListQuery`, `ApiError`) at `apps/web/src/lib/types.ts` | WebSocket client at `apps/web/src/lib/ws.ts` | env config at `apps/web/src/lib/config.ts`
route map ~ central navigation and links at `apps/web/src/config/routes.ts`
ui components ~ generic and app-agnostic (never import app data/modules/hooks) | split into categories: `apps/web/src/ui/primitives/`, `ui/layout/`, `ui/data/`, `ui/feedback/`, `ui/forms/` | each category has its own sub-barrel | UI is not a separate package

**NEVER** put page components in `apps/web/src/app/`. They belong in `apps/web/src/modules/{feature}/pages/`.

## Data Contracts (DTOs)

Convention ~ Rule
response types ~ plain TS interfaces in `apps/web/src/modules/{feature}/types.ts` — mirror API DTO shapes exactly
paginated lists ~ API returns `{ items: T[], total, page, limit, pages }` | mirror as `Paginated<T>` in `apps/web/src/lib/types.ts` | list wrappers accept `{ page?, limit? }` params
form validation ~ zod schemas in `apps/web/src/modules/{feature}/schemas.ts` | infer types with `z.infer<typeof schema>` | validate in the form handler before calling the feature `api.ts`

## API Client & Auth Flow

Convention ~ Rule
upstream url ~ `NEXT_PUBLIC_API_URL` (defaults to `http://api.localhost/api/v1`) | browser NEVER talks directly to the API — all requests go through the BFF
api fetch ~ `apiFetch<T>(path, options)` in `apps/web/src/lib/api.ts` calls BFF routes at `/api/*` with `credentials: 'same-origin'` | each feature `api.ts` exports named functions (`listUsers`, `createUser`, …)
error handling ~ `apiFetch` throws `ApiError(status, message)` on non-ok responses | form handlers catch it and show inline error WITHOUT clearing user input

The browser never sees tokens. On login, the BFF (`apps/web/src/app/api/auth/login/route.ts`) forwards credentials to the upstream API, receives access + refresh JWTs, stores them in server-side storage (`apps/web/src/lib/storage.ts` — in-memory Map, easily replaceable by Redis) keyed by a random opaque UUID, and sets a single `httpOnly`, `secure`, `sameSite=lax` cookie via `apps/web/src/lib/server-auth.ts`. The browser only receives `{ ok: true }` and the cookie.

On subsequent requests the BFF looks up tokens via the session cookie, attaches `Authorization: Bearer {accessToken}`, and proxies the response. When the access token expires within 15 seconds (`sessionRefreshThreshold`), the BFF transparently refreshes it using the stored refresh token. On logout the BFF clears the cookie (`maxAge: 0`) and deletes the session.

## WebSockets

Convention ~ Rule
transport ~ singleton client in `apps/web/src/lib/ws.ts` (framework-agnostic, handles reconnect + auth)
provider ~ `SocketProvider` at `apps/web/src/common/providers/SocketProvider.tsx` owns lifecycle and exposes via context
accessor ~ `useSocket()` in `apps/web/src/common/hooks/` (thin context reader)
subscriptions ~ per-feature hooks in `apps/web/src/modules/{feature}/hooks/` (e.g. `useSessionEvents`) own their `useEffect` + cleanup
event types ~ live with REST types in `apps/web/src/modules/{feature}/types.ts`
cache updates ~ WS handlers invalidate react-query keys — never set local state directly

## Guards & Providers

Convention ~ Rule
auth context ~ `AuthProvider` in `apps/web/src/common/providers/` is the single source of truth for `user`, `login`, `logout`
auth hook ~ `useAuth()` in `apps/web/src/common/hooks/` throws if used outside the provider
route guards ~ `<RequireAuth/>` and `<RequireRole role="admin"/>` live in `apps/web/src/common/guards/`
admin shell ~ `apps/web/src/modules/admin/components/AdminShell.tsx` composes both guards + chrome

## 2FA QR Rendering

Convention ~ Rule
otpauth URI ~ built in the frontend from the raw TOTP secret returned by the API | lives in `apps/web/src/modules/auth/lib/otpauth.ts` | lets the frontend style/label the URI (issuer, account) without changing the API contract
QR rendering ~ rendered client-side from the otpauth URI (e.g. via `qrcode.react` or equivalent) inside the settings-page 2FA component | keeps QR-library dependencies out of the backend and avoids shipping binary image payloads over the API

## Error Handling

Convention ~ Rule
fetch errors ~ catch at the fetch boundary | show inline error | NEVER clear user input on failure
validation ~ use `zod.safeParse()` → map `issues` into `Record<field, message>` for field-level errors

## Styling

Convention ~ Rule
css approach ~ Tailwind utility classes | do NOT create custom CSS files unless absolutely necessary
theme tokens ~ defined in `brand/tokens.js` at repo root | imported into `apps/web/tailwind.config.ts` under `theme.extend`
color format ~ use hex values only in `brand/tokens.js` | never hardcode colors in components
responsive ~ mobile-first design | single column default | expand on larger breakpoints
fonts ~ display fonts for headings loaded via `next/font/local` from `brand/fonts/`

## Brand Tokens

General brand rules live in shared conventions. Frontend-specific rules only:

Convention ~ Rule
tailwind import ~ `import { colors, radii, ... } from '../../brand/tokens'` in `apps/web/tailwind.config.ts`
storybook MDX import ~ `import { colors } from '../../../../brand/tokens'` in brandbook MDX files
logos ~ SVGs in `brand/logos/` served via `apps/web/public/brand` symlink (Next.js) and `staticDirs` (Storybook)
fonts ~ `brand/fonts/*.woff2` loaded by `next/font/local`
drift prevention ~ never hardcode hex or font values in components | MDX brandbook pages import from `brand/tokens` and render live values

## Storybook

Shared Storybook rules live in shared conventions. Frontend specifics only:

Convention ~ Rule
scope ~ design-system primitives from `apps/web/src/ui/` + MDX brandbook | feature components in `modules/` do NOT get stories
brandbook pages ~ MDX files in `apps/storybook/stories/brand/*.mdx` render live values from `brand/tokens` (sidebar group: `Brandbook/*`)
addons ~ `@storybook/addon-essentials` + `@storybook/blocks` for MDX support

## Naming

Convention ~ Rule
page components ~ `XxxPage` (e.g. `LoginPage`, `UsersListPage`)
route files ~ `page.tsx` / `layout.tsx` (Next.js App Router)
hooks ~ `useXxx` (e.g. `useAuth`, `useLogin`, `useSessionEvents`)
api functions ~ verb-first (e.g. `listUsers`, `createUser`, `revokeSession`)
types ~ `Xxx` for entities, `XxxInput` for form inputs, `XxxResponse` for API responses
zod schemas ~ `xxxSchema` (e.g. `loginSchema`, `createUserSchema`)