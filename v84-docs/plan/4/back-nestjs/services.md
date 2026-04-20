[v84-4-1-1]#1 UsersService 2FA orchestration — enable/verify/disable
  task: implement `enableTwoFactor(userId)` to create a cryptographically secure TOTP secret, persist `twoFactorSecret`, and return `{ secret }`; `verifyAndActivateTwoFactor(userId, code)` validates the code against the stored secret and sets `twoFactorEnabled=true`; `disableTwoFactor(userId, password, code)` re-verifies the bcrypt password, validates the TOTP code, clears `twoFactorSecret`, sets `twoFactorEnabled=false`, and revokes the user's other active sessions.
  files: apps/api/src/modules/users/users.service.ts
[v84-4-1-2]#1 Login 2FA integration
  task: extend `AuthService.login` to check `user.twoFactorEnabled` after credential validation, call TOTP verification inline when the flag is true, return `{ requiresTwoFactor: true }` when `totpCode` is missing or wrong, otherwise proceed with session and token issuance. Keep failure response shape and latency uniform across password-vs-2FA failure paths to avoid timing/feature-leakage attacks.
  files: apps/api/src/modules/auth/auth.service.ts
  depends: [v84-4-1-1]#1
[v84-4-2-1]#1 Password change orchestration
  task: password change flows through `UsersService.update()` — when `dto.password` is supplied, verify `currentPassword` via bcrypt, hash the new password, persist. Add automatic revocation of the user's other active sessions on a successful password change so stolen sessions don't survive the fix.
  files: apps/api/src/modules/users/users.service.ts
[v84-4-2-2]#1 Email change request orchestration
  task: implement `UsersService.requestEmailChange(userId, newEmail, currentPassword)` — verify the password, return a generic success response regardless of whether `newEmail` is already registered (prevents account enumeration), mint a time-bound verification token, persist it, and dispatch `ConfirmEmailChange` email to the new address.
  files: apps/api/src/modules/users/users.service.ts
[v84-4-2-2]#2 Email change confirmation orchestration
  task: implement `UsersService.confirmEmailChange(token)` — look up the user by token, enforce strict TTL validation against an `expiresAt` timestamp, reject expired tokens immediately, update `user.email`, and clear the token.
  files: apps/api/src/modules/users/users.service.ts
[v84-4-3-1]#1 Active session listing orchestration
  task: implement `SessionsService.list(userId, currentSessionId)` — query the `Session` entity using the `user_id` index, select only display fields, skip joining the parent `User` entity, and return a plain array mapped via `toSessionResponse` with the `current` flag set on the requester's own session.
  files: apps/api/src/modules/sessions/sessions.service.ts
[v84-4-3-2]#1 Session revocation orchestration
  task: implement `SessionsService.revoke(userId, sessionId)` — verify ownership (`session.user.id === userId`), delete the session row, invalidate the associated refresh token in Redis, throw `NotFoundException`/`ForbiddenException` on mismatch. Also implement `SessionsService.revokeAllOther(userId, currentSessionId)` for the bulk-revoke endpoint.
  files: apps/api/src/modules/sessions/sessions.service.ts
