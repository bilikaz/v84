[v84-1-4]#1 Root layout with providers and brand metadata
  task: create app/layout.tsx — html shell, import globals.css, wrap children in AuthProvider + GoogleProvider, metadata from `@/config`. Layout reads copy and env from the config sub-barrel; direct `brand/*` or `process.env` access is not allowed here (use the wrappers from [v84-1-4]#8 below).
  files: apps/web/src/app/layout.tsx, apps/web/src/app/globals.css

[v84-1-4]#2 Public landing page (placeholder)
  task: create app/(public)/page.tsx as 2-line re-export from modules/home/pages/HomePage
  files: apps/web/src/app/(public)/page.tsx, apps/web/src/modules/home/pages/HomePage.tsx

[v84-1-4]#3 Auth route group — login, register, forgot/reset password, verification
  task: create page.tsx files under app/auth/* as 2-line re-exports from modules/auth. Verification and reset-password use path-param shape ([token]) so the token lands in the URL — the verify route nests under /auth/register/ because it's the final step of the registration journey, not a separate resource.
  files: apps/web/src/app/auth/login/page.tsx, apps/web/src/app/auth/register/page.tsx, apps/web/src/app/auth/register/[token]/page.tsx, apps/web/src/app/auth/forgot-password/page.tsx, apps/web/src/app/auth/reset-password/[token]/page.tsx

[v84-1-4]#4 Dashboard layout and index page
  task: create app/dashboard/layout.tsx (auth-gated shell) and app/dashboard/page.tsx as 2-line re-export from modules/dashboard
  files: apps/web/src/app/dashboard/layout.tsx, apps/web/src/app/dashboard/page.tsx
  depends: [v84-1-4]#1

[v84-1-4]#5 Dashboard settings pages
  task: create page.tsx files under app/dashboard/settings/* as 2-line re-exports from modules/account
  files: apps/web/src/app/dashboard/settings/page.tsx, apps/web/src/app/dashboard/settings/confirm-email/page.tsx
  depends: [v84-1-4]#4

[v84-1-4]#6 Admin layout and index page
  task: create app/admin/layout.tsx (admin-role-gated shell) and app/admin/page.tsx as 2-line re-export from modules/admin
  files: apps/web/src/app/admin/layout.tsx, apps/web/src/app/admin/page.tsx
  depends: [v84-1-4]#1

[v84-1-4]#7 Admin user management pages
  task: create page.tsx files under app/admin/users/* as 2-line re-exports from modules/users
  files: apps/web/src/app/admin/users/page.tsx, apps/web/src/app/admin/users/new/page.tsx, apps/web/src/app/admin/users/[id]/edit/page.tsx
  depends: [v84-1-4]#6

[v84-1-4]#8 Frontend config wrappers — brand re-export, env readers, sub-barrel
  task: frontend code imports env and brand exclusively through a single `@/config` sub-barrel so src/ stays insulated from repo-root `brand/` and from `process.env`. Create config/brand.ts that re-exports `copy` from the repo-root brand package (parallel to api's templates/emails/theme.ts re-export — brand lives outside apps/web/src/, so direct imports break tsc rootDir). Create config/public-env.ts that reads NEXT_PUBLIC_* values (safe in client and server code). Create config/server-env.ts that begins with `import 'server-only'` so any accidental client import fails at build time, and reads secrets / server-only env. Create config/index.ts that re-exports copy + publicEnv + routes helpers; do NOT re-export serverEnv from the top-level barrel (keep it reachable only via `@/config/server-env` so the server-only gate survives accidental client paths).
  files: apps/web/src/config/brand.ts, apps/web/src/config/public-env.ts, apps/web/src/config/server-env.ts, apps/web/src/config/index.ts
[v84-1-4]#9 Common sub-barrels for guards, hooks, providers
  task: create the sub-barrel index.ts files at `common/{guards,hooks,providers}/` that re-export the symbols in each folder. Per convention, imports go through these sub-barrels (`@/common/guards`, `@/common/hooks`, `@/common/providers`) — never a top-level `common/index.ts`. Initially each barrel may be empty; later iterations append their new symbols.
  files: apps/web/src/common/guards/index.ts, apps/web/src/common/hooks/index.ts, apps/web/src/common/providers/index.ts
[v84-1-4]#10 Dashboard shell and sub-barrel
  task: create `modules/dashboard/components/UserShell.tsx` — the auth-gated shell chrome used by `app/dashboard/layout.tsx` (nav, user dropdown, slot for page content) and re-export it from `modules/dashboard/components/index.ts`. UserShell composes the route guards and the page outline; the dashboard page components slot into its children.
  files: apps/web/src/modules/dashboard/components/UserShell.tsx, apps/web/src/modules/dashboard/components/index.ts
  depends: [v84-1-4]#4

