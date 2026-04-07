# NestJS Patterns

## tsconfig — use nodenext, not commonjs

NestJS 11 supports `nodenext` module resolution. Use it — native ES modules are faster (static analysis, tree-shaking, faster module loading). Do NOT use `commonjs` — it's legacy and causes `baseUrl` deprecation issues with TypeScript 6+.

```json
{
  "compilerOptions": {
    "module": "nodenext",
    "moduleResolution": "nodenext",
    "resolvePackageJsonExports": true,
    "esModuleInterop": true,
    "declaration": true,
    "removeComments": true,
    "emitDecoratorMetadata": true,
    "experimentalDecorators": true,
    "allowSyntheticDefaultImports": true,
    "target": "ES2023",
    "sourceMap": true,
    "outDir": "./dist",
    "incremental": true,
    "skipLibCheck": true,
    "strictNullChecks": true,
    "noImplicitAny": true,
    "strictBindCallApply": true,
    "forceConsistentCasingInFileNames": true,
    "noFallthroughCasesInSwitch": true
  }
}
```

Use TypeScript ~5.9 — TS 5.9 fixed ESM/CJS interop with `nodenext` (TS 5.7 fails on ESM-only packages like uuid). TS 6.0 breaks TypeORM 0.3 entirely. Do NOT use `commonjs` — it's slower. Do NOT use TS 5.7 (ESM import errors) or TS 6.0 (TypeORM incompatible).

## Dependencies — always run pnpm install after adding packages

When adding a dependency to `package.json`, ALWAYS run `pnpm install` (or `pnpm add`) from the workspace root. Writing to `package.json` without running install means the package is NOT in the lockfile and will NOT be installed in Docker containers or CI.

```bash
# CORRECT — pnpm add updates both package.json and lockfile
cd apps/api && pnpm add -D @types/passport-jwt

# WRONG — editing package.json directly, lockfile is out of sync
# manually adding "@types/passport-jwt": "^4.0.1" to devDependencies
```

This applies to ALL packages — dependencies, devDependencies, peerDependencies. If it's not in `pnpm-lock.yaml`, it doesn't exist.

## Configuration — all config lives in config files, not in code

All env parsing, defaults, fallbacks, and type conversion happen in config files inside a `config/` folder. Application code uses only typed getters — no `process.env`, no fallbacks, no `parseInt()` in services/controllers.

### Config file

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

All env values arrive as strings — convert to correct types here (parseInt, parseFloat, === 'true', etc.). All defaults/fallbacks go here, nowhere else.

### Using config in code — getter only, no fallbacks

```typescript
// CORRECT — typed getter from config service
constructor(private readonly configService: ConfigService) {}

get port(): number {
  return this.configService.get<number>('database.port');
}

// WRONG — never do this in application code
const port = parseInt(process.env.DATABASE_PORT || '3306');
```

### Config module setup

```typescript
// app.module.ts
import { ConfigModule } from '@nestjs/config';
import databaseConfig from './config/database.config';
import appConfig from './config/app.config';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      load: [databaseConfig, appConfig],
    }),
  ],
})
export class AppModule {}
```

### Config folder structure

```
src/config/
├── app.config.ts        ← API_PORT, NODE_ENV
├── database.config.ts   ← DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
├── throttle.config.ts   ← THROTTLE_TTL, THROTTLE_LIMIT
└── index.ts             ← barrel export
```

## Request DTOs — every endpoint gets one

Every controller endpoint must have a request DTO, even if the body is empty. DTOs define the API contract and enable validation via ValidationPipe. No raw `@Body()` without a DTO class.

### Request DTO with validation

```typescript
// src/spins/dto/create-spin.dto.ts
import { IsString, MaxLength } from 'class-validator';

export class CreateSpinDto {
  @IsString()
  @MaxLength(255)
  name: string;
}
```

### Empty request DTO — still required

```typescript
// If the endpoint takes no body, create an empty DTO anyway
// This documents the contract and allows future fields without refactor
export class CreateSpinDto {}
```

### Using DTOs in controllers

```typescript
// CORRECT — always type the body with a DTO
@Post()
create(@Body() dto: CreateSpinDto) {
  return this.service.create(dto);
}

// WRONG — never use raw body or inline types
@Post()
create(@Body() body: { name: string }) { ... }

@Post()
create(@Body() body: any) { ... }
```

### Query DTOs — same rules apply for @Query()

Query params arrive as strings. All parsing and defaults go in the DTO via `@Transform`, never `parseInt` in the controller.

```typescript
// src/spins/dto/get-spins-query.dto.ts
import { IsOptional, IsInt, Min } from 'class-validator';
import { Transform } from 'class-transformer';

export class GetSpinsQueryDto {
  @IsOptional()
  @Transform(({ value }) => parseInt(value, 10))
  @IsInt()
  @Min(1)
  page: number = 1;

  @IsOptional()
  @Transform(({ value }) => parseInt(value, 10))
  @IsInt()
  @Min(1)
  limit: number = 50;
}
```

```typescript
// CORRECT — query DTO handles parsing and defaults
@Get()
getAll(@Query() query: GetSpinsQueryDto) {
  return this.service.getAll(query.page, query.limit);
}

// WRONG — never parseInt in controller
@Get()
getAll(@Query('page') page?: string) {
  const p = page ? parseInt(page, 10) : 1;
}
```

### DTO folder structure

```
src/{feature}/dto/
├── create-{feature}.dto.ts    ← POST body
├── update-{feature}.dto.ts    ← PATCH/PUT body
├── get-{feature}-query.dto.ts ← GET query params
├── {feature}-response.dto.ts  ← response shape
└── index.ts                   ← barrel export
```
