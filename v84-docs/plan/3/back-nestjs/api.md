[v84-3-1-1]#1 Public registration API endpoint and DTOs
  task: define RegisterDto (email-only for step 1) with class-validator fields, add POST /auth/register route to AuthController, attach Swagger decorators, enforce strict rate limiting on the route, and return identical status, body, and latency regardless of whether the email already exists to prevent bot spam and enumeration. The registration is split into two steps: (1) email submission mints a verification token and sends the verification email; (2) user clicks the link, views `/auth/register/[token]`, and POSTs to `/auth/register/complete` with their chosen password — that's where `SetPasswordDto` (see `#3` below) enters.
  files: apps/api/src/modules/auth/dto/register.dto.ts, apps/api/src/modules/auth/dto/index.ts, apps/api/src/modules/auth/auth.controller.ts
[v84-3-1-1]#3 Set-password DTO for registration completion
  task: define `SetPasswordDto` (token + password + confirmPassword with class-validator complexity rules) used by `POST /auth/register/complete` — the second step of the registration flow where the user sets their password after clicking the verification link. Exported from the auth/dto barrel.
  files: apps/api/src/modules/auth/dto/set-password.dto.ts, apps/api/src/modules/auth/dto/index.ts
[v84-3-1-2]#1 Email verification API endpoint
  task: add GET /auth/verify/:token route to AuthController, extract token from route params, attach Swagger decorators, enforce short token expiry and single-use invalidation, and constrain post-verification redirects to allowed origins
  files: apps/api/src/modules/auth/auth.controller.ts
[v84-3-2-1]#1 Password reset request API endpoint and DTO
  task: define ForgotPasswordDto with class-validator (email), add POST /auth/forgot-password route to AuthController, attach Swagger decorators, enforce strict per-IP/email rate limiting, and return identical status, body, and latency for existing vs. missing emails to prevent account enumeration
  files: apps/api/src/modules/auth/dto/forgot-password.dto.ts, apps/api/src/modules/auth/dto/index.ts, apps/api/src/modules/auth/auth.controller.ts
[v84-3-2-2]#1 Password reset action API endpoint and DTO
  task: define ResetPasswordDto with class-validator (token, password, confirmPassword), add POST /auth/reset-password route to AuthController, attach Swagger decorators, enforce single-use and expiry checks on the reset token in the route layer before allowing the password update to proceed, and return HTTP 200 with a success message
  files: apps/api/src/modules/auth/dto/reset-password.dto.ts, apps/api/src/modules/auth/dto/index.ts, apps/api/src/modules/auth/auth.controller.ts
