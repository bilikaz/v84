
# --- iteration 1 ---
[v84-1-3]#1 NestJS app bootstrap — global prefix, ValidationPipe, Swagger docs
  task: create main.ts with NestFactory, global prefix from app.prefix, whitelist+forbidNonWhitelisted ValidationPipe, Swagger at /api/docs
  files: apps/api/src/main.ts

[v84-1-3]#2 AppModule root — ConfigModule global, all providers registered
  task: wire ConfigModule.forRoot with registerAs configs (app, database, jwt, redis, mail), import DatabaseModule, feature modules, HealthController
  files: apps/api/src/app.module.ts

[v84-1-3]#3 Config files — registerAs pattern, no fallback defaults
  task: create registerAs configs for app, database, jwt, redis, mail; barrel export from config/index.ts
  files: apps/api/src/config/app.config.ts, apps/api/src/config/database.config.ts, apps/api/src/config/jwt.config.ts, apps/api/src/config/redis.config.ts, apps/api/src/config/mail.config.ts, apps/api/src/config/index.ts

[v84-1-3]#4 Health-check endpoint at GET /api/v1/health
  task: create HealthController returning { status: 'ok' }, register in AppModule
  files: apps/api/src/health.controller.ts

[v84-1-3]#5 DatabaseModule — TypeORM connected to MariaDB
  task: create DatabaseModule with TypeOrmModule.forRootAsync using database config, entities autoloaded
  files: apps/api/src/database/database.module.ts, apps/api/src/database/index.ts
  depends: [v84-1-3]#3

[v84-1-3]#6 Redis service — cache and session store connection
  task: create RedisService wrapping ioredis client, configured from redis config, exported from DatabaseModule
  files: apps/api/src/database/redis.service.ts
  depends: [v84-1-3]#3

[v84-1-3]#7 TypeORM data-source for CLI migrations
  task: create standalone data-source.ts for TypeORM CLI (migration:generate, migration:run) reading env directly
  files: apps/api/src/database/data-source.ts

[v84-1-3]#9 Test-only reset endpoint — TestModule + TestController
  task: expose `POST /api/v1/test/reset` that calls the shared `resetDatabaseAndSeed(dataSource, redis)` helper so Playwright tests can return the DB to the seeded baseline between specs. `TestModule` imports `DatabaseModule` (for `DataSource` + `RedisService`). `AppModule` conditionally imports `TestModule` only when `NODE_ENV === 'test'`, so dev and prod never register the endpoint. `@ApiExcludeController()` keeps it out of Swagger.
  files: apps/api/src/modules/test/test.controller.ts, apps/api/src/modules/test/test.module.ts
  depends: [v84-1-3]#2, [v84-1-3]#10

[v84-1-3]#10 Shared test-reset helpers — resetDatabase + resetDatabaseAndSeed
  task: create `apps/api/src/database/test-reset.ts` exporting `resetDatabase(dataSource)` (truncates every TypeORM-managed table, discovered via `dataSource.entityMetadatas` so new `@Entity()` is wiped automatically) and `resetDatabaseAndSeed(dataSource, redis)` (wraps `resetDatabase` + FLUSHDB + `runAllSeeders(..., { force: true })`). Used by both the Jest test helper (`ctx.resetState`) and the `/test/reset` HTTP endpoint so every test path converges on one reset contract.
  files: apps/api/src/database/test-reset.ts
  depends: [v84-1-3]#5, [v84-1-3]#6

[v84-1-6]#1 Email theme re-exports from brand tokens
  task: re-export brand colors, fonts, app name from brand/tokens and brand/copy via theme.ts so api code never imports brand directly
  files: apps/api/src/templates/emails/theme.ts, apps/api/src/templates/emails/index.ts, apps/api/src/templates/render.ts

# --- iteration 2 ---
[v84-2-2-1]#1 Auth endpoints controller and DTOs
  task: create AuthController with POST /auth/login, /logout, /refresh, plus OAuth sign-in routes /auth/google and /auth/apple; define LoginDto, RefreshTokenDto, GoogleLoginDto (idToken), AppleLoginDto (identityToken + optional name/email hints) with class-validator, Swagger @ApiTags, proper HTTP status codes; apply @Exclude() to UserResponseDto to strip passwordHash, use generic brand-agnostic validation/error messages; wire @nestjs/throttler in auth.module.ts with strict rate limit (10 req/60s) — TTL and limit read from an env-configurable auth.config registerAs block; export the DTO sub-barrel (no module-level barrel)
  files: apps/api/src/modules/auth/auth.controller.ts, apps/api/src/modules/auth/dto/login.dto.ts, apps/api/src/modules/auth/dto/refresh-token.dto.ts, apps/api/src/modules/auth/dto/google-login.dto.ts, apps/api/src/modules/auth/dto/apple-login.dto.ts, apps/api/src/modules/auth/dto/index.ts, apps/api/src/modules/auth/auth.module.ts, apps/api/src/config/auth.config.ts
[v84-2-2-2]#1 Passport strategies and auth guards
  task: implement every Passport strategy the auth endpoints need — JwtStrategy (access tokens from Authorization header), LocalStrategy (email+password for /auth/login), RefreshTokenStrategy (refresh token body for /auth/refresh), GoogleStrategy + AppleStrategy (OAuth ID-token login for /auth/google and /auth/apple); plus the matching Passport-wrapper guards used by AuthController (@UseGuards(...)) — JwtAuthGuard (common/, cross-role), LocalAuthGuard + RefreshAuthGuard + GoogleAuthGuard + AppleAuthGuard (auth-scoped, live in modules/auth/guards/). All strategies live in common/strategies per convention. Export each strategy from the common/strategies sub-barrel and each auth-local guard from modules/auth/guards/index.ts.
  files: apps/api/src/common/strategies/jwt.strategy.ts, apps/api/src/common/strategies/local.strategy.ts, apps/api/src/common/strategies/refresh-token.strategy.ts, apps/api/src/common/strategies/google.strategy.ts, apps/api/src/common/strategies/apple.strategy.ts, apps/api/src/common/strategies/index.ts, apps/api/src/common/guards/jwt-auth.guard.ts, apps/api/src/common/guards/index.ts, apps/api/src/modules/auth/guards/local-auth.guard.ts, apps/api/src/modules/auth/guards/refresh-auth.guard.ts, apps/api/src/modules/auth/guards/google-auth.guard.ts, apps/api/src/modules/auth/guards/apple-auth.guard.ts, apps/api/src/modules/auth/guards/index.ts
  depends: [v84-2-1-1]#1
[v84-2-2-2]#2 Role-based access guard and decorators
  task: implement RolesGuard checking user roles against a custom @Roles() decorator; create @CurrentUser() decorator extracting validated user from JWT payload; export from common/guards and common/decorators
  files: apps/api/src/common/guards/roles.guard.ts, apps/api/src/common/decorators/roles.decorator.ts, apps/api/src/common/decorators/current-user.decorator.ts, apps/api/src/common/decorators/index.ts, apps/api/src/common/guards/index.ts
  depends: [v84-2-2-2]#1
[v84-2-4-1]#1 User management API endpoints and DTOs
  task: create UsersController with paginated GET /users, detail GET /users/:id, create POST /users, update PATCH /users/:id (self-update), admin-patch PATCH /users/:id via admin-only route, delete DELETE /users/:id; define CreateUserDto, UpdateUserDto (self-mutable fields only), AdminUpdateUserDto (admin-only fields like role changes), ListUsersQueryDto, UserResponseDto with class-validator, Swagger, pagination support, and admin-only guards on write endpoints. The separate AdminUpdateUserDto isolates admin-only mutations (role flips, force-unverify, etc.) from self-serve patches so class-validator can keep the per-field allow-list tight on each surface.
  files: apps/api/src/modules/users/users.controller.ts, apps/api/src/modules/users/dto/create-user.dto.ts, apps/api/src/modules/users/dto/update-user.dto.ts, apps/api/src/modules/users/dto/admin-update-user.dto.ts, apps/api/src/modules/users/dto/list-users-query.dto.ts, apps/api/src/modules/users/dto/user-response.dto.ts, apps/api/src/modules/users/dto/index.ts, apps/api/src/modules/users/users.module.ts
  depends: [v84-2-2-2]#2
[v84-2-4-1]#2 Generic paginated response DTO
  task: create generic PaginatedResponseDto<T> at apps/api/src/common/dto/paginated-response.dto.ts exporting { items, total, page, limit, pages }; required by shared conventions for all list endpoints and needed for the paginated user list in v84-2-4-1
  files: apps/api/src/common/dto/paginated-response.dto.ts, apps/api/src/common/dto/index.ts

# --- iteration 3 ---
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

# --- iteration 4 ---
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
