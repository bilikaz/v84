# @v84/storybook

Dev-only Storybook instance. **No source of its own** — this workspace exists purely to host the Storybook dev server, its deps, and its config. Stories live next to the code they document, in the consuming apps.

## What it shows

Stories are globbed from two locations in [`.storybook/main.ts`](.storybook/main.ts):

| Glob | Owner | What's in it |
|------|-------|--------------|
| `../../web/src/ui/**/*.stories.@(ts|tsx)` | `@v84/web` | Design-system primitives (`Button`, `Input`, `Card`, `Modal`, `Table`, etc.) — used by the web app |
| `../../api/src/templates/**/*.stories.@(ts|tsx)` | `@v84/api` | React Email templates (`EmailLayout`, `PasswordResetEmail`, …) — rendered by the API's `NotificationsService` |

Add new stories directly next to the component they describe; Storybook will pick them up on next HMR.

## Why is it in `apps/` and not `packages/`?

- It's a long-running dev server with its own Dockerfile and Traefik route (`http://storybook.localhost`) — architecturally it's a third app alongside `web` and `api`, not a library imported by them.
- `packages/` in this repo is reserved for code that would actually be imported from multiple workspaces. There's no second consumer for Storybook.
- If additional dev-tool configs appear later (`eslint-config`, `tsconfig`, …), they should go in `packages/` and Storybook can stay here — the patterns are complementary, not competing.

## Why are stories not in this workspace?

Colocation rule across the repo: **stories live next to their source**. A UI primitive owned by `apps/web` keeps its story in `apps/web/src/ui/<Component>.stories.tsx`; an email template owned by `apps/api` keeps its story in `apps/api/src/templates/emails/<Template>.stories.tsx`. This workspace only holds the Storybook runtime.

## Running

```bash
# local (uses docker-compose)
docker compose -f docker/dev/docker-compose.yml up -d storybook

# direct (from this directory)
pnpm dev
```

Then visit http://storybook.localhost (via Traefik) or http://localhost:6006.

## Adding a new story

1. Create `<Component>.stories.tsx` next to the component file inside either `apps/web/src/ui/**` or `apps/api/src/templates/**`.
2. Nothing to configure here — the glob picks it up.
3. If the story needs a new dev dep (e.g. `@storybook/addon-interactions`), add it to this workspace's `package.json`, not the component's app.

## Adding a new source location

If a new app grows stories (e.g. `apps/worker/src/jobs/**/*.stories.tsx`), add a glob line to [`.storybook/main.ts`](.storybook/main.ts) and the equivalent content path to [`tailwind.config.ts`](tailwind.config.ts). Also bind-mount the source into the storybook container in [`docker/dev/docker-compose.yml`](../../docker/dev/docker-compose.yml).

## Caveats

- **Source is bind-mounted, not copied.** The storybook container reads `apps/web/src` and `apps/api/src` via read-only bind mounts defined in `docker/dev/docker-compose.yml`. If a story imports a symbol that isn't visible under those paths, add a mount.
- **Story files are excluded from the consuming app's `tsc`.** Both `apps/web/tsconfig.json` and `apps/api/tsconfig.json` exclude `src/**/*.stories.tsx` so the app's compile graph never sees `@storybook/react`. If you add a new story location, add the same exclude to that app.
- **Tailwind content paths are duplicated here.** This workspace has its own [`tailwind.config.ts`](tailwind.config.ts) listing both source trees so Storybook previews match the app styles. Keep it in sync when a new story location is added.
