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
