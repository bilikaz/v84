
# --- iteration 2 ---
[v84-2-4-2]#1 Define Zod schemas for user creation and update in the users feature module
  task: Create `createUserSchema` and `updateUserSchema` with strict validation rules for email, username, role, and password
  files: apps/web/src/modules/users/schemas.ts
[v84-2-4-2]#2 Implement form submission flow with field-level error mapping and safe retry
  task: Wire Zod `.safeParse` to form handlers, map validation issues to `Record<string, string>`, and catch `ApiError` to show inline feedback without clearing user input
  files: apps/web/src/modules/users/components/UserForm.tsx
  depends: [v84-2-4-2]#1

# --- iteration 3 ---
[v84-3-1-1]#1 Define Zod schema for user registration
  task: Create `registerSchema` with email, password, and confirm password validation in the auth feature module
  files: apps/web/src/modules/auth/schemas.ts
[v84-3-1-1]#2 Implement Registration Form with validation & submission flow
  task: Build `RegistrationForm` component wired to `registerSchema`, handling field-level errors via `.safeParse`, externalizing form labels and messages to `brand/copy`, and submitting to the auth module API wrapper (`apps/web/src/modules/auth/api.ts`). Export RegistrationForm, ForgotPasswordForm, and ResetPasswordForm from a single modules/auth/components/index.ts sub-barrel so pages import the full auth-forms surface via one path.
  files: apps/web/src/modules/auth/components/RegistrationForm.tsx, apps/web/src/modules/auth/components/index.ts
  depends: [v84-3-1-1]#1
[v84-3-2-1]#1 Define Zod schema for forgot password request
  task: Create `forgotPasswordSchema` with email validation in the auth feature module
  files: apps/web/src/modules/auth/schemas.ts
[v84-3-2-1]#2 Implement Forgot Password Form with validation & submission flow
  task: Build `ForgotPasswordForm` component wired to `forgotPasswordSchema`, handling field-level errors via `.safeParse`, externalizing form labels and messages to `brand/copy`, and submitting to the auth module API wrapper
  files: apps/web/src/modules/auth/components/ForgotPasswordForm.tsx
  depends: [v84-3-2-1]#1
[v84-3-2-2]#1 Define Zod schema for password reset action
  task: Create `resetPasswordSchema` with password and confirm password validation in the auth feature module
  files: apps/web/src/modules/auth/schemas.ts
[v84-3-2-2]#2 Implement Reset Password Form with validation & submission flow
  task: Build `ResetPasswordForm` component wired to `resetPasswordSchema`, handling field-level errors via `.safeParse`, externalizing form labels and messages to `brand/copy`, and submitting to the auth module API wrapper
  files: apps/web/src/modules/auth/components/ResetPasswordForm.tsx
  depends: [v84-3-2-2]#1

# --- iteration 4 ---
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
