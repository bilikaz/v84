
# --- iteration 2 ---
[v84-2-1-1]#1 Create User entity
  task: Define User entity with uuid v7 primary key (mandate constructor assignment `this.id = uuidv7()`), email, username, passwordHash, role enum, and timestamps using snake_case DB mapping. Explicitly mandate `!` type assertion for all properties (e.g., `email!: string`). Add a B-tree index on the email column to prevent full table scans during login lookups. Export from the entities sub-barrel so other modules can import User via a single path.
  files: apps/api/src/modules/users/entities/user.entity.ts, apps/api/src/modules/users/entities/index.ts
[v84-2-1-1]#2 Create Session entity
  task: Define Session entity with uuid v7 primary key (mandate constructor assignment `this.id = uuidv7()`), userId FK, refreshTokenHash, userAgent, ip, expiresAt, and timestamps, plus index on userId for active session lookup. Mandate constructor assignment for `id` and `!` type assertions for all properties. Export from the entities sub-barrel so other modules can import Session via a single path.
  files: apps/api/src/modules/sessions/entities/session.entity.ts, apps/api/src/modules/sessions/entities/index.ts
[v84-2-1-3]#1 Implement seed runner script
  task: Create seed-runner.ts that validates NODE_ENV (exits on prod), discovers *.seed.ts files, tracks execution in seed_history, and runs pending seeds.
  files: apps/api/src/database/seed-runner.ts
  depends: [v84-2-1-1]#1
[v84-2-1-3]#2 Create user factory
  task: Implement factory for generating User entities with faker, including valid email, username, and hashed password. Export the factory from the factories sub-barrel so seed files can import via a single path. `@faker-js/faker` v10 is ESM-only; Jest (CJS) cannot consume it — when seed/factory code reaches the test runner it blows up on the boundary, so ship a CJS-compatible stub at apps/api/test/helpers/faker-stub.ts exposing the faker surface the factory actually uses (internet.email, internet.userName, …), and map it via jest `moduleNameMapper` so the factory gets the stub under test and the real faker at runtime.
  files: apps/api/src/database/factories/user.factory.ts, apps/api/src/database/factories/index.ts, apps/api/test/helpers/faker-stub.ts
[v84-2-1-3]#3 Create dev users seed
  task: Write seed file that uses factory to insert default admin (admin@admin.localhost) and regular user with password 'password'.
  files: apps/api/src/database/seeds/demo.seeder.ts
  depends: [v84-2-1-3]#2

# --- iteration 3 ---
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

# --- iteration 4 ---
[v84-4-1-1]#1 Add 2FA columns to User entity
  task: add `twoFactorEnabled` (boolean, default false) and `twoFactorSecret` (nullable varchar) columns to the User entity using the project's snake_case column-naming convention: `@Column({ name: 'two_factor_enabled', default: false }) twoFactorEnabled!: boolean;` and `@Column({ name: 'two_factor_secret', nullable: true, type: 'varchar' }) twoFactorSecret!: string | null;`.
  files: apps/api/src/modules/users/entities/user.entity.ts
  depends: [v84-2-1-1]#1
