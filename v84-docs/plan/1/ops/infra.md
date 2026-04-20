[v84-1-2]#1 Dev Docker Compose stack
  task: author docker/dev/docker-compose.yml that orchestrates the full dev environment — Traefik reverse proxy with .localhost domain routing (v84-1-2-1), MariaDB + Adminer (v84-1-2-2), Redis for sessions (v84-1-2-3), Mailpit SMTP+web UI (v84-1-2-4), api service (v84-1-3), web service (v84-1-4), storybook service (v84-1-5). Each service reachable at its own .localhost host via Traefik labels. Mount source code bind volumes for hot reload on api/web/storybook. Name volumes for db + redis persistence across restarts. Tag each service block with its specific `[v84-1-2-x]` or `[v84-1-{3,4,5}]` sub-tag so the file carries the v84 tags of every deliverable it wires up.
  files: docker/dev/docker-compose.yml

[v84-1-3]#8 API Dockerfile
  task: multi-stage Dockerfile for the NestJS api workspace. Dev stage runs `pnpm start:dev` with ts-node and source bind-mounted for hot reload; prod stage does `pnpm build` + runs compiled dist/main.js under node. Use node:20-slim base, install pnpm via corepack.
  files: docker/dev/api.Dockerfile

[v84-1-4]#3 Web Dockerfile
  task: multi-stage Dockerfile for the Next.js web workspace. Dev stage runs `next dev` with source bind-mounted for HMR; prod stage does `next build` + `next start`. Use node:20-slim base, install pnpm via corepack.
  files: docker/dev/web.Dockerfile

[v84-1-5]#8 Storybook Dockerfile
  task: Dockerfile for the Storybook host workspace — runs `storybook dev -p 6006` with apps/web/src/ui and apps/api/src/templates bind-mounted so live stories pick up edits without rebuild. Storybook is dev-only; no prod stage.
  files: docker/dev/storybook.Dockerfile

[v84-1-4]#11 Next.js app config files
  task: set up the framework-level config that lives at the web workspace root — `next.config.ts` (output settings, redirects, image domains) and `postcss.config.js` (PostCSS pipeline wiring Tailwind + autoprefixer). These aren't `src/` code and don't belong under any feature module; they govern how the Next.js app builds and serves. `next-env.d.ts` is deliberately excluded — Next.js auto-regenerates it on every build, so any hand-added tag would be wiped.
  files: apps/web/next.config.ts, apps/web/postcss.config.js

[v84-1-5]#9 Storybook host config files
  task: set up `apps/storybook/.storybook/main.ts` (stories globs pointing at `apps/web/src/ui` and `apps/api/src/templates`, addon list, framework opts) and `.storybook/preview.ts` (global decorators + parameters — layout, backgrounds, brand theme). Also `apps/storybook/postcss.config.js` so Tailwind utilities resolve identically between the web app and the Storybook host.
  files: apps/storybook/.storybook/main.ts, apps/storybook/.storybook/preview.ts, apps/storybook/postcss.config.js

[v84-1-2]#2 Parallel test Docker stack
  task: author `docker/test/docker-compose.yml` — a second compose file that mirrors the dev stack (MariaDB + Redis + Mailpit + API + Web) but is completely isolated from dev (separate volume names, separate network, separate ports, `NODE_ENV=test`). Integration and e2e tests run against this stack so nothing pollutes the dev database or inbox. Ship three dedicated Dockerfiles: `docker/test/api.Dockerfile` (NestJS image tuned for test runs with test deps installed), `docker/test/web.Dockerfile` (Next.js built for the test environment), and `docker/test/e2e.Dockerfile` (Playwright runner with its system dependencies). Iter-5 extends this stack with GitHub Actions + local run scripts, but the stack itself is project-skeleton infra.
  files: docker/test/docker-compose.yml, docker/test/api.Dockerfile, docker/test/web.Dockerfile, docker/test/e2e.Dockerfile
