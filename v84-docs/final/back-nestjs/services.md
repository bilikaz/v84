
# --- iteration 2 ---
[v84-2-1-2]#1 Auth service orchestration — login, logout, and refresh token flows
  task: implement AuthService methods for login (validate credentials, create session, issue tokens), logout (revoke session), and refresh (implement single-use refresh token rotation: immediately invalidate the old refresh token upon successful refresh and issue a new pair). Implement UsersService as the User repository boundary — findByEmail / findById / create / save — used by AuthService for login lookup and by iter-2-4-1's admin UsersController for CRUD. Alongside the services, wire the Sessions feature module: SessionsModule registers TypeOrmModule.forFeature([Session]) and exposes SessionsService for repository lookups that AuthService uses to create/revoke session rows.
  files: apps/api/src/modules/auth/auth.service.ts, apps/api/src/modules/users/users.service.ts, apps/api/src/modules/sessions/sessions.module.ts, apps/api/src/modules/sessions/sessions.service.ts
  depends: [v84-2-1-1]#1, [v84-2-1-1]#2
[v84-2-1-2]#2 Database infrastructure wiring — register TypeORM and data source
  task: configure TypeOrmModule.forRootAsync in DatabaseModule and setup DataSource for migrations, wiring up database.config.ts
  files: apps/api/src/database/database.module.ts, apps/api/src/database/data-source.ts, apps/api/src/config/database.config.ts

# --- iteration 3 ---
[v84-3-1-1]#1 AuthService.register — validate input, generate verification token, hash password, save unverified user
  task: implement the register method in AuthService to validate input, generate a verification token, hash the password, and save the new user record with isVerified=false in a single query, explicitly avoiding access or eager joins of lazy-loaded relations
  files: apps/api/src/modules/auth/auth.service.ts
[v84-3-1-2]#1 AuthService.verifyEmail — validate verification token, activate account, clear token
  task: implement the verifyEmail method in AuthService to locate the user by the verification token, set isVerified to true, clear the token field, and persist the user
  files: apps/api/src/modules/auth/auth.service.ts
[v84-3-2-1]#1 AuthService.requestReset — constant-time check, generate reset token, persist to user
  task: implement the requestReset method in AuthService to perform a constant-time lookup strictly on the indexed email column (avoiding joins/relations), wrap email dispatch in try/catch (log failures internally, return standard success response), generate a password reset token, and persist it to the user record
  files: apps/api/src/modules/auth/auth.service.ts
[v84-3-2-1]#2 AuthService token expiry enforcement
  task: implement token expiry enforcement and checking logic in AuthService.requestReset and AuthService.resetPassword, enforcing time-bound validity to prevent long-term account compromise
  files: apps/api/src/modules/auth/auth.service.ts
[v84-3-2-2]#1 AuthService.resetPassword — validate reset token, hash new password, clear token
  task: implement the resetPassword method in AuthService to validate the reset token, hash the new password, clear the token field, invalidate all active sessions and refresh tokens for the user immediately upon successful password hash update, and persist the updated user record
  files: apps/api/src/modules/auth/auth.service.ts

# --- iteration 4 ---
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
