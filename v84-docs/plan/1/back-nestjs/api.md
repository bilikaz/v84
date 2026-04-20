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
  task: expose `POST /api/v1/test/reset` that calls the shared `resetDatabaseAndSeed(dataSource, redis)` helper so Playwright tests can return the DB to the seeded baseline between specs. `TestModule` imports `DatabaseModule` (for the global `DataSource`) and declares `RedisService` in its own `providers` list (matching the AuthModule pattern — RedisService isn't re-exported from DatabaseModule). `AppModule` conditionally imports `TestModule` only when `NODE_ENV === 'test'`, so dev and prod never register the endpoint. `@ApiExcludeController()` keeps it out of Swagger.
  files: apps/api/src/modules/test/test.controller.ts, apps/api/src/modules/test/test.module.ts
  depends: [v84-1-3]#2, [v84-1-3]#10

[v84-1-3]#10 Shared test-reset helpers — resetDatabase + resetDatabaseAndSeed
  task: create `apps/api/src/database/test-reset.ts` exporting `resetDatabase(dataSource)` (truncates every TypeORM-managed table, discovered via `dataSource.entityMetadatas` so new `@Entity()` is wiped automatically) and `resetDatabaseAndSeed(dataSource, redis)` (wraps `resetDatabase` + FLUSHDB + `runAllSeeders(..., { force: true })`). Used by both the Jest test helper (`ctx.resetState`) and the `/test/reset` HTTP endpoint so every test path converges on one reset contract.
  files: apps/api/src/database/test-reset.ts
  depends: [v84-1-3]#5, [v84-1-3]#6

[v84-1-6]#1 Email theme re-exports from brand tokens
  task: re-export brand colors, fonts, app name from brand/tokens and brand/copy via theme.ts so api code never imports brand directly
  files: apps/api/src/templates/emails/theme.ts, apps/api/src/templates/emails/index.ts, apps/api/src/templates/render.ts
