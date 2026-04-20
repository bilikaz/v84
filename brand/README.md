# V84 Brand

This folder holds the **primitives** that define the V84 brand identity: colors, typography, spacing, logos, fonts. It is the single source of truth for every visual that ships anywhere — web app, email templates, future mobile apps, PDF exports.

The folder **is not** the brandbook. The folder holds data. The **Brandbook** is the *view* of that data, rendered in Storybook under the `Brandbook/` sidebar group (see [apps/storybook/stories/brand/](../apps/storybook/stories/brand/)). Folder = primitives, Storybook section = the book rendered from them.

## Contents

| Path | What it is | Who reads it |
|------|------------|--------------|
| [`tokens.mjs`](tokens.mjs) | ESM version of the token values | Vite/Storybook, Tailwind (via Next.js), any ESM consumer |
| [`tokens.cjs`](tokens.cjs) | CommonJS copy of the same values — hand-synced with `tokens.mjs` | Node runtime (api email templates compile to CJS and `require()` this) |
| [`tokens.d.ts`](tokens.d.ts) | Type declarations shared by both runtime files | TypeScript everywhere (tsc uses this for type checking) |
| [`package.json`](package.json) | Routes imports via `exports` conditions: `import` → `tokens.mjs`, `require` → `tokens.cjs`, `types` → `tokens.d.ts` | Every consumer — pkg-exports picks the right file automatically |
| [`logos/`](logos/) | SVG logos (main + alt) | Next.js (via `apps/web/public/brand` symlink), Storybook (via `staticDirs`) |
| `fonts/` *(optional)* | Self-hosted `.woff2` files | Web via `next/font/local` — email templates use a system stack |
| [`README.md`](README.md) | This file | Humans reading the repo |

## The "source vs view" pattern

This is the key rule, and it's non-obvious until you've been bitten by the alternative:

> **Code consumes `brand/tokens` directly. Docs (MDX) import the same `brand/tokens` and render it for humans.**

**Why this matters.** The #1 failure mode of design-system docs is drift: the docs say "brand color is `#4f46e5`" but the actual code ships `#4338ca` because someone changed it six months ago and forgot to update the docs. That class of bug disappears entirely when the docs import the same file the code imports — changing the value changes both at once.

**Concrete example — colors:**

```
brand/tokens.mjs + tokens.cjs    ← colors.brand = '#000000'  (hand-synced)
brand/tokens.d.ts                ← types for the same data
brand/package.json               ← exports conditions route import/require
   │
   ├─────────────────────┬───────────────────────┐
   │                     │                       │
   ▼                     ▼                       ▼
tailwind.config.ts    email/theme.ts           apps/storybook/stories/brand/Colors.mdx
(ESM → tokens.mjs)    (CJS → tokens.cjs)       (ESM → tokens.mjs)

All three read the same value. Change both .mjs and .cjs → all three update.
```

**Rule of thumb:**

- **Anything the code has to consume at build/runtime** → lives as an export in both `tokens.mjs` and `tokens.cjs` (with a matching entry in `tokens.d.ts`).
- **Anything only humans read** → lives in an MDX page in `apps/storybook/stories/brand/`. Those MDX pages **import from `brand/tokens`** to render live values.
- **Anything in between** (logo files, fonts) → lives as real files under `brand/` or `apps/web/public/brand/`, referenced by both code and docs via a stable path.

**What does NOT go in `tokens.mjs`/`tokens.cjs`:**

- Tailwind-shaped structures (e.g. `{ primary: { 500: ..., 600: ... } }`) — `tokens.js` stays flat and consumer-neutral. Tailwind config reshapes primitives into its own conventions.
- Component-specific values (button padding, card shadow) — those live with their components, composed from these primitives.
- Voice/tone text, usage don'ts — those are pure prose and live in their own MDX pages in Storybook, not in code.

## Why dual format (`.mjs` + `.cjs` + `.d.ts`)?

Two problems forced this shape:

**1. `rootDir` — tokens can't be a `.ts` file.**
`brand/` needs to be importable from apps that each have their own `tsconfig.json` with different `rootDir` settings. A plain `brand/tokens.ts` would force every consumer's `tsc` to bring the file into its own compile graph — and api's `rootDir: ./src` specifically rejects source files from outside `apps/api/src`. Fighting that by removing `rootDir` or adding path aliases ripples into nest-cli output paths, runtime resolution, and a series of secondary bugs.

So we ship tokens as a pre-compiled runtime module + a sibling `.d.ts`. Every consumer's tsc treats `brand/` the way it treats any dependency in `node_modules`: `.d.ts` for types (not emitted, so `rootDir` doesn't fire), `.js` for runtime.

**2. ESM vs CJS — one runtime file isn't enough.**
Three very different tools consume tokens:

- **Vite** (Storybook) serves files from `/@fs/...` as ESM and won't do CJS-to-ESM interop on arbitrary user files. Needs `export const X = ...`.
- **Next.js Tailwind** loads `tailwind.config.ts` via jiti, which handles ESM cleanly. Prefers `export const`.
- **Nest api** compiles TypeScript to `module: commonjs`, so its runtime is plain `require()`. Can't `require()` an ESM file in Node 20.

One file can't satisfy both. The clean solution is **dual format** with `package.json` `exports` conditions:

```json
"exports": {
  ".": {
    "types": "./tokens.d.ts",
    "import": "./tokens.mjs",
    "require": "./tokens.cjs"
  }
}
```

Every consumer writes the same import (`from '../../brand/tokens'` or `from '../../../brand'`), and the resolver routes it to the right file based on module system: ESM gets `.mjs`, CJS gets `.cjs`, TypeScript gets `.d.ts`. Nobody has to know which file they're reading — it just works.

**The tradeoff:** `tokens.mjs` and `tokens.cjs` are hand-synced. They're small, rarely change, and mismatches surface immediately (either as type errors at MDX/Tailwind, or as undefined values at api runtime). Treat `.mjs` as the source you edit; copy any change into `.cjs` in the same commit.

## How each consumer uses it

### Web — Tailwind

```ts
// apps/web/tailwind.config.ts
import { colors, radii, spacing, typography } from '../../brand/tokens';

const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors,
      borderRadius: radii,
      spacing,
      fontFamily: typography.fontFamily,
      fontSize: typography.fontSize,
      fontWeight: typography.fontWeight,
      lineHeight: typography.lineHeight,
    },
  },
  plugins: [],
};
```

Now `className="bg-brand text-surface"` works, and the values are guaranteed to match the brandbook.

### Web — fonts (if self-hosted)

```ts
// apps/web/src/app/layout.tsx
import localFont from 'next/font/local';

const displayFont = localFont({
  src: [
    { path: '../../../brand/fonts/Inter-Regular.woff2', weight: '400' },
    { path: '../../../brand/fonts/Inter-SemiBold.woff2', weight: '600' },
  ],
  variable: '--font-display',
});
```

The CSS variable `--font-display` is referenced by `typography.fontFamily.display` in `tokens.mjs`/`tokens.cjs`, so Tailwind and email templates both resolve to the same font chain.

### API — email templates

```ts
// apps/api/src/templates/emails/theme.ts
// Directory import — resolves via brand/package.json exports map.
// api compiles to CJS, so the `require` condition picks tokens.cjs at runtime;
// tsc uses tokens.d.ts for type checking. The directory form (not './brand/tokens')
// makes tsc treat this as an external module and skip the rootDir check for project source files.
export { colors, radii, spacing, typography } from '../../../../../brand';
```

```tsx
// apps/api/src/templates/emails/EmailLayout.tsx
import { colors, typography } from './theme';

<Text style={{ color: colors.text, fontFamily: typography.fontFamily.sans }}>
  ...
</Text>
```

Email clients strip CSS classes, so email templates use inline styles — but the *values* come from the same tokens as the web app.

### Storybook — live documentation

```mdx
// apps/storybook/stories/brand/Colors.mdx
import { colors } from '../../../../brand/tokens';
import { Meta } from '@storybook/blocks';

<Meta title="Brandbook/Colors" />

# Colors

{Object.entries(colors).map(([name, hex]) => (
  <Swatch key={name} name={name} hex={hex} />
))}
```

Storybook's Vite is an ESM consumer, so pkg-exports routes it to `tokens.mjs`. The swatches render the same hex values the code ships. No manual sync between the view and the source — though the `.mjs`/`.cjs` pair themselves do need to stay in sync (see the note above).

## Adding a new token

1. Add the constant to **all three** files: `tokens.mjs`, `tokens.cjs`, and `tokens.d.ts`. The `.mjs` and `.cjs` are hand-synced — they must hold identical values.
2. If web needs a Tailwind class for it, make sure `tailwind.config.ts` is reshaping it correctly (usually no change — it picks up new keys automatically).
3. If the brandbook should show it, update the relevant MDX page in [apps/storybook/stories/brand/](../apps/storybook/stories/brand/) to iterate over the new shape.
4. No duplication anywhere else — every other consumer reads from the same triple.

## Removing a token

1. Delete the constant from `tokens.mjs`, `tokens.cjs`, and `tokens.d.ts`.
2. TypeScript will error at every consumer (tailwind config, email templates, MDX pages).
3. Fix each error — rename or replace. The compiler is your migration tool.

## Why not put tokens in MDX directly?

MDX is *read* by Storybook, not *imported as a data module* by the rest of the codebase. `tailwind.config.ts` cannot `import { colors } from '../../apps/storybook/stories/brand/Colors.mdx'`. So if tokens lived only in MDX, both the web tailwind config and the email templates would have to duplicate the values — exactly the drift problem we're trying to avoid. Tokens are data; MDX is a view of the data; the arrow points one way.

## Why not use a brand-book SaaS (Zeroheight, Supernova)?

Good tools, wrong stage. A SaaS brandbook makes sense when you have a design team large enough that non-developer editing is a recurring bottleneck (typically 15–20+ people). Below that scale, the overhead of maintaining a second platform, keeping tokens in sync, and paying for licenses outweighs the benefit. Storybook with MDX is free, versioned with the repo, and renders live values — the right answer for our size.

## Why not put `brand/` under `apps/web/`?

Because brand is bigger than any one app. The web app consumes it, the API consumes it (for email templates), a future mobile app or PDF-export service would consume it. Putting it under `apps/web/` would imply ownership by web, which is wrong — web is one consumer among several. Repo-root reflects the real scope.

**Exception:** logo *images* live in `apps/web/public/brand/` because the web app is the thing serving HTTP requests. Email templates reference them via `${WEB_URL}/brand/...`. Code lives at root, served files live under the server.
