# Next.js 16 Patterns

## Configuration — all config lives in config files, not in code

All env parsing, defaults, and type conversion happen in config files inside a `config/` folder. Components and pages use only typed getters — no `process.env.NEXT_PUBLIC_*` scattered in components.

### Config file

```typescript
// src/config/api.config.ts
const apiConfig = {
  baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://api.localhost',
} as const;

export default apiConfig;
```

All `NEXT_PUBLIC_*` env values are read here, nowhere else. Defaults and fallbacks go here only.

### Using config in code — import, never env direct

```typescript
// CORRECT — import from config
import apiConfig from '@/config/api.config';

const res = await fetch(`${apiConfig.baseUrl}/api/spins`);

// WRONG — never do this in components or pages
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
```

### Config folder structure

```
src/config/
├── api.config.ts        ← NEXT_PUBLIC_API_URL
└── index.ts             ← barrel export
```

## tsconfig — no baseUrl

`baseUrl` is deprecated in TypeScript 7.0. Use `paths` without `baseUrl`:

```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

Do NOT add `"baseUrl": "."` — it triggers deprecation warnings and will break in TS 7.

## Proxy (not middleware)

Next.js 16 uses `proxy` instead of `middleware`. The function is also called `proxy`, not `middleware`.

```ts
// src/app/proxy.ts
export function proxy(request: Request) {
  // runs before the request reaches the page
}
```
