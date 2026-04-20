
# --- iteration 1 ---
[v84-1-3]#1 API test harness — Jest configs, env, and base TestContext factory
  task: wire the API workspace's Jest setup — `jest.config.ts` for unit tests under `apps/api/src/**/*.spec.ts` and `jest-e2e.config.ts` for integration tests under `apps/api/test/**/*.e2e.spec.ts`. Both read `apps/api/test/env.ts` to load a deterministic test env (disabled throttler, in-process mail transport, isolated database/Redis URLs). Expose `createTestApp()` in `apps/api/test/helpers/app.ts` — the canonical `TestContext` factory that every integration spec calls: boots a full NestJS module, opens a supertest handle, provides `ctx.resetState()` between tests, and returns `ctx.close()` for teardown. Later iterations add feature-specific helpers that build on top.
  files: apps/api/jest.config.ts, apps/api/jest-e2e.config.ts, apps/api/test/env.ts, apps/api/test/helpers/app.ts
[v84-1-4]#1 Web test harness — Vitest setup and stubs
  task: set up `apps/web/src/__tests__/setup.ts` — Vitest `setupFiles` entry that populates the env vars `src/config/server-env.ts` requires at import time and registers a `beforeEach` that clears the BFF in-memory session storage so tests don't leak sessions into each other. Also `apps/web/src/__tests__/stubs/server-only.ts` — an empty module that replaces the real `server-only` package under `node` test environments (the real one throws on import, which is the wrong behavior under vitest).
  files: apps/web/src/__tests__/setup.ts, apps/web/src/__tests__/stubs/server-only.ts

# --- iteration 2 ---
[v84-2-1-1]#1 User and Session entity tests
  task: Integration coverage for User and Session entities — schema, UUID v7 generation, relations, MariaDB constraints — exercised through the real auth flows in auth.e2e.spec.ts and users-admin.e2e.spec.ts.
  files: apps/api/test/auth.e2e.spec.ts, apps/api/test/users-admin.e2e.spec.ts
[v84-2-1-2]#1 Token lifecycle tests
  task: Integration coverage for JWT/refresh token mechanics — TTL expiry, single-use refresh rotation, logout invalidation — no mocking of crypto or time.
  files: apps/api/test/refresh.e2e.spec.ts
[v84-2-1-3]#1 Seed data verification tests
  task: Integration tests for the seed-runner confirming default admin and user accounts are created with correct roles, bcrypt-hashed passwords, and uuid v7 IDs.
  files: apps/api/test/seed-data.e2e.spec.ts
[v84-2-2-1]#1 Auth endpoint tests
  task: Supertest integration tests for login/logout/refresh — exact JSON shapes, httpOnly cookie flags, JWT claims (iat, exp), rate limiting behaviour.
  files: apps/api/test/auth.e2e.spec.ts
[v84-2-2-1]#3 Auth test-flow helpers
  task: start `apps/api/test/helpers/auth-flows.ts` — the shared toolkit every integration spec uses to arrange authenticated state: `loginHappyPath(ctx, email, password)` wraps the full login round-trip and returns `{ accessToken, refreshToken }` so specs don't re-implement the dance. Iteration 3 appends `registerAndComplete` (register → verify → set-password) and iteration 4 appends `generateTotp` / `decodeJwtPayload` as their features come online — same file, grown over time.
  files: apps/api/test/helpers/auth-flows.ts
[v84-2-2-2]#1 Auth guard presence tests
  task: One-line 401/403 assertions for every protected endpoint, verifying NestJS guards are wired and reject missing/malformed tokens.
  files: apps/api/test/auth-guards.e2e.spec.ts
[v84-2-3-2]#1 Frontend auth state tests
  task: Vitest tests for the BFF session layer (storage TTL refresh threshold, cookie security attributes, session cleanup on failure). AuthProvider/useAuth are exercised indirectly through the server-auth helpers they call.
  files: apps/web/src/__tests__/lib/storage.test.ts, apps/web/src/__tests__/lib/server-auth.test.ts
[v84-2-4-1]#1 Admin user management tests
  task: Integration tests for admin CRUD — role-based access control, duplicate email rejection, exact positive response shapes, cross-user isolation, no passwordHash leaks.
  files: apps/api/test/users-admin.e2e.spec.ts
[v84-2-4-1]#2 Self-serve /users/me integration tests
  task: Integration coverage for the self-service surface (`GET /users/me`, `PATCH /users/me`) — identity returned matches session, partial updates respect the self-mutable allow-list (username, password, etc.), forbidden fields (role) are rejected, no passwordHash leaks. Lives in its own spec file to keep the admin flow and the self-serve flow independent.
  files: apps/api/test/users-me.e2e.spec.ts
[v84-2-2-1]#2 DTO validation integration tests
  task: Generic coverage of the class-validator pipeline — malformed payloads return 400 with the expected error-array shape, unknown fields stripped (or rejected per `whitelist: true`), shared tests across auth/users DTOs so regression in the global `ValidationPipe` is caught once.
  files: apps/api/test/validation.e2e.spec.ts
[v84-2-4-2]#1 User management UI e2e tests
  task: Playwright e2e tests for the admin dashboard — user table rendering, create form submission, edit form submission, delete modal confirmation, UI state updates after API mutations.
  files: e2e/user-management.spec.ts
[v84-2-4-3]#1 Admin access guard e2e tests
  task: Playwright e2e tests verifying non-admin users receive 403/redirect when accessing /admin/* routes, while admin users maintain full access.
  files: e2e/admin-guards.spec.ts

# --- iteration 3 ---
[v84-3-1-1]#1 Registration API integration test
  task: Integration coverage for `POST /auth/register` — validates input schema, rejects duplicates, creates unverified user with uuid v7, pins exact JSON response shape, and captures email trigger.
  files: apps/api/test/auth.e2e.spec.ts
[v84-3-1-1]#2 Registration Form Playwright e2e
  task: Playwright e2e for Registration form — UI validation feedback, form submission, backend unverified user creation, and redirect to `/dashboard`.
  files: e2e/auth.spec.ts
[v84-3-1-1]#3 Playwright API/Mailpit helper
  task: add `e2e/helpers/api.ts` — direct API + Mailpit helpers Playwright tests use for setup/teardown without driving the UI: `deleteAllEmails`, `waitForEmail`, `extractVerifyLink`, `registerViaApi` (full register → verify → set-password round-trip via the API), and `loginViaApi`. Keeps specs tight by arranging state over HTTP and only using the browser for the flow actually under test.
  files: e2e/helpers/api.ts
[v84-3-1-2]#1 Verification API integration test
  task: Integration test for `GET /auth/verify/:token` — processes valid/expired/invalid tokens, activates account, sets `isVerified`, invalidates token, and verifies welcome email dispatch.
  files: apps/api/test/auth.e2e.spec.ts
[v84-3-1-2]#2 Verification & Welcome E2E
  task: Playwright e2e for Verification link processing — simulates clicking verification URL, verifies dashboard access, and confirms WelcomeEmail content arrives in Mailpit.
  files: e2e/auth.spec.ts
[v84-3-1-2]#3 Mail-capture test helper
  task: add `apps/api/test/helpers/mail-capture.ts` — an in-process email capture helper that intercepts `NotificationsService` sends during integration tests, exposes `waitForEmail(to)` / `extractVerifyLink(body)` utilities, and clears between tests. Arrives with the notifications module so iter-3 verification + welcome email tests can assert dispatch shape and content; later iterations reuse the same helper for password-reset and email-change flows.
  files: apps/api/test/helpers/mail-capture.ts
[v84-3-2-1]#1 Forgot Password API integration test
  task: Integration test for `POST /auth/forgot-password` — generates reset token, persists it, dispatches PasswordResetEmail via in-process `mail-capture.ts`, enforces rate limits, and prevents user enumeration. Lives in the dedicated `password-reset.e2e.spec.ts` alongside the reset action test.
  files: apps/api/test/password-reset.e2e.spec.ts
[v84-3-2-1]#2 Forgot Password Playwright e2e
  task: Playwright e2e for Forgot Password flow — email entry, success state UI, and Mailpit verification that the reset email with correct token arrives.
  files: e2e/auth.spec.ts
[v84-3-2-2]#1 Reset Password API integration test
  task: Integration test for `POST /auth/reset-password` — validates token existence and non-reuse, enforces password complexity, updates password hash, and verifies token invalidation. Colocated with the forgot-password test in `password-reset.e2e.spec.ts`.
  files: apps/api/test/password-reset.e2e.spec.ts
[v84-3-2-2]#2 Reset Password Playwright e2e
  task: Playwright e2e for Reset Password flow — form submission, validation errors, success redirect, and verification that the reset token is revoked post-use.
  files: e2e/auth.spec.ts

# --- iteration 4 ---
[v84-4-1-1]#1 2FA enable/disable integration tests
  task: Test 2FA lifecycle — verify generate-secret returns valid secret + otpauth URI, verifyTotp validates correct/incorrect codes, enable sets totpSecret/is2faEnabled on entity, disable clears secret and flag, pin exact JSON shapes.
  files: apps/api/test/2fa.e2e.spec.ts
[v84-4-1-1]#2 E2E 2FA setup flow
  task: Execute Playwright e2e for 2FA settings page — navigate to settings, trigger QR generation, simulate authenticator app by reading OTP, enter verification code, confirm enable state, and toggle disable flow.
  files: e2e/settings.spec.ts
[v84-4-1-1]#3 Playwright TOTP helper
  task: add `e2e/helpers/totp.ts` — a standalone TOTP code generator (inline HMAC-SHA1 + base32 decode) that Playwright specs use to mint valid codes from a stored secret without spawning a real authenticator app. Same algorithm as the API's `otpauth` library but reimplemented locally because the monorepo's node_modules aren't accessible from the Playwright workspace.
  files: e2e/helpers/totp.ts
[v84-4-1-2]#1 API 2FA login challenge integration test
  task: Test `POST /auth/login` — verify account with 2FA enabled rejects missing/wrong `totpCode` with `{ requires2fa: true }` shape, then accepts correct `totpCode` and returns JWT/session cookie.
  files: apps/api/test/auth.e2e.spec.ts
[v84-4-1-2]#2 E2E 2FA login challenge
  task: Execute Playwright e2e for login flow — normal login triggers 2FA prompt UI, enter valid OTP via authenticator integration, verify successful redirect to dashboard and cookie issuance.
  files: e2e/auth.spec.ts
[v84-4-2-1]#1 API password change integration test
  task: Test `POST /auth/change-password` — validate current password match, reject wrong current password, update bcrypt hash on success, reject same/new/weak passwords per schema, pin response shape.
  files: apps/api/test/auth.e2e.spec.ts
[v84-4-2-1]#2 E2E password change flow
  task: Execute Playwright e2e for password change settings — submit form with valid current/new passwords, verify success toast/redirect, confirm login with new password works, test error states for mismatch/weak password.
  files: e2e/settings.spec.ts
[v84-4-2-2]#1 API email change integration test
  task: Test `POST /users/me/email` and `POST /users/me/email/confirm` — generate unique verification token, capture `ConfirmEmailChange` email via in-process `mail-capture.ts`, validate token expiration/reuse, update `user.email` upon valid token. Lives in a dedicated spec file rather than `auth.e2e.spec.ts` to keep the email-change flow isolated.
  files: apps/api/test/email-change.e2e.spec.ts
[v84-4-2-2]#2 E2E email change flow
  task: Execute Playwright e2e for email change settings — enter new email, verify pending state UI, click verification link from Mailpit, confirm email updated in profile, verify old email can no longer login.
  files: e2e/settings.spec.ts
[v84-4-3-1]#1 API session listing integration test
  task: Test `GET /sessions` — fetch active sessions with device metadata, IP, `lastSeenAt`, filter to current user only, pin exact `SessionResponseDto` shape including `id`, `deviceName`, `deviceOs`, `ipAddress`, `current` flag. Lives in a dedicated `sessions.e2e.spec.ts` alongside the revocation test.
  files: apps/api/test/sessions.e2e.spec.ts
[v84-4-3-1]#2 E2E session listing UI
  task: Execute Playwright e2e for sessions settings page — load active sessions table, verify rendering of device type, IP, last active time, confirm current session is marked/visible.
  files: e2e/settings.spec.ts
[v84-4-3-2]#1 API session revocation integration test
  task: Test `DELETE /sessions/:sessionId` and `DELETE /sessions/all` — revoke specific session (and all-except-current), verify the corresponding refresh token is invalidated in Redis, assert the revoked session cannot make further authenticated requests. Colocated with listing in `sessions.e2e.spec.ts`.
  files: apps/api/test/sessions.e2e.spec.ts
[v84-4-3-2]#2 E2E session revocation UI
  task: Execute Playwright e2e for session revocation — click revoke on a specific session row, verify immediate UI removal from table, confirm revoked session cannot access protected routes on separate tab/context.
  files: e2e/settings.spec.ts
