# Skill: Publish

> Update the 32 atomic final files with what was done in this iteration

## When To Use

After the executor has completed all tasks in iteration `{n}`.

## Steps

1. Read `/v84-docs/plan/{n}/final.md` — the tagged reference document
2. Read `/v84-docs/plan/{n}/tasks.md` — check which tasks were marked [done]
3. Read `/v84-docs/structure/roles.md` — for role-topic tag mapping
4. For each `{role-tag}-{topic-tag}` that has content in final.md, update `/v84-docs/final/{role-tag}-{topic-tag}.md`
5. Run `bash v84-docs/trees/generate.sh` to refresh trees after code changes
6. Update `/v84-docs/state.md` — mark publish step as done
7. Do not create directories — they already exist

## How To Update Final Files

For each item tagged `[{role-tag}-{topic-tag}]` in final.md, write it to the corresponding file in `final/`.

### New items (iteration 1 or first time this topic has content)

Add the item with its v84 tag:

```
[v84-1-2] Message entity: id (int PK auto-inc), key (varchar(36) uuid v4 unique indexed), body (text), createdAt (datetime @CreateDateColumn). Strict mode: all fields use !.
```

### Unchanged items from previous iterations

If an item from a previous iteration is NOT mentioned in this iteration's final.md, leave it as-is. Do not touch it, do not re-add it, do not mark it.

### Reused items

If the compare step marked something `[reusable]`, add a reference note:

```
[v84-1-2] Message entity: id, key, body, createdAt
[reused by v84-3-1] — no changes needed, used as-is for the notification feature
```

### Modified items

If the compare step marked something `[modify]`, update the entry and mark the change:

```
[v84-1-2] Message entity: id, key, body, createdAt
[modified by v84-3-2] added column: expiresAt (datetime, nullable) for TTL feature
```

### Replaced / deprecated items

If something was replaced by this iteration, mark the old entry as deprecated and add the new one:

```
[v84-1-2] [deprecated by v84-4-1] Message entity with body field
[v84-4-1] SecureMessage entity with encryptedBody field — replaced Message for encryption support
```

### Extended items

If the compare step marked something `[extend]`, add the extension:

```
[v84-1-2] POST /messages — create message, returns key
[extended by v84-3-1] added optional query param ?ttl=3600 for message expiration
```

## What Goes Into Which File

The tag prefix determines the file:
- `[back-nestjs-entities]` → `final/back-nestjs-entities.md`
- `[business-risk]` → `final/business-risk.md`
- `[front-nextjs-components]` → `final/front-nextjs-components.md`

## What NOT To Do

- Do not write to files that have no new content from this iteration — if business-compliance has nothing new, skip it
- Do not remove or overwrite previous iteration content — append or annotate
- Do not drop v84 tags — every entry must have its tag for cross-reference
- Do not create directories — they already exist
- Do not search or read source code

## Update stack.md with new packages

After updating final files, check the compare outputs (`plan/{n}/{role-tag}-final.md`) for any items marked `[new-package]`. For each one:
1. Add it to the correct section in `structure/stack.md` (Project Stack for infrastructure, Installed Packages for npm packages)
2. Include version, Used For, and Key Methods/Patterns
3. If it's a Docker image (like Traefik), add to Project Stack table
4. If it's an npm package, add to the relevant app section (apps/api, apps/web, packages/ui)

This keeps stack.md as the single source of truth for what is installed.
