[v84-3-1-2]#1 Add email verification columns to User entity
  task: Define `isVerified` (boolean, default false) and `verificationToken` (varchar, nullable) columns in User entity. Add B-tree index on `verificationToken` to support fast lookup during verification link processing.
  files: apps/api/src/modules/users/entities/user.entity.ts
  depends: [v84-2-1-1]#1
[v84-3-2-1]#1 Add password reset column to User entity
  task: Define `resetPasswordToken` (varchar, nullable) column in User entity. Add B-tree index on `resetPasswordToken` to support fast lookup during password reset flows.
  files: apps/api/src/modules/users/entities/user.entity.ts
  depends: [v84-2-1-1]#1
[v84-3-2-1]#2 Add reset token expiry column to User entity
  task: Define `resetPasswordTokenExpiry` (datetime, nullable) column in User entity. Expiry fields are evaluated at runtime via `WHERE ... > NOW()` and do not use a B-tree index.
  files: apps/api/src/modules/users/entities/user.entity.ts
  depends: [v84-2-1-1]#1
