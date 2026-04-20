# Playwright container for e2e tests. Includes browsers + system deps.
# Uses the official Playwright image which ships with everything pre-installed.
# [v84-1-2][ops:infra]
FROM mcr.microsoft.com/playwright:v1.59.1-noble

WORKDIR /app

# Copy dependency manifests
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json tsconfig.base.json ./
COPY apps/api/package.json ./apps/api/package.json
COPY apps/web/package.json ./apps/web/package.json
COPY apps/storybook/package.json ./apps/storybook/package.json

# Install pnpm + deps
RUN npm install -g pnpm@9 && pnpm install --frozen-lockfile

# e2e tests + helpers are mounted via volume.
# Admin account is seeded by the `seed` one-shot service which depends on
# api healthy — by the time e2e starts, `admin@admin.localhost` exists.
CMD ["npx", "playwright", "test", "--reporter=line"]
