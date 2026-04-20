# [v84-1-3][ops:infra]
FROM node:20-slim

# Install pnpm globally and build tools for native modules (bcrypt)
RUN npm install -g pnpm@9 && \
    apt-get update && apt-get install -y python3 make g++ && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifests only (source mounted via volume)
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json tsconfig.base.json ./
COPY apps/api/package.json ./apps/api/package.json
COPY apps/web/package.json ./apps/web/package.json
COPY apps/storybook/package.json ./apps/storybook/package.json

# Install dependencies
RUN pnpm install --frozen-lockfile

# Source is mounted via volume — no COPY src
CMD ["pnpm", "--filter", "@v84/api", "start:dev"]
