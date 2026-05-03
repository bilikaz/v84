# Format

> YAML on disk, JSON Schema on the wire. Markdown only for
> free-form agent prose under `instructions/`. Tight rules on
> naming, ids, and prose fields keep parsing trivial.

This page covers naming conventions and the on-disk YAML
discipline. The on-wire JSON Schema protocol — how the harness
talks to the model — lives in [llm-format.md](llm-format.md).

## YAML by default (on disk)

Every file under `<project>/v84/` is YAML. No bespoke text
formats. No mixed structure + prose files. Parsing is `yaml.safe_load`
end-to-end.

Markdown only in three places:
- Agent system prompts under `v84-docs/instructions/<group>/<stem>.md`
  (paired with a `<stem>.schema.json`).
- These conceptual docs under `v84-docs/readme/`.
- Hand-off documents the harness writes for an external
  implementer: `iterations/<n>/tasks.md` and `iterations/<n>/fix.md`.

## Field naming: `_id` vs `_tag`

Two suffix conventions for slug-style identifier fields:

- **`_id`** for unique instance handles. There is exactly one
  v84-1, exactly one v84-1.3, exactly one v84-1.3.frontend.1.
  Examples: `task_id`, `action_id`, `iteration_id`,
  `current_iteration` (no suffix because it stands alone).

- **`_tag`** for categorical slugs from a known enum. There are
  eight role tags total; each role has up to four reviewer tags.
  Examples: `role_tag` (`frontend`/`backend`/...), `reviewer_tag`
  (`pages`/`primitives`/...).

This is meaningful to the LLM: `role_tag: frontend` means
"frontend is one of the named role categories"; `task_id: v84-1.3`
means "v84-1.3 is the unique handle for this specific task." Two
different reading modes.

## Id formats

| Thing                 | Format                                       | Assigned by  |
|-----------------------|----------------------------------------------|--------------|
| Iteration / top-task  | `v84-N`                                      | harness      |
| Sub-task              | `v84-N.M`, `v84-N.M.K`, … (recursive)        | harness      |
| Action                | `<task_id>.<role_tag>.<n>`                   | agent (writer/patch) |
| Reviewer correction   | `v84-<iter>.<role>.<reviewer_tag>.c.<n>`     | harness      |
| Lead's own correction | `v84-<iter>.<role>.lead.c.<n>`               | harness      |
| Architect correction  | `v84-<iter>.architect.c.<n>`                 | harness      |
| Rule proposal         | `v84-<iter>.<source>.rule.<n>`               | harness      |

`<source>` is `<role_tag>` for writer, `<role_tag>.<reviewer_tag>`
for reviewer, `architect` for architect, `<role_tag>.lead` for
lead-authored. Lead-authored rule records land directly with
`status: accepted` (lead is the role's authority); writer / reviewer
raises land `pending` until the lead verdicts them.

Greppable as `[v84-N` (whole iteration), `[v84-N.M` (one sub-task),
`[v84-N.architect` (architect's contributions), etc.

## Prose fields use `|` block scalar

Every prose field uses `|` block scalar, always:

```yaml
action: |
  Add the responsive page shell to index.html — meta viewport,
  flex container, and a centred .canvas div sized via min(80vw,
  80vh) for fluid scaling.
```

Plain YAML scalars break when prose contains:
- Colons followed by a space (`(prefers-reduced-motion: no-preference)`)
- Embedded quotes
- Other YAML-special chars (`{`, `[`, `&`, `*`, `!`, `>`, `|`)

Block scalars never do — they're literal until indentation drops.

The harness has a custom YAML representer registered on
`SafeDumper` that auto-promotes any string containing `: ` or
newlines to `|` style on dump. Agents are also told via
instruction to use `|` for every prose field. Defence in depth.

## On-the-wire format: JSON

The wire format is JSON, not YAML. Every stage owns a
`<stage>.md` (prose) plus a `<stage>.schema.json` (response
shape) under `v84-docs/instructions/<group>/`.

`call_json` augments the system prompt with a `## Response
format` block built from the schema, sends
`response_format: {"type": "json_object"}`, parses with
`json.loads`, validates against the schema, and retries up to
`cfg.retries` times on parse or validation failure (sampling
fresh each retry — no echo of the bad output).

There is no marker pattern. Earlier versions used a
`====== MY RESPONSE ======` marker before a YAML body; that
worked but failed ~20% of the time as weak models broke
indentation or wandered into prose. Switching to JSON Schema with
provider-side JSON enforcement collapsed the failure rate, so the
marker is gone.

See [llm-format.md](llm-format.md) for the full wire-format
spec — schema subset supported, retry semantics, streaming
snapshots, MultiSpinner integration, log file naming.

## Instruction file pattern

Every stage is a pair: `instructions/<group>/<stem>.md` carries
the prose; `instructions/<group>/<stem>.schema.json` carries the
response shape.

The `.md` is pure prose. What the agent is, what it receives,
when to accept / reject, what to think about. No JSON examples,
no schema details, no "respond with JSON" boilerplate — that's
auto-generated from the schema.

```markdown
# <stage> — agent instruction

<one-paragraph identity statement>

## What you receive

- <message-by-message list of context the harness will inject>

## Calibrate to project scope        ← iteration stages
## Rules                             ← init stages

<iteration stages: scope discipline + project-size calibration block>
<init stages: numbered constraints the agent must respect>

## What to emit

<short description of the named fields the response carries —
high-level only; the schema and example come from the .json>
```

Iteration stages (plan, draft, review, review_validate, lead,
architect, architect_validate, patch, classify-rules) use
**Calibrate to project scope** — output should match what this
iteration is actually building, no production-scale concerns on
a demo. Init stages (suggest-roles, suggest-stack, suggest-
structure, decompose) use **Rules** — numbered list of
constraints. A stage may include both.

The `.schema.json` is standard JSON Schema with one v84-specific
convention: a top-level `examples: [{title, example}]` list. Each
title labels the situation that example covers; the harness
renders one `### <title>` block per example into the auto-built
system-prompt addendum so the model can match its situation to a
concrete shape.

This shape was tuned empirically — schema-as-source-of-truth +
titled examples + provider-side JSON enforcement had the lowest
fail rate across local LLM models (Qwen, etc.) on long-running
pipelines. Don't add fields to the agent's response unless
they're load-bearing for downstream consumers.

## File naming

- All file/dir names lowercase.
- Hyphenated for compound terms:
  `corrections-rejected.yaml`, `corrections-applied.yaml`.
- Period-separated when grouping by category +
  type: `<role>.rules.yaml`, `global.rules.yaml`,
  `<role>.<reviewer_tag>.yaml`.

YAML keys use snake_case (`task_id`, `next_step`, `for_role`).
Tag values bare (`frontend`, `pages`).

Iteration numbers are plain integers — `iterations/1/`, not
`iterations/001/`. Padding breaks past 999 and isn't worth the
visual win.

## What this rules out

- **Bespoke text formats with custom parsers.** Including the
  old-v84 `====== MY RESPONSE ======` markers IN the body
  separating sections.
- **Mixed structure + prose in one file.** A YAML record with a
  multi-line `proposal:` block scalar is fine. A markdown file
  with YAML front-matter and a structured body is not.
- **JSON on disk.** YAML wins on readability, comment support,
  and block scalars on persisted state. JSON is the wire format
  for LLM responses (because schema enforcement collapses the
  failure rate); on disk, YAML.
- **Schemaless wire format.** Every stage has an explicit
  `<stage>.schema.json`. The validator (`llm.client._validate_against_schema`)
  rejects drift after parse and triggers a retry.

## Summary

- YAML on disk, JSON Schema on the wire.
- `.md` for free-form agent prose; `<stage>.md` is paired with
  `<stage>.schema.json`.
- `_id` for unique handles, `_tag` for category slugs.
- `|` block scalar for every prose field on disk.
- Provider-side `response_format: json_object` + per-stage JSON
  Schema. No marker.
- `instructions/<group>/<stem>.{md,schema.json}` per stage.
- File names lowercase, hyphen-separated, period for category groups.
- Iteration numbers are plain integers without padding.
