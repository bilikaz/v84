
# --- iteration 1 ---
[v84-1-1]#1 Pin pnpm version in packageManager field
  needs: pnpm (tool, match lockfile version)
  task: add "packageManager" field to root package.json with exact pnpm version from lockfile
  files: package.json

[v84-1-1]#2 Align typescript version across workspaces
  needs: typescript (devDependency, ^5.5.0)
  task: verify all four workspaces resolve the same TS minor; pin range in root and inherit via tsconfig
  files: package.json, apps/api/package.json, apps/web/package.json, apps/storybook/package.json

[v84-1-1]#3 Add shared eslint config package or root overrides for workspace consistency
  needs: eslint (devDependency, ^8.57.0)
  task: confirm apps inherit root .eslintrc.js; add workspace-specific override files only where needed
  files: .eslintrc.js, apps/api/package.json, apps/web/package.json

[v84-1-1]#4 Move @faker-js/faker to devDependencies
  needs: @faker-js/faker (devDependency, ^10.4.0)
  task: move @faker-js/faker from dependencies to devDependencies in api package.json
  files: apps/api/package.json

[v84-1-3]#1 Ensure NestJS peer dependencies stay aligned
  needs: @nestjs/core @nestjs/common @nestjs/platform-express (dependency, ^11.0.0)
  task: verify all @nestjs/* packages resolve to the same 11.x minor to avoid peer conflicts
  files: apps/api/package.json, pnpm-lock.yaml

[v84-1-4]#1 Add @testing-library/jest-dom for web test matchers
  needs: @testing-library/jest-dom (devDependency, ^6.0.0)
  task: add @testing-library/jest-dom to web devDependencies and configure vitest setup file
  files: apps/web/package.json, apps/web/vitest.config.ts

[v84-1-4]#2 Evaluate Tailwind v3 vs v4 before locking in
  needs: tailwindcss (devDependency, ^3.4.13)
  task: decide whether to stay on TW 3.x or migrate to 4.x now; document decision; align version in web and storybook
  files: apps/web/package.json, apps/storybook/package.json

[v84-1-5]#1 Align Storybook addon versions
  needs: @storybook/* (devDependency, ^8.3.0)
  task: verify all @storybook/* packages pin same minor range to prevent version skew
  files: apps/storybook/package.json

[v84-1-5]#2 Add react and react-dom as workspace catalog shared versions
  needs: react react-dom (dependency, ^19.1.0)
  task: use pnpm catalog or workspace protocol to deduplicate react across api, web, and storybook
  files: pnpm-workspace.yaml, apps/api/package.json, apps/web/package.json, apps/storybook/package.json

[v84-1-6]#1 Add brand package to pnpm workspace
  needs: brand (workspace, local)
  task: add brand/ to pnpm-workspace.yaml packages list so other workspaces can reference it
  files: pnpm-workspace.yaml, brand/package.json

# --- iteration 2 ---
[v84-2-2-1]#1 Add @nestjs/throttler for rate limiting on auth endpoints
  needs: @nestjs/throttler (dependency, latest)
  task: add @nestjs/throttler to apps/api/package.json
  files: apps/api/package.json
