[v84-4-1-1]#1 Define Zod schema for TOTP verification code
  task: create `totpCodeSchema` in apps/web/src/modules/account/schemas.ts to validate 6-digit numeric codes for 2FA setup and disable steps.
  files: apps/web/src/modules/account/schemas.ts
[v84-4-1-1]#2 Implement TwoFactorSetup component with QR rendering and submission flow
  task: build `TwoFactorSetup` component in apps/web/src/modules/account/components/TwoFactorSetup.tsx — single component that handles both enable (secret → QR → verify) and disable (password + code) flows. Wire `totpCodeSchema` to `.safeParse()` for field-level errors, render the QR from the raw TOTP secret client-side with `qrcode.react` (building the `otpauth://` URI locally), submit to `modules/account/api.ts` enable/verify/disable, and re-export from apps/web/src/modules/account/components/index.ts.
  files: apps/web/src/modules/account/components/TwoFactorSetup.tsx, apps/web/src/modules/account/components/index.ts
  depends: [v84-4-1-1]#1
[v84-4-2-1]#1 Define Zod schema for password change
  task: create `changePasswordSchema` in apps/web/src/modules/account/schemas.ts with `currentPassword`, `password`, and `confirmPassword` fields and a cross-field check on password match.
  files: apps/web/src/modules/account/schemas.ts
[v84-4-2-1]#2 Implement PasswordChangeForm with validation & submission flow
  task: build `PasswordChangeForm` component in apps/web/src/modules/account/components/PasswordChangeForm.tsx — wire `changePasswordSchema` to `.safeParse()` for field errors, externalize labels to `brand/copy`, submit to `modules/account/api.ts changePassword`, and re-export from apps/web/src/modules/account/components/index.ts.
  files: apps/web/src/modules/account/components/PasswordChangeForm.tsx, apps/web/src/modules/account/components/index.ts
  depends: [v84-4-2-1]#1
[v84-4-2-2]#1 Define Zod schema for email change request
  task: create `changeEmailSchema` in apps/web/src/modules/account/schemas.ts with strict email validation for the new address plus a `currentPassword` field for re-authentication.
  files: apps/web/src/modules/account/schemas.ts
[v84-4-2-2]#2 Implement EmailChangeForm with validation & submission flow
  task: build `EmailChangeForm` component in apps/web/src/modules/account/components/EmailChangeForm.tsx — wire `changeEmailSchema` to `.safeParse()` for field errors, show a success state prompting the user to check the new email for the confirmation link, submit to `modules/account/api.ts requestEmailChange`, and re-export from apps/web/src/modules/account/components/index.ts.
  files: apps/web/src/modules/account/components/EmailChangeForm.tsx, apps/web/src/modules/account/components/index.ts
  depends: [v84-4-2-2]#1
[v84-4-3-1]#1 Sessions list component
  task: build `SessionsList` component in apps/web/src/modules/account/components/SessionsList.tsx — calls `modules/sessions/api.ts listSessions`, renders device/OS/IP/last-seen for each session, marks the current session, and wires per-row revoke buttons to `revokeSession` (and an optional "revoke all other" action to `revokeAllSessions`). Re-export from apps/web/src/modules/account/components/index.ts.
  files: apps/web/src/modules/account/components/SessionsList.tsx, apps/web/src/modules/account/components/index.ts
