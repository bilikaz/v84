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
