# Project Stack & Installed Packages

> Toon tables use ~ as separator

## Project Stack

Infrastructure, tooling, and conventions that are not npm packages.

Type ~ Choice ~ Notes
repo ~ monorepo ~ single repo for all services
database ~ MariaDB ~ relational | TypeORM for ORM | migrations via TypeORM CLI
dev-environment ~ Docker Compose ~ all services containerized for local dev
db-admin ~ Adminer ~ web UI for database access in dev environment
ci ~ GitHub Actions ~ lint → test → build → deploy pipeline
containerization ~ Docker ~ multi-stage builds | slim production images
env-management ~ dotenv ~ .env.example committed | .env in .gitignore
commit-style ~ Conventional Commits ~ feat/fix/chore prefix | enables auto-changelog

## Installed Packages

Packages listed here are the source of truth for what is available and how to use it. Agents should prefer what is already installed. If a task genuinely requires a new package, flag it explicitly — don't silently assume it exists. When a package is added or updated, this section must be updated too.

### apps/api (NestJS backend)

Package ~ Version ~ Used For ~ Key Methods/Patterns
@nestjs/core ~ * ~ framework core ~ Module() | Controller() | Injectable()
@nestjs/common ~ * ~ decorators and pipes ~ Get() | Post() | Body() | Param() | ValidationPipe
@nestjs/platform-express ~ * ~ HTTP adapter ~ NestFactory.create()
@nestjs/typeorm ~ * ~ TypeORM integration ~ TypeOrmModule.forRoot() | TypeOrmModule.forFeature()
@nestjs/swagger ~ * ~ API docs ~ ApiTags() | ApiOperation() | ApiResponse()
@nestjs/throttler ~ * ~ rate limiting ~ ThrottlerModule.forRoot() | Throttle()
typeorm ~ * ~ ORM ~ Entity() | Column() | PrimaryGeneratedColumn() | Repository.find() | Repository.save()
class-validator ~ * ~ DTO validation ~ IsString() | IsNotEmpty() | MaxLength() | MinLength()
class-transformer ~ * ~ DTO transformation ~ Transform() | plainToInstance()
uuid ~ * ~ key generation ~ v4()
pino ~ * ~ structured logging ~ pino() | logger.info() | logger.error()
mysql2 ~ * ~ database driver ~ used by TypeORM with type: 'mysql' for MariaDB/MySQL

### apps/web (Next.js frontend)

Package ~ Version ~ Used For ~ Key Methods/Patterns
next ~ * ~ framework ~ App Router | page.tsx | layout.tsx | useRouter()
react ~ * ~ UI library ~ useState() | useEffect() | useRef()
zod ~ * ~ validation ~ z.string() | z.object() | schema.parse() | schema.safeParse()
tailwindcss ~ * ~ styling ~ utility classes | theme.extend in tailwind.config.ts

### packages/ui (shared UI components)

Package ~ Version ~ Used For ~ Key Methods/Patterns
react ~ * ~ peer dependency ~ same as apps/web
storybook ~ * ~ component dev ~ Meta | StoryObj | decorators

### root (monorepo tooling)

Package ~ Version ~ Used For ~ Key Methods/Patterns
pnpm ~ * ~ package manager ~ pnpm install | pnpm --filter
husky ~ * ~ git hooks ~ pre-commit hook
lint-staged ~ * ~ staged file linting ~ runs eslint + prettier on staged files
eslint ~ * ~ linting ~ extends shared config
prettier ~ * ~ formatting ~ shared .prettierrc
playwright ~ * ~ e2e testing ~ test() | expect() | page.goto() | page.fill() | page.click()
jest ~ * ~ backend testing ~ describe() | it() | expect()
vitest ~ * ~ frontend testing ~ describe() | it() | expect()

### Notes

- Version `*` means "use latest at time of install" — update this field when pinning specific versions
- When adding a new package, add it here with Used For and Key Methods/Patterns
- When a package API changes (e.g. breaking update), update Key Methods/Patterns to reflect current usage
- Agents must not use methods not listed in Key Methods/Patterns — if you need a method not listed, flag it for review

## Monorepo Structure

```
/
├── apps/
│   ├── api/              ← NestJS backend
│   └── web/              ← Next.js frontend
├── packages/
│   └── ui/               ← shared UI components | Storybook | reusable across web and mobile
├── docker/
│   ├── dev/
│   │   ├── docker-compose.yml  ← all services + MariaDB + Adminer + hot reload
│   │   ├── api.Dockerfile      ← mounts source | npm run dev | no build step
│   │   └── web.Dockerfile      ← mounts source | npm run dev | no build step
│   └── prod/
│       ├── docker-compose.yml  ← production images only | no Adminer | external DB possible
│       ├── api.Dockerfile      ← multi-stage build | slim production image
│       └── web.Dockerfile      ← multi-stage build | slim production image
├── .github/
│   └── workflows/        ← CI/CD pipelines
├── .husky/               ← git hooks
├── pnpm-workspace.yaml
├── tsconfig.base.json    ← shared TypeScript config
├── .eslintrc.js          ← shared ESLint config
├── .prettierrc           ← shared Prettier config
└── v84-docs/             ← this documentation system
```
