# Docker Compose Patterns

## Database volumes — always persist data

Every database service must have a named volume. Without it, data is lost on container restart.

```yaml
# CORRECT — named volume for persistence
services:
  db:
    image: mariadb:latest
    volumes:
      - db_data:/var/lib/mysql

volumes:
  db_data:

# WRONG — no volume, data lost on restart
services:
  db:
    image: mariadb:latest
```

Common mount paths by database:
- MariaDB/MySQL: `/var/lib/mysql`
- PostgreSQL: `/var/lib/postgresql/data`
- MongoDB: `/data/db`
- Redis: `/data`

## Named volumes for node_modules — prevent host/container conflicts

In dev, source is mounted from host but node_modules must stay container-only. Named volumes shadow the host's node_modules so the container uses its own installs.

```yaml
services:
  api:
    volumes:
      - ../../apps/api:/app/apps/api          # mount entire app dir for hot-reload
      - api-node-modules:/app/node_modules     # shadow root node_modules
      - api-app-node-modules:/app/apps/api/node_modules  # shadow app node_modules

volumes:
  api-node-modules:
  api-app-node-modules:
```

Without this, the host's node_modules (possibly built for a different OS/Node version) leaks into the container and causes ESM/CJS errors, missing native bindings, etc.

## Dockerfile — install only, no source copy for dev

Dev Dockerfiles copy only package manifests and install deps. Source is mounted as a volume at runtime — no COPY needed. Use `--filter` to install only the workspace packages needed.

```dockerfile
FROM node:22-alpine
RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /app

# Copy manifests only for layer caching
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/api/package.json ./apps/api/
COPY apps/web/package.json ./apps/web/
COPY packages/ui/package.json ./packages/ui/

# Install only deps needed by this service
RUN pnpm install --frozen-lockfile --filter @my-app/api...

# Source mounted at runtime
WORKDIR /app/apps/api

# Re-install if named volume shadowed build deps, then start
CMD sh -c 'if [ ! -d /app/node_modules/.pnpm ]; then cd /app && pnpm install --frozen-lockfile --filter @my-app/api...; fi && pnpm run dev'
```

Use **Node 22+** — Node 20 cannot `require()` ESM modules, which breaks TypeORM and other packages that ship as ESM-only. Node 22.12+ supports ESM/CJS interop without flags.

The CMD check handles first-run with empty named volumes — if node_modules was shadowed by an empty volume, it re-installs before starting. Subsequent runs skip this since the volume persists.

## Lockfile — always copy it

Always copy the lockfile alongside package.json. Without it, `--frozen-lockfile` fails.

Lockfile per package manager:
- pnpm: `pnpm-lock.yaml`
- npm: `package-lock.json`
- yarn: `yarn.lock`

## Environment variables — use .env file, not hardcoded values

```yaml
# CORRECT — reference from .env
services:
  db:
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${DATABASE_NAME}

# WRONG — hardcoded credentials
services:
  db:
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: raffle
```

## Traefik routing — .localhost domains in dev, no raw ports

Dev services are accessed via `.localhost` domains through Traefik, not direct port mappings. Only Traefik exposes port 80.

```yaml
# CORRECT — Traefik routes by hostname
services:
  api:
    labels:
      - traefik.enable=true
      - traefik.http.routers.api.rule=Host(`api.localhost`)
      - traefik.http.services.api.loadbalancer.server.port=3001

# WRONG — raw port mapping
services:
  api:
    ports:
      - "3001:3001"
```

## Dev tools with servers — every runnable tool gets a container

If a package runs a dev server (Storybook, mail catcher, queue dashboard, Swagger UI standalone, etc.), it must have a Docker service with Traefik routing. A tool without a container is invisible.

```yaml
# Storybook example
services:
  storybook:
    build:
      context: ../..
      dockerfile: docker/dev/storybook.Dockerfile
    volumes:
      - ../../packages/ui:/app/packages/ui
      - storybook-node-modules:/app/node_modules
      - storybook-app-node-modules:/app/packages/ui/node_modules
    labels:
      - traefik.enable=true
      - traefik.http.routers.storybook.rule=Host(`storybook.localhost`)
      - traefik.http.routers.storybook.entrypoints=web
      - traefik.http.services.storybook.loadbalancer.server.port=6006
```

## Database healthcheck — always add, use depends_on condition

Services that need the DB must wait for it to be ready, not just started.

```yaml
services:
  db:
    image: mariadb:11.4
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    labels:
      - traefik.enable=false

  api:
    depends_on:
      db:
        condition: service_healthy    # wait for DB to be actually ready
```

Do NOT use `depends_on: - db` without `condition: service_healthy` — the container starts but the DB may not be accepting connections yet.

## Internal services — no Traefik, no ports

Services only accessed by other containers (like databases) get no port mapping and no Traefik routing.

## restart policy — always unless-stopped

Every dev service gets `restart: unless-stopped`. Containers crash during development — auto-restart keeps the environment running.

```yaml
services:
  api:
    restart: unless-stopped
```
