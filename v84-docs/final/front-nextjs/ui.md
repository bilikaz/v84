
# --- iteration 1 ---
[v84-1-5]#1 Scaffold ui/ category folders, sub-barrels, and the initial component set
  needs: react (peer, @v84/web)
  task: scaffold the ui/ tree in five categories — primitives (Button, Badge, Input, Select), data (Table), feedback (Card, Modal), layout (placeholder), forms (placeholder). Each category has its own index.ts sub-barrel re-exporting its components (NO top-level ui/index.ts — consumers import from the category sub-barrel like @/ui/primitives). Include ui/styles.css for shared utility classes that aren't worth a Tailwind plugin. Components are generic and app-agnostic — they never import app data, modules, or hooks.
  files: apps/web/src/ui/primitives/Button.tsx, apps/web/src/ui/primitives/Badge.tsx, apps/web/src/ui/primitives/Input.tsx, apps/web/src/ui/primitives/Select.tsx, apps/web/src/ui/primitives/index.ts, apps/web/src/ui/data/Table.tsx, apps/web/src/ui/data/index.ts, apps/web/src/ui/feedback/Card.tsx, apps/web/src/ui/feedback/Modal.tsx, apps/web/src/ui/feedback/index.ts, apps/web/src/ui/layout/index.ts, apps/web/src/ui/forms/index.ts, apps/web/src/ui/styles.css

[v84-1-5]#2 Add Button story to Storybook
  needs: @storybook/react (dev, @v84/storybook)
  task: create Button.stories.tsx colocated with Button.tsx in ui/primitives/; cover primary, secondary, danger variants and all sizes. Stories live next to their source file (colocation) per Storybook convention, NOT in a separate apps/storybook/stories/ tree.
  files: apps/web/src/ui/primitives/Button.stories.tsx
  depends: [v84-1-5]#1

[v84-1-5]#3 Add Badge story to Storybook
  needs: @storybook/react (dev, @v84/storybook)
  task: create Badge.stories.tsx colocated with Badge.tsx in ui/primitives/
  files: apps/web/src/ui/primitives/Badge.stories.tsx
  depends: [v84-1-5]#1

[v84-1-5]#4 Add Input story to Storybook
  needs: @storybook/react (dev, @v84/storybook)
  task: create Input.stories.tsx colocated with Input.tsx in ui/primitives/
  files: apps/web/src/ui/primitives/Input.stories.tsx
  depends: [v84-1-5]#1

[v84-1-5]#5 Add Select story to Storybook
  needs: @storybook/react (dev, @v84/storybook)
  task: create Select.stories.tsx colocated with Select.tsx in ui/primitives/
  files: apps/web/src/ui/primitives/Select.stories.tsx
  depends: [v84-1-5]#1

[v84-1-5]#6 Add Table story to Storybook
  needs: @storybook/react (dev, @v84/storybook)
  task: create Table.stories.tsx colocated with Table.tsx in ui/data/
  files: apps/web/src/ui/data/Table.stories.tsx
  depends: [v84-1-5]#1

[v84-1-5]#7 Add Card and Modal stories to Storybook
  needs: @storybook/react (dev, @v84/storybook)
  task: create Card.stories.tsx and Modal.stories.tsx colocated with their sources in ui/feedback/
  files: apps/web/src/ui/feedback/Card.stories.tsx, apps/web/src/ui/feedback/Modal.stories.tsx
  depends: [v84-1-5]#1

[v84-1-6]#1 Brand package sources — tokens + copy, dual-format (ESM + CJS + types)
  task: author the repo-root brand/ package that every other workspace consumes. Ship tokens (colors, radii, spacing, typography) and copy (app name, email subjects, taglines) in three formats each so Vite/Storybook (ESM) and NestJS Node-CJS runtimes (CJS) both resolve — one runtime file cannot satisfy both. brand/tokens.mjs + brand/tokens.cjs + brand/tokens.d.ts; same trio for copy. Ship an extra brand/copy.js as a CJS path-resolver shim for tools that resolve by path instead of package exports (jest / ts-node with absolute require paths) — it just does `module.exports = require('./copy.cjs')`. package.json declares the dual-format entry conditions via `exports` with `import`→.mjs, `require`→.cjs, `types`→.d.ts for the `.`, `./tokens`, and `./copy` subpaths. tokens.mjs + tokens.cjs must hold identical values (same for copy.mjs + copy.cjs) — hand-synced per shared conventions. No plain .ts source: would force consumers' tsc into the emit graph and break rootDir.
  files: brand/package.json, brand/tokens.mjs, brand/tokens.cjs, brand/tokens.d.ts, brand/copy.mjs, brand/copy.cjs, brand/copy.d.ts, brand/copy.js

[v84-1-6]#2 Wire brand tokens into Tailwind theme
  needs: @v84/brand (workspace, @v84/web)
  task: confirm tailwind.config.ts in web and storybook extends theme with brand token values for colors, radii, spacing, typography
  files: apps/web/tailwind.config.ts, apps/storybook/tailwind.config.ts
  depends: [v84-1-6]#1

[v84-1-6]#3 Brandbook reference pages (MDX) — Colors, Typography, Spacing, Logos, Introduction
  needs: @storybook/react (dev, @v84/storybook)
  task: create the Brandbook section in Storybook as a set of MDX pages that import live values from repo-root `brand/tokens` and `brand/copy`. Introduction.mdx is the landing page and links the other four. Colors.mdx renders a swatch grid, Typography.mdx shows font families / sizes / weights, Spacing.mdx visualises the spacing scale, Logos.mdx renders the logo variants. Brand reference MDX pages live in apps/storybook/stories/brand/ (the only non-colocated Storybook content — they describe repo-root `brand/` tokens and don't belong next to a single component).
  files: apps/storybook/stories/brand/Introduction.mdx, apps/storybook/stories/brand/Colors.mdx, apps/storybook/stories/brand/Typography.mdx, apps/storybook/stories/brand/Spacing.mdx, apps/storybook/stories/brand/Logos.mdx
  depends: [v84-1-6]#1
