
# --- iteration 2 ---
[v84-2-3-1]#1 Session storage
  task: add `import 'server-only'` at the top of the file; store accessToken and refreshToken in apps/web/src/lib/storage.ts; server-auth.ts handles only the opaque session ID cookie — tokens must never be placed directly in cookies
  files: apps/web/src/lib/storage.ts
[v84-2-3-1]#2 Server-auth cookie utilities
  task: provide helpers to read the session ID from incoming cookies, set the httpOnly/lax session cookie, conditionally set the Secure attribute to false when process.env.NODE_ENV is development, and clear it on logout
  files: apps/web/src/lib/server-auth.ts
[v84-2-3-1]#3 API fetch wrapper
  task: implement apiFetch<T>() that calls BFF routes at /api/* with credentials: same-origin, throws ApiError on non-ok responses. Re-export apiFetch + ApiError + Paginated/ListQuery types from the lib sub-barrel so consumers import via a single `@/lib` path.
  files: apps/web/src/lib/api.ts, apps/web/src/lib/index.ts
[v84-2-3-1]#4 Auth response types
  task: define TS interfaces for login response, session object, and API error shape
  files: apps/web/src/modules/auth/types.ts
[v84-2-3-1]#5 Auth module API wrappers
  task: define login, logout, and getSession API functions that delegate to apiFetch(/api/auth/*)
  files: apps/web/src/modules/auth/api.ts
  depends: [v84-2-3-1]#3, [v84-2-3-1]#4
[v84-2-3-1]#6 Shared lib types
  task: define Paginated<T> and ListQuery generic interfaces and ApiError class for cross-module type reuse
  files: apps/web/src/lib/types.ts
[v84-2-3-1]#7 Users response types
  task: define User interface, create/update input shapes, and apply Paginated<User> for list endpoints mirroring API DTOs
  files: apps/web/src/modules/users/types.ts
  depends: [v84-2-3-1]#6
[v84-2-3-1]#8 Users module API wrappers
  task: define listUsers, createUser, updateUser, and deleteUser functions that delegate to apiFetch(/api/users/*)
  files: apps/web/src/modules/users/api.ts
  depends: [v84-2-3-1]#3
[v84-2-3-1]#9 BFF login route handler
  task: forward credentials to upstream API /auth/login, store tokens server-side via storage.ts, set session cookie (containing opaque UUID) via server-auth.ts, return { ok: true }
  files: apps/web/src/app/api/auth/login/route.ts
  depends: [v84-2-3-1]#1, [v84-2-3-1]#2
[v84-2-3-1]#10 BFF logout route handler
  task: call backend /auth/logout to revoke the refresh token, clear its own session cookie with maxAge: 0, return { ok: true }
  files: apps/web/src/app/api/auth/logout/route.ts
  depends: [v84-2-3-1]#1, [v84-2-3-1]#2
[v84-2-3-1]#11 BFF proxy helpers
  task: implement shared proxyAuthed/proxyPublic helpers in lib/proxy.ts — attach stored Authorization Bearer token, enforce CSRF via same-origin Origin/Referer check on state-changing methods (POST/PATCH/DELETE), auto-refresh token and retry once on upstream 401. Every BFF route handler under app/api/*/route.ts uses these helpers.
  files: apps/web/src/lib/proxy.ts
  depends: [v84-2-3-1]#1

[v84-2-3-1]#12 BFF users CRUD route handlers
  task: proxy the admin user-management surface — GET /api/users (list, paginated) + POST /api/users (create) in the collection route, and GET/PATCH/DELETE /api/users/[id] in the item route. All handlers delegate to proxyAuthed (attach Bearer token + CSRF + refresh-on-401). No business logic in the BFF: forward body/params straight through and return the upstream response.
  files: apps/web/src/app/api/users/route.ts, apps/web/src/app/api/users/[id]/route.ts
  depends: [v84-2-3-1]#11
[v84-2-3-1]#13 BFF users/me and OAuth Google route handlers
  task: add the self-service endpoint `GET /api/users/me` (returns the current user) and the OAuth-login endpoint `POST /api/auth/google` (forwards Google ID token to upstream `/auth/google` for exchange) — both delegate to the shared proxy helpers. `/api/users/me` uses `proxyAuthed` for session-bound identity lookup; `/api/auth/google` uses `proxyPublic` because the client is not yet logged in.
  files: apps/web/src/app/api/users/me/route.ts, apps/web/src/app/api/auth/google/route.ts
  depends: [v84-2-3-1]#11

# --- iteration 3 ---
[v84-3-1-1]#1 BFF register route handler
  task: handle POST /api/auth/register, forward credential payload to upstream /auth/register via fetch(), and return response
  files: apps/web/src/app/api/auth/register/route.ts
  depends: [v84-2-3-1]#1
[v84-3-1-1]#4 BFF register-complete route handler
  task: handle POST /api/auth/register/complete — forwards `{ token, username, password }` to upstream `/auth/register/complete`, the step-2 endpoint that the user hits from the verification link's landing page to finalize their account with a chosen password.
  files: apps/web/src/app/api/auth/register/complete/route.ts
  depends: [v84-2-3-1]#1
[v84-3-1-2]#1 BFF registration-token check route handler
  task: handle GET /api/auth/register/check with token as query param, proxy token verification request to upstream /auth/register/check?token=:token via fetch(), and return the { email } payload. The verify flow is part of the registration journey — not a separate resource — so it nests under /auth/register/, not a /auth/verify/ subtree.
  files: apps/web/src/app/api/auth/register/check/route.ts
  depends: [v84-2-3-1]#1
[v84-3-2-1]#1 BFF forgot password route handler
  task: handle POST /api/auth/forgot-password, forward email payload to upstream /auth/forgot-password via fetch(), and return success response
  files: apps/web/src/app/api/auth/forgot-password/route.ts
  depends: [v84-2-3-1]#1
[v84-3-2-2]#1 BFF reset password route handler
  task: handle POST /api/auth/reset-password, forward token and new password payload to upstream /auth/reset-password via fetch(), and return success
  files: apps/web/src/app/api/auth/reset-password/route.ts
  depends: [v84-2-3-1]#1
[v84-3-1-1]#2 Auth module API wrappers
  task: define register, verifyEmail, forgotPassword, and resetPassword API functions that delegate to apiFetch(/api/auth/*)
  files: apps/web/src/modules/auth/api.ts
[v84-3-1-1]#3 Auth response types
  task: define TS interfaces for registration, verification, and password reset response shapes
  files: apps/web/src/modules/auth/types.ts

# --- iteration 4 ---
[v84-4-1-1]#1 BFF 2FA route handlers
  task: create Next.js route handlers for `POST /api/users/me/2fa/enable` (returns `{ secret }`), `POST /api/users/me/2fa/verify` (activates 2FA), and `DELETE /api/users/me/2fa` (disable) that proxy to the upstream API using `proxyAuthed`.
  files: apps/web/src/app/api/users/me/2fa/enable/route.ts, apps/web/src/app/api/users/me/2fa/verify/route.ts, apps/web/src/app/api/users/me/2fa/route.ts
  depends: [v84-2-3-1]#11
[v84-4-1-1]#2 Account module 2FA API wrappers
  task: add `enableTwoFactor`, `verifyTwoFactor`, and `disableTwoFactor` functions to apps/web/src/modules/account/api.ts that call the corresponding BFF endpoints.
  files: apps/web/src/modules/account/api.ts
  depends: [v84-4-1-1]#1
[v84-4-1-2]#1 Login 2FA response type
  task: extend the login response type in apps/web/src/modules/auth/types.ts with an optional `{ requiresTwoFactor?: true }` property so the LoginPage can branch to the TOTP prompt.
  files: apps/web/src/modules/auth/types.ts
[v84-4-2-1]#1 Account module password-change API wrapper
  task: add `changePassword(currentPassword, password)` to apps/web/src/modules/account/api.ts — hits the existing `PATCH /api/users/me` handler with `{ currentPassword, password }`. No dedicated BFF route.
  files: apps/web/src/modules/account/api.ts
[v84-4-2-2]#1 BFF email-change route handler
  task: create `POST /api/users/me/email/route.ts` that proxies the `{ newEmail, currentPassword }` body to the upstream API using `proxyAuthed`.
  files: apps/web/src/app/api/users/me/email/route.ts
  depends: [v84-2-3-1]#11
[v84-4-2-2]#2 BFF confirm-email route handler
  task: create `POST /api/users/me/email/confirm/route.ts` that proxies the token confirmation to the upstream API using `proxyAuthed`.
  files: apps/web/src/app/api/users/me/email/confirm/route.ts
[v84-4-2-2]#3 Account module email-change API wrappers
  task: add `requestEmailChange` and `confirmEmailChange` functions to apps/web/src/modules/account/api.ts.
  files: apps/web/src/modules/account/api.ts
  depends: [v84-4-2-2]#1, [v84-4-2-2]#2
[v84-4-3-1]#1 BFF active sessions route handler
  task: create `GET /api/users/me/sessions/route.ts` that proxies the session-list request to the upstream API using `proxyAuthed`; return a plain array of session objects.
  files: apps/web/src/app/api/users/me/sessions/route.ts
  depends: [v84-2-3-1]#11
[v84-4-3-1]#2 Sessions module listing API wrapper
  task: add `listSessions` function to apps/web/src/modules/sessions/api.ts that calls `GET /users/me/sessions` and returns `Session[]`. Also define the shared `Session` response type in apps/web/src/modules/sessions/types.ts so the component layer and api wrapper both consume the same shape.
  files: apps/web/src/modules/sessions/api.ts, apps/web/src/modules/sessions/types.ts
  depends: [v84-4-3-1]#1
[v84-4-3-2]#1 BFF session revocation route handlers
  task: create `DELETE /api/users/me/sessions/[id]/route.ts` (revoke one) and `DELETE /api/users/me/sessions/all/route.ts` (revoke all except current) that proxy to the upstream API using `proxyAuthed`.
  files: apps/web/src/app/api/users/me/sessions/[id]/route.ts, apps/web/src/app/api/users/me/sessions/all/route.ts
  depends: [v84-2-3-1]#11
[v84-4-3-2]#2 Sessions module revocation API wrappers
  task: add `revokeSession(id)` and `revokeAllSessions()` functions to apps/web/src/modules/sessions/api.ts.
  files: apps/web/src/modules/sessions/api.ts
  depends: [v84-4-3-2]#1
