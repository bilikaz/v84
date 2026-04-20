# Conventions — Executor

Code patterns for the executor agent. When the stack or packages change, update these patterns to match.

## How To Tag Code

Every piece of code gets both a v84 plan tag AND a role-topic tag:

### Creating a whole file for one task
```typescript
// [v84-1-1-2][back-nestjs:entities]
import { Entity, Column, PrimaryGeneratedColumn } from 'typeorm';

@Entity()
export class User { ... }
```

### Creating a file that serves multiple tasks
```typescript
import { Controller, Post, Get } from '@nestjs/common';

// [v84-1-2-1][back-nestjs:api]
@Post()
async create(@Body() dto: CreateUserDto) { ... }

// [v84-1-3-1][back-nestjs:api]
@Get(':id')
async findOne(@Param('id') id: string) { ... }
```

### Adding a method to an existing file
```typescript
// [v84-2-1-1][back-nestjs:services]
async deleteUser(id: string) { ... }
```

### Config and YAML files
```yaml
# [v84-1-1-1][ops:infra]
services:
  api:
    build: ./api.Dockerfile
```

### Tagging rules
- Tag goes on the line DIRECTLY above the function/class/block
- Always include BOTH `[v84-tag]` and `[role-topic]`
- Use the v84 tag from the task — do not invent new tags
- If the whole file is for one task, tag at the top
- If the file has parts from different tasks, tag each part
- Comment syntax: `//` for TS/JS, `#` for YAML/bash, `--` for SQL, `/* */` for CSS

---

## NestJS Patterns

### tsconfig — use nodenext, not commonjs

NestJS 11 supports `nodenext` module resolution. Use it. Do NOT use `commonjs` — it's legacy. TypeScript version is pinned in `package.json` — do not change it without verifying TypeORM + ESM compatibility.

### Configuration — all config in config files

All env parsing, defaults, fallbacks, and type conversion happen in config files inside `src/config/`. Application code uses only typed getters — no `process.env`, no fallbacks, no `parseInt()` in services/controllers.

```typescript
// src/config/database.config.ts
import { registerAs } from '@nestjs/config';

export default registerAs('database', () => ({
  host: process.env.DATABASE_HOST || 'localhost',
  port: parseInt(process.env.DATABASE_PORT || '3306', 10),
  username: process.env.DATABASE_USER || 'root',
  password: process.env.DATABASE_PASSWORD || '',
  name: process.env.DATABASE_NAME || 'v84',
}));
```

Using config in code — getter only, no fallbacks:
```typescript
constructor(private readonly configService: ConfigService) {}

get port(): number {
  return this.configService.get<number>('database.port');
}
```

### Request DTOs — every endpoint gets one

Every controller endpoint must have a request DTO. DTOs define the API contract and enable validation via ValidationPipe. No raw `@Body()` without a DTO class.

### Dependencies — always use pnpm add

When adding a dependency, ALWAYS use `pnpm add` from the workspace root. Writing to `package.json` without running install means the package is NOT in the lockfile.

---

## TypeORM Patterns

### Entity — strict mode

All entity fields use `!` (definite assignment assertion) because TypeORM populates them:

```typescript
import { v7 as uuidv7 } from 'uuid';

@Entity()
export class User {
  @PrimaryColumn('uuid')
  id: string = uuidv7();

  @Column({ type: 'varchar', length: 255, unique: true })
  email!: string;

  @Column({ name: 'password_hash', type: 'varchar', length: 255 })
  passwordHash!: string;

  @CreateDateColumn({ name: 'created_at' })
  createdAt!: Date;
}
```


### Migrations — ALWAYS generated, NEVER hand-written

Entities are the source of truth. TypeORM diffs entities against the DB and generates migrations automatically. NEVER write migration SQL by hand.

Migration generation runs inside the Docker container (needs DB access). See `back-nestjs.md` Migrations table for the exact command — uses the `pnpm typeorm` script from `apps/api/package.json` (`tsx node_modules/typeorm/cli.js`).

### DatabaseModule — forRootAsync with ConfigService

```typescript
@Module({
  imports: [
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: (configService: ConfigService) => ({
        type: 'mysql',
        host: configService.get<string>('database.host'),
        port: configService.get<number>('database.port'),
        username: configService.get<string>('database.username'),
        password: configService.get<string>('database.password'),
        database: configService.get<string>('database.name'),
        entities: [__dirname + '/../**/entities/*.entity{.ts,.js}'],
        migrations: [__dirname + '/migrations/*{.ts,.js}'],
        synchronize: false,
        migrationsRun: true,
        timezone: 'Z',
      }),
    }),
  ],
})
export class DatabaseModule {}
```

Key: `synchronize: false` (use migrations), `migrationsRun: true` (auto-run on startup).

### Seed accounts — predictable dev credentials

When seeding user/account entities, create one account per role:
- Email: `{role}@{role}.localhost`
- Password: `password` (same for all seeded accounts)

Every role in the system gets a seed account — no exceptions.

---

## Docker Patterns

### Named volumes for node_modules

In dev, source is mounted from host but node_modules must stay container-only:
```yaml
volumes:
  - ../../apps/api:/app/apps/api
  - /app/apps/api/node_modules     # anonymous volume shadows host
```

### Dev Dockerfile — manifests only, source is mounted

```dockerfile
FROM node:20-slim
RUN npm install -g pnpm@9
WORKDIR /app
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/api/package.json ./apps/api/
RUN pnpm install --frozen-lockfile
CMD ["pnpm", "--filter", "@v84/api", "start:dev"]
```

### Traefik routing — .localhost domains

```yaml
labels:
  - traefik.enable=true
  - traefik.http.routers.api.rule=Host(`api.localhost`)
  - traefik.http.services.api.loadbalancer.server.port=3001
```

### Database healthcheck — always add

```yaml
depends_on:
  db:
    condition: service_healthy
```

### Every dev tool with a server gets a container

Storybook, mail catcher, queue dashboard — if it has a server, it needs a Docker service with Traefik routing.

---

## Next.js Patterns

### Config — all env parsing in config files

All `NEXT_PUBLIC_*` env values read in `src/config/` only. Components import from config, never read `process.env` directly.

### Server-only code

Use `server-only` package to prevent server code from leaking to client bundles:
```typescript
import 'server-only';
```

---

## Storybook Patterns

### NEVER run storybook init

`storybook init` is interactive and hangs agents. Always create config files manually.

### Story format
```typescript
import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';

const meta: Meta<typeof Button> = { component: Button };
export default meta;
type Story = StoryObj<typeof Button>;

export const Default: Story = { args: {} };
export const Disabled: Story = { args: { disabled: true } };
```
