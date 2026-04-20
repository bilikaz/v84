# [v84-1-5][ops:infra]
FROM node:20-slim

# Install pnpm globally
RUN npm install -g pnpm@9

WORKDIR /app

# Copy dependency manifests for the workspaces Storybook renders stories from
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json tsconfig.base.json ./
COPY apps/storybook/package.json ./apps/storybook/package.json
COPY apps/web/package.json ./apps/web/package.json
COPY apps/api/package.json ./apps/api/package.json

# Install dependencies for all workspaces referenced above
RUN pnpm install --frozen-lockfile

# Source is mounted via volumes — no COPY src
CMD ["pnpm", "--filter", "@v84/storybook", "dev"]
