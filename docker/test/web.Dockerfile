# [v84-1-2][ops:infra]
FROM node:20-slim

# Install pnpm globally
RUN npm install -g pnpm@9

WORKDIR /app

# Copy dependency manifests only (source mounted via volume)
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json tsconfig.base.json ./
COPY apps/web/package.json ./apps/web/package.json

# Install dependencies
RUN pnpm install --frozen-lockfile

# Source is mounted via volume — no COPY src
CMD ["pnpm", "--filter", "@v84/web", "dev"]
