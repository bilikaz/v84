# Skill: Compare (Shared)

> Compare the resolved plan against existing final documents to identify impacts on what already exists

## When To Use

After the architect has resolved iteration `{n}` and the merged plan is ready.

## Steps

1. Read `/v84-docs/structure/roles.md` — find your role and its 8 topic tags
2. Read the resolved plan at `/v84-docs/plan/{n}/resolved.md`
3. For each of your topic tags that appear in the plan, read `/v84-docs/final/{role-tag}-{topic-tag}.md`
4. Compare what the plan proposes against what already exists in final docs
5. Generate output at `/v84-docs/plan/{n}/{role-tag}-final.md` — the directory already exists, do not create it

## Output Format

Copy the EXACT structure from the resolved plan — same hierarchy, same tags, same content. Then add your comparison notes inline under relevant items.

- If a final doc is empty (nothing exists yet) — keep the plan content as-is, do not add "net-new" or "nothing to compare" notes
- If something in the final doc is impacted — add a comparison note directly under the relevant plan item
- Use these prefixes for comparison notes:
  - `[reusable]` — exists and can be used as-is. Reference its tag.
  - `[modify]` — exists but needs changes. Say what changes.
  - `[conflict]` — plan contradicts existing decision. Reference both tags.
  - `[extend]` — plan adds to something existing. Reference the existing tag.
  - `[large-scale]` — the thing being changed is used widely. Flag blast radius.

## Example

```
## [v84-2-1]
Add user authentication

- [back-nestjs-entities] User entity: id, email, passwordHash, createdAt
  [modify] Message entity from [v84-1-1] needs a new nullable userId foreign key column
  [large-scale] Message entity is referenced by 3 endpoints — all need auth header handling

- [back-nestjs-api] POST /auth/login — body: {email, password}, response 200: {token}
```

## What NOT To Do

- Do not include other roles' content — your output only covers your role's topics
- Do not add commentary on empty final files — if nothing exists, the plan stands as-is
- Do not rewrite or summarize plan content — copy it exactly, add comparison notes only
- Do not search or read source code — only work with v84-docs files
- Do not invent impacts that don't exist in the final docs
- Do not add summaries, tables, or status overviews — the output IS the plan with comparison notes
- Do not create directories — they already exist

## New Dependencies

If the resolved plan contains items marked `[new-dependency]`, the role agent responsible for that package/service must:
1. Verify it is genuinely missing from `structure/stack.md`
2. Add a `[new-dependency-install]` note with the exact install command and config needed
3. Mark it as `[new-package]` so the architect knows to update stack.md during publish

Example:
```
- [devops-qa-infra] Traefik for reverse proxy routing
  [new-dependency-install] pnpm not applicable — Docker image traefik:v3.6.12 in docker-compose.yml
  [new-package] Traefik v3.6 — reverse proxy | add to Project Stack in stack.md

- [front-nextjs-components] Storybook for component development
  [new-dependency-install] cd packages/ui && pnpm add storybook @storybook/react
  [new-package] storybook — component dev | add to packages/ui in stack.md
```

## Output

Write to `/v84-docs/plan/{n}/{role-tag}-final.md`
