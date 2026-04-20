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
