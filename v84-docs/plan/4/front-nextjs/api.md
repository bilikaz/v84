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
