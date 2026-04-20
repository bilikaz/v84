[v84-2-1-2]#1 Auth service orchestration — login, logout, and refresh token flows
  task: implement AuthService methods for login (validate credentials, create session, issue tokens), logout (revoke session), and refresh (implement single-use refresh token rotation: immediately invalidate the old refresh token upon successful refresh and issue a new pair). Implement UsersService as the User repository boundary — findByEmail / findById / create / save — used by AuthService for login lookup and by iter-2-4-1's admin UsersController for CRUD. Alongside the services, wire the Sessions feature module: SessionsModule registers TypeOrmModule.forFeature([Session]) and exposes SessionsService for repository lookups that AuthService uses to create/revoke session rows.
  files: apps/api/src/modules/auth/auth.service.ts, apps/api/src/modules/users/users.service.ts, apps/api/src/modules/sessions/sessions.module.ts, apps/api/src/modules/sessions/sessions.service.ts
  depends: [v84-2-1-1]#1, [v84-2-1-1]#2
[v84-2-1-2]#2 Database infrastructure wiring — register TypeORM and data source
  task: configure TypeOrmModule.forRootAsync in DatabaseModule and setup DataSource for migrations, wiring up database.config.ts
  files: apps/api/src/database/database.module.ts, apps/api/src/database/data-source.ts, apps/api/src/config/database.config.ts
