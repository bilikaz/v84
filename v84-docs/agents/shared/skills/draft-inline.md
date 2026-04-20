# Skill: Draft

> Write entries ONLY for your topic scope

## Tag Glossary (know these exactly)

- `{role_tag}` — your role, e.g. `back-nestjs`, `front-nextjs`, `reviewer`, `ops`
- `{topic_tag}` — your topic, e.g. `api`, `entities`, `security`
- `{agent_tag}` — `{role_tag}:{topic_tag}`, e.g. `back-nestjs:api`. This identifies YOU.
- `{v84_tag}` — a plan-node tag like `v84-2-1-1`, taken from `##` / `###` headings in the PLAN section
- Entry reference format: `[{v84_tag}]#{n}` — e.g. `[v84-2-1-1]#1`, `[v84-2-1-1]#2`

Your exact `{role_tag}`, `{topic_tag}`, and `{agent_tag}` values are in the `=== YOU ARE ===` section above.

Placeholders like `{v84_tag}` and `{n}` are TEMPLATES — replace them with real values. NEVER write literal braces like `[{v84-2-1-1}]` or `{n}` in your output.

## Your Context

Everything you need is provided above:
- YOU ARE section tells you your role/topic/scope — STAY INSIDE IT
- CONVENTIONS tell you project rules
- SOURCE TREE shows what files exist
- INSTALLED PACKAGES shows what is available
- TOPIC HISTORY shows what was done before
- PLAN shows what to build (each `##` / `###` heading has a `{v84_tag}`)

## Scope Rules

ONLY write entries for work that falls within YOUR Scope (the Scope line under `=== YOU ARE ===`). Other `{agent_tag}` values handle other work.

Example: if your scope is "Auth flows | roles | guards | token strategy" then:
- YES: JWT strategy, auth guards, login/logout service logic
- NO: user entity (that's entities topic), login page (that's pages topic), login form (that's forms topic), auth API endpoint (that's api topic)

When two topics could claim the same work, the topic whose Scope lists it more specifically owns it. If unsure, do NOT write the entry — the other topic will.

## Output

Think through the plan however you like — analyze scope, check conventions, reason about what's needed. When you're done thinking, mark the start of your entries with:

====== MY RESPONSE ======

Below that line, output ONLY entry lines. No prose, no summaries, no explanations after the marker.

If NOTHING in the plan falls within your scope — output `(empty)` after the marker.

## Entry Format

```
[{v84_tag}]#{n} Short description of what to build
  needs: package-name (npm, apps/api)
  task: what the executor does — imperative, one line
  files: apps/api/src/path/to/file.ts
  depends: [{other_v84_tag}]#{m}
```

`{v84_tag}` MUST match a `##` or `###` heading from the PLAN. Never invent `{v84_tag}` values.
`{n}` starts at 1 and increments per entry within the same `{v84_tag}` (e.g. `#1`, `#2`, `#3`).

Fields after header are optional — include only what applies:
- `replaces:` — old entry from topic history this supersedes
- `expands:` — old entry from topic history this adds to
- `needs:` — new package not in installed packages list
- `task:` — what to build. If your Role is `Reviewer`: use this for what to verify/check.
- `files:` — where to write. **If your Role is `Reviewer`: NEVER include files** — you flag concerns, not file paths.
- `depends:` — another entry that must exist first

Number entries per tag: `#1`, `#2`, `#3`.

## Do NOT

- Write entries outside your scope — other topics handle those
- Duplicate work another topic owns — check your scope boundary
- Invent plan tags — only use headings from the plan
- Write prose, summaries, or explanations — entries only
- Assume packages exist — check installed packages, add `needs:` if missing
