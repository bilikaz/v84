[v84-2-1-1]#1 User and Session entity tests
  task: Integration coverage for User and Session entities — schema, UUID v7 generation, relations, MariaDB constraints — exercised through the real auth flows in auth.e2e.spec.ts and users-admin.e2e.spec.ts.
  files: apps/api/test/auth.e2e.spec.ts, apps/api/test/users-admin.e2e.spec.ts
[v84-2-1-2]#1 Token lifecycle tests
  task: Integration coverage for JWT/refresh token mechanics — TTL expiry, single-use refresh rotation, logout invalidation — no mocking of crypto or time.
  files: apps/api/test/refresh.e2e.spec.ts
[v84-2-1-3]#1 Seed data verification tests
  task: Integration tests for the seed-runner confirming default admin and user accounts are created with correct roles, bcrypt-hashed passwords, and uuid v7 IDs.
  files: apps/api/test/seed-data.e2e.spec.ts
[v84-2-2-1]#1 Auth endpoint tests
  task: Supertest integration tests for login/logout/refresh — exact JSON shapes, httpOnly cookie flags, JWT claims (iat, exp), rate limiting behaviour.
  files: apps/api/test/auth.e2e.spec.ts
[v84-2-2-1]#3 Auth test-flow helpers
  task: start `apps/api/test/helpers/auth-flows.ts` — the shared toolkit every integration spec uses to arrange authenticated state: `loginHappyPath(ctx, email, password)` wraps the full login round-trip and returns `{ accessToken, refreshToken }` so specs don't re-implement the dance. Iteration 3 appends `registerAndComplete` (register → verify → set-password) and iteration 4 appends `generateTotp` / `decodeJwtPayload` as their features come online — same file, grown over time.
  files: apps/api/test/helpers/auth-flows.ts
[v84-2-2-2]#1 Auth guard presence tests
  task: One-line 401/403 assertions for every protected endpoint, verifying NestJS guards are wired and reject missing/malformed tokens.
  files: apps/api/test/auth-guards.e2e.spec.ts
[v84-2-3-2]#1 Frontend auth state tests
  task: Vitest tests for the BFF session layer (storage TTL refresh threshold, cookie security attributes, session cleanup on failure). AuthProvider/useAuth are exercised indirectly through the server-auth helpers they call.
  files: apps/web/src/__tests__/lib/storage.test.ts, apps/web/src/__tests__/lib/server-auth.test.ts
[v84-2-4-1]#1 Admin user management tests
  task: Integration tests for admin CRUD — role-based access control, duplicate email rejection, exact positive response shapes, cross-user isolation, no passwordHash leaks.
  files: apps/api/test/users-admin.e2e.spec.ts
[v84-2-4-1]#2 Self-serve /users/me integration tests
  task: Integration coverage for the self-service surface (`GET /users/me`, `PATCH /users/me`) — identity returned matches session, partial updates respect the self-mutable allow-list (username, password, etc.), forbidden fields (role) are rejected, no passwordHash leaks. Lives in its own spec file to keep the admin flow and the self-serve flow independent.
  files: apps/api/test/users-me.e2e.spec.ts
[v84-2-2-1]#2 DTO validation integration tests
  task: Generic coverage of the class-validator pipeline — malformed payloads return 400 with the expected error-array shape, unknown fields stripped (or rejected per `whitelist: true`), shared tests across auth/users DTOs so regression in the global `ValidationPipe` is caught once.
  files: apps/api/test/validation.e2e.spec.ts
[v84-2-4-2]#1 User management UI e2e tests
  task: Playwright e2e tests for the admin dashboard — user table rendering, create form submission, edit form submission, delete modal confirmation, UI state updates after API mutations.
  files: e2e/user-management.spec.ts
[v84-2-4-3]#1 Admin access guard e2e tests
  task: Playwright e2e tests verifying non-admin users receive 403/redirect when accessing /admin/* routes, while admin users maintain full access.
  files: e2e/admin-guards.spec.ts
