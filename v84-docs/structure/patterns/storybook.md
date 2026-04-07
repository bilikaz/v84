# Storybook Patterns

## NEVER run storybook init

`storybook init` is interactive — it prompts for builder selection and hangs agents. Always create config files manually.

## Manual setup

### Install packages

```bash
cd packages/ui && pnpm add -D storybook @storybook/react @storybook/react-vite react react-dom
```

Storybook needs `react` and `react-dom` as dev dependencies even if they're peer deps — Vite can't resolve them otherwise.

### tsconfig.json

```json
{
  "compilerOptions": {
    "module": "nodenext",
    "moduleResolution": "nodenext",
    "target": "ES2023",
    "jsx": "react-jsx",
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "strict": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "resolvePackageJsonExports": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "./dist"
  },
  "include": ["src/**/*", ".storybook/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

### Config files

```typescript
// packages/ui/.storybook/main.ts
import type { StorybookConfig } from '@storybook/react-vite';

const config: StorybookConfig = {
  stories: ['../src/**/*.stories.@(ts|tsx)'],
  framework: '@storybook/react-vite',
  addons: [],
};

export default config;
```

```typescript
// packages/ui/.storybook/preview.ts
import type { Preview } from '@storybook/react';

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
  },
};

export default preview;
```

### Package.json script

```json
{
  "scripts": {
    "storybook": "storybook dev -p 6006 --config-dir .storybook",
    "build-storybook": "storybook build --config-dir .storybook"
  }
}
```

## Writing stories

```typescript
// src/SpinButton.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { SpinButton } from './SpinButton';

const meta: Meta<typeof SpinButton> = {
  component: SpinButton,
};

export default meta;
type Story = StoryObj<typeof SpinButton>;

export const Default: Story = {
  args: {},
};

export const Disabled: Story = {
  args: {
    disabled: true,
  },
};
```

## Docker — runs in its own container

Storybook has a dev server, so it needs a Docker service with Traefik routing. Do not run it inside the web container.

```yaml
# docker/dev/docker-compose.yml
services:
  storybook:
    build:
      context: ../..
      dockerfile: docker/dev/storybook.Dockerfile
    restart: unless-stopped
    volumes:
      - ../../packages/ui:/app/packages/ui
      - storybook-node-modules:/app/node_modules
      - storybook-app-node-modules:/app/packages/ui/node_modules
    labels:
      - traefik.enable=true
      - traefik.http.routers.storybook.rule=Host(`storybook.localhost`)
      - traefik.http.routers.storybook.entrypoints=web
      - traefik.http.services.storybook.loadbalancer.server.port=6006

volumes:
  storybook-node-modules:
  storybook-app-node-modules:
```

```dockerfile
# docker/dev/storybook.Dockerfile
FROM node:22-alpine
RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /app
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/api/package.json ./apps/api/
COPY apps/web/package.json ./apps/web/
COPY packages/ui/package.json ./packages/ui/
RUN pnpm install --frozen-lockfile --filter @my-app/ui...
WORKDIR /app/packages/ui
CMD sh -c 'if [ ! -d /app/node_modules/.pnpm ]; then cd /app && pnpm install --frozen-lockfile --filter @my-app/ui...; fi && pnpm run storybook'
```
