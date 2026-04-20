[v84-4-1-1]#1 2FA Setup & Disable DTOs
  task: define `VerifyTwoFactorDto` (6-digit `code`) and `DisableTwoFactorDto` (`password` + `code`) with class-validator fields and Swagger decorators, exported from the users/dto barrel. No dedicated DTOs for enable/generate-secret — those endpoints take no body and the enable endpoint returns `{ secret }` directly.
  files: apps/api/src/modules/users/dto/verify-two-factor.dto.ts, apps/api/src/modules/users/dto/disable-two-factor.dto.ts, apps/api/src/modules/users/dto/index.ts
[v84-4-1-1]#2 2FA Routes in UsersController
  task: add `POST /users/me/2fa/enable` (returns `{ secret }`), `POST /users/me/2fa/verify` (activates 2FA), and `DELETE /users/me/2fa` (disable with password + code) to UsersController with Swagger docs and correct HTTP status codes. The disable endpoint requires strong re-authentication (password + current code) — rate limiting is handled at the edge (Traefik).
  files: apps/api/src/modules/users/users.controller.ts
[v84-4-1-2]#1 Login 2FA DTO & Response Updates
  task: `LoginDto` already declares optional `totpCode` (iteration 2). Add Swagger `@ApiResponse` decorators on `AuthController.login` documenting the 2FA challenge response shape `{ requiresTwoFactor: true }` so OpenAPI clients see both branches.
  files: apps/api/src/modules/auth/dto/login.dto.ts, apps/api/src/modules/auth/auth.controller.ts
[v84-4-2-1]#1 Password Change via Update User
  task: password change flows through the existing `PATCH /users/me` endpoint. `UpdateUserDto` already accepts `currentPassword` + `password` — no dedicated change-password route or DTO. Verify Swagger docs on `UsersController.updateMe` describe the password-change path (required `currentPassword` when `password` is supplied).
  files: apps/api/src/modules/users/dto/update-user.dto.ts, apps/api/src/modules/users/users.controller.ts
[v84-4-2-2]#1 Email Change DTOs & Routes
  task: `RequestEmailChangeDto` (`newEmail` + `currentPassword`) and `ConfirmEmailChangeDto` (`token`) live in users/dto/change-email.dto.ts. Add `POST /users/me/email` (request) and `POST /users/me/email/confirm` (confirm) on UsersController with Swagger docs.
  files: apps/api/src/modules/users/dto/change-email.dto.ts, apps/api/src/modules/users/dto/index.ts, apps/api/src/modules/users/users.controller.ts
[v84-4-3-1]#1 Session Listing Route
  task: add `GET /sessions` to SessionsController returning the current user's active sessions as a plain array (not paginated per the boilerplate). Define `SessionResponseDto` (opaque `id`, `deviceName`, `deviceOs`, `ipAddress`, `lastSeenAt`, `createdAt`, `current`) in sessions/dto/session-response.dto.ts with a `toSessionResponse()` mapper that sets `current: true` for the requester's own session.
  files: apps/api/src/modules/sessions/sessions.controller.ts, apps/api/src/modules/sessions/dto/session-response.dto.ts, apps/api/src/modules/sessions/dto/index.ts
[v84-4-3-2]#1 Session Revocation Routes
  task: add `DELETE /sessions/:sessionId` (revoke one) and `DELETE /sessions/all` (revoke all except the current one) to SessionsController with Swagger docs.
  files: apps/api/src/modules/sessions/sessions.controller.ts
