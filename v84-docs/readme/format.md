# Format

> YAML for everything structured. Markdown only for free-form
> agent prose under `instructions/`. Tight rules on naming, ids,
> and prose fields keep parsing trivial.

## YAML by default

Every file under `<project>/v84/` is YAML. No bespoke text
formats. No mixed structure + prose files. Parsing is `yaml.safe_load`
end-to-end.

Markdown only in two places:
- Agent system prompts under `v84-docs/instructions/`.
- These conceptual docs under `v84-docs/readme/`.

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
| Suggestion            | `v84-<iter>.<role>.<reviewer_tag>.s.<n>`     | harness      |
| Lead's own correction | `v84-<iter>.<role>.lead.c.<n>`               | harness      |
| Architect correction  | `v84-<iter>.architect.c.<n>`                 | harness      |
| Convention proposal   | `v84-<iter>.<source>.{conv}.<n>`             | harness      |
| Decision proposal     | `v84-<iter>.<source>.{dec}.<n>`              | harness      |

`<source>` is `<role_tag>` for writer, `<role_tag>.<reviewer_tag>`
for reviewer, `architect` for architect, `<role_tag>.lead` for
lead-authored. Lead-authored conv/dec records land directly with
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

## The marker pattern

Every agent's system prompt ends with:

```
When finished, the **first non-thinking line** must be exactly:

====== MY RESPONSE ======

[then the YAML response]
```

Why:
- Reasoning models (Qwen3, DeepSeek-R1, etc.) emit
  `<think>…</think>` blocks. The marker sits after thinking so we
  can find it after stripping.
- The marker is load-bearing: `llm.client.call` looks for it and
  retries on absence.
- "First non-thinking line" handles all reasoning conventions
  (including ones that don't use `<think>` tags).

Six equals signs each side, single spaces. Do not vary.

## Instruction file pattern

Every `instructions/**/*.md` follows the same shape:

```markdown
# <stage> — agent instruction

<one-paragraph identity statement>

## What you receive

- <message-by-message list of context the harness will inject>

## Calibrate to project scope        ← iteration stages
## Rules                             ← init stages

<iteration stages: scope discipline + project-size calibration block>
<init stages: numbered constraints the agent must respect>

Iteration stages (plan, draft, review, lead, architect, patch) use
**Calibrate to project scope** — output should match what this
iteration is actually building, no production-scale concerns on a
demo. Init stages (suggest-roles, suggest-stack, decompose) use
**Rules** — numbered list of constraints (prefer fewer roles, use
only the fields you're given, no tech choices in tasks, etc.).
A stage may also include both: an iteration stage with hard
procedural constraints (patch's mechanical apply rules) carries
**Rules** alongside **Calibrate**.

## Output Format

**Think as long as you need before submitting.** Use the thinking
phase to <stage-specific guidance>. Longer thinking is fine —
longer *response* is not.

When finished, the **first non-thinking line** must be exactly:

====== MY RESPONSE ======

After the marker emit **valid YAML** with up to <N> top-level
fields. <stage-specific guidance>

- `field_one`: <semantic + schema>
- `field_two`: <semantic + schema>

**Every prose field uses `|` block scalar.** That covers ...

### Output Example

[concrete YAML example]
```

This shape was tuned empirically — the marker rule + literal
example template + per-field combined-purpose-and-schema
descriptions had the lowest fail rate across local LLM models
(Qwen, etc.) on long-running pipelines. Don't add fields to the
agent's response unless they're load-bearing for downstream
consumers.

## File naming

- All file/dir names lowercase.
- Hyphenated for compound terms:
  `corrections-rejected.yaml`, `corrections-applied.yaml`.
- Period-separated when grouping by category +
  type: `<role>.conventions.yaml`, `global.decisions.yaml`,
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
- **JSON instead of YAML.** YAML wins on readability, comment
  support, and block scalars. JSON is fine for wire formats; on
  disk, YAML.
- **Schemaless YAML.** Every YAML file type has an implicit schema
  defined by the agent instruction + harness parser. Drift gets
  caught at `_parse` time and the harness raises.

## Summary

- YAML for structure, `.md` for free-form agent prose.
- `_id` for unique handles, `_tag` for category slugs.
- `|` block scalar for every prose field.
- Marker `====== MY RESPONSE ======` on every agent response.
- `instructions/**/*.md` follows the same five-section template.
- File names lowercase, hyphen-separated, period for category groups.
- Iteration numbers are plain integers without padding.
