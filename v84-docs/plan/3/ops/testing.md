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
