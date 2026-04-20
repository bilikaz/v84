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
