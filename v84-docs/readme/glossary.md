# Glossary

Alphabetical reference. Cross-referenced.

---

**Action** — One file-level change a writer drafts. Carries an
`id` (`<task_id>.<role_tag>.<n>`), `action` prose, `files`,
optional `depends`. Lives in `iterations/<n>/<role>.yaml`. See
[concepts.md](concepts.md#actions-are-concrete-file-level-work).

**action_id** — Unique handle for an action. Format
`<task_id>.<role_tag>.<n>`, e.g. `v84-1.3.frontend.1`. Encodes
the parent task and role; greppable in source tags.

**Architect** — Single agent, cross-role. Reads every active role's
bundle (writer draft + lead corrections + accepted role conv/dec),
emits cross-role corrections + global conv/dec proposals + can
reject lead corrections that create cross-role conflict. See
[four-layer-split.md](four-layer-split.md#architect).

**Brief** — User's original project description. Cached as
`<project>/v84/brief.md` during init; deleted after decompose
since the task list takes over as source of truth.

**Cache** — Per-iteration disk cache of rendered context blocks.
Lives at `iterations/<n>/cache/<func>.<role>.md`. Each file holds
the rendered markdown for one builder + role; mtime-keyed against
source files for invalidation. Used by writer/patch/review/lead
to skip re-rendering and to inspect "what each stage sent the
LLM." See [core/cache.py].

**Cascade effect** — When adding one thing to a system raises
questions elsewhere. The reason for the round-based loop. See
[iteration-loop.md](iteration-loop.md#why-a-loop).

**Challenge** — The single question a reviewer holds in mind while
reading every action in the writer's draft. One field per reviewer
in the role template. See [roles.md](roles.md#per-role-anatomy).

**Convention** — A durable rule applying across this and future
iterations. Lives at `iterations/<n>/{role,global}.conventions.yaml`
(pending / accepted / rejected) and at
`<project>/v84/{role,global}.conventions.yaml` (post-promotion).
By definition approved; pending and rejected variants live behind
their own `pending_conventions_block` / `rejected_conventions_block`
helpers. See
[conventions-and-decisions.md](conventions-and-decisions.md).

**Corrections** — Lead's punch list for the next round's writer.
Stored at `iterations/<n>/<role>.corrections.yaml`. Each entry
carries `id`, `verdict` (fix/missing/remove), `action_id` or
`task_id`, and `correction` prose. Architect appends cross-role
corrections to the same file. See
[cycle-flow.md](cycle-flow.md#stage-4-lead).

**corrections-applied.yaml** — Audit file where patch moves
applied corrections so the next round's reviewers can verify what
was honored. See [cycle-flow.md](cycle-flow.md#stage-7-patch-round-2).

**core.yaml** — `<project>/v84/core.yaml`. The recursive task
tree + iteration pointer (`current_iteration`,
`completed_iterations`). Source of truth for "what's being built."

**Cycle** — One round of writer → reviewer → lead → architect →
validate inside an iteration. Round 1's first stage is draft;
round 2+ starts with patch. See
[iteration-loop.md](iteration-loop.md).

**Decision** — A one-shot ruling for this iteration only. Same
shape and lifecycle as conventions. See
[conventions-and-decisions.md](conventions-and-decisions.md).

**Documentation** — Per-role implementation history at
`<project>/v84/documentation/<role>.yaml`. Appended on each
successful iteration close (by `finish` after verification).
Iteration → sub-tasks → actions, with parent task prose. Read by
writer / patch / review / lead via `role_history_block`.

**Draft** — Round-1 writer stage. Per-role parallel call; writes
each role's actions list. Round 2+ writers are the patch stage
instead.

**finish** — Iteration verification + close stage. Runs after
`user_review`'s pure-accept path. Checks every action's `files:`
exist on disk AND carry an owning action's tag (aggregator-aware).
On gaps → writes `iterations/<n>/fix.md`, stays at `next_step:
finish` for re-run. On pass → appends to documentation/<role>.yaml,
moves parent_id to `completed_iterations`, advances next_step →
done.

**fix.md** — Punch list emitted by the `finish` stage when file
verification fails. Lives at `iterations/<n>/fix.md`; lists each
gap by action (`missing` or `untagged`) for the external
implementer's next pass. Cleared automatically on a successful
pristine pass.

**for_role** — Field on architect's missing-type corrections —
required because `task_id` alone doesn't encode role. The
harness uses it to route the architect's correction into the
right role's `corrections.yaml`.

**global (in layout)** — Sibling key to roles in `profile.yaml`'s
`layout:` block, holding project-wide root files (workspace
manifest, root package.json, root configs). Required for
`monorepo` layout type; AI proposes it during the structure
stage. Renders first in `project_layout_block`. Not a real role
(no writer/reviewer/lead).

**for_role** — Field on architect's missing-type corrections —
required because `task_id` alone doesn't encode role. The
harness uses it to route the architect's correction into the
right role's `corrections.yaml`.

**Globals** — Convention or decision records that apply across
all roles. Architect-emitted; pending in
`iterations/<n>/global.{conventions,decisions}.yaml`; promoted
to `<project>/v84/global.{conventions,decisions}.yaml` at user_review.

**id** — See [format.md#id-formats](format.md#id-formats) for the
table of every id format.

**Iteration** — One top-level task in `core.yaml`, executed via
the cycle. Numbered with plain integers (`v84-1`, `v84-2`, ...).
The unit of work in v84.

**iteration_id** — Identifier for one iteration. Same as the
top-level task id (`v84-1`, `v84-2`, ...).

**Layout** — Repo layout chosen at init by the `structure` stage.
`profile.yaml` carries `project.layout_type` (`monorepo` /
`single-app` / `flat` / `scripts`) and a `layout:` block keyed by
`global` (when present) and each active role, listing
`{name, path, notes?}` sections. Read by writer/patch/review/lead
via `cached_layout_block(role)`; read project-wide by decompose,
architect, and handoff via `project_layout_block`.

**Lead** — One agent per active role. Synthesises every reviewer's
suggestions for the role, sets role-scoped conv/dec verdicts,
and may author its own role-scoped conv/dec via
`needs_convention` / `needs_decision` (settle directly accepted —
lead is the role's authority). Output goes to
`<role>.corrections.yaml`, `<role>.corrections-rejected.yaml`,
and updates statuses in `<role>.{conventions,decisions}.yaml`.
See [four-layer-split.md](four-layer-split.md#lead).

**Marker** — `====== MY RESPONSE ======`. Required first
non-thinking line in every agent response. The parser strips
thinking and looks for this. See [format.md](format.md#the-marker-pattern).

**max_concurrency** — Per-LLM-tier cap on in-flight calls. Set in
`profile.yaml`'s `llm.<tier>.max_concurrency`. Single tier defaults
to 1, multi to 4. Used by `call_many` for fan-out stages.

**Patch** — Round 2+ writer stage. Reads existing draft +
corrections, emits patched actions list. Ids of surviving actions
preserved; new ids continue per-task numbering. Moves applied
corrections to `<role>.corrections-applied.yaml`. See
[cycle-flow.md](cycle-flow.md#stage-7-patch-round-2).

**Plan** — First iteration stage. Decomposes the iteration's task
into sub-tasks, optionally asks clarifying questions, writes
sub-tasks under the parent in `core.yaml` and creates
`iterations/<n>/status.yaml` to start the cycle.

**Profile** — `<project>/v84/profile.yaml`. Active roles, llm
tier endpoints + concurrency, model_tiers, loop knobs,
`project.layout_type`, and the `layout:` block (per-role + global
section paths). Read at the start of every stage.

**Proposal** — A pending convention or decision raised by writer,
reviewer, or architect. Becomes a `rule` once the lead (for
role-scoped) or user_review (for promoted) accepts it. Lead may
also raise its OWN role-scoped proposals that settle directly
accepted (no in-iteration verdicting — lead is the role's
authority).

**Rejected by** — `rejected_by: lead | architect | <role>.lead`
field on entries in `<role>.corrections-rejected.yaml` and on
rejected globals. Distinguishes which layer rejected. The
`<role>.lead` form appears when a lead vetoes an architect global
during cross-lead validation.

**rejection_reason** — Free-form prose recorded on rejected
conv/dec records (and on lead-rejected architect globals). Set
by the lead's verdict; surfaced to next round's architect via
`rejected_conventions_block` / `rejected_decisions_block` so the
architect doesn't re-propose blindly.

**Review** — Stage 3 in round 1 (and after patch in round 2+).
Per-role-per-lens parallel calls; each reviewer emits suggestions
+ optional convention/decision proposals.

**role_history_block** — Context block read by writer / patch /
reviewer / lead, rendered from `documentation/<role>.yaml`. Shows
every action this role has shipped in past iterations (grouped by
iteration → sub-task → action). Empty on first iteration. Lets
agents build on top of prior work without redoing it.

**Reviewer** — One agent per (role, lens). Four lenses per role
by default. Each holds one `challenge` question while reading the
role's writer draft and emits single-lens suggestions.

**reviewer_tag** — The lens slug within a role (`pages`,
`primitives`, `entities`, etc.). Categorical; from the role's
template.

**role_tag** — The role slug (`frontend`, `backend`, …). The
eight ship in `init/roles/`; project activates a subset.

**Round** — One pass through the cycle. Round 1 = draft → review
→ lead → architect → validate. Round 2+ = patch → review → lead
→ architect → validate. Round counter ticks at the validate→patch
transition.

**rule** — Canonical field name for the active text of an accepted
convention or decision. Lead emits it on accept verdicts. Used by
`_render_records` when building the conventions/decisions context
block.

**status.yaml** — `iterations/<n>/status.yaml`. Two fields:
`round` (current round) and `next_step` (the stage that should
run next). Drives the iteration's state machine. See
[iteration-loop.md](iteration-loop.md#statusyaml-drives-everything).

**structure (init stage)** — Stage 3 of init. Single LLM call
proposes layout type + per-role section paths + (for monorepo)
a `global` section list. User reviews each scope sequentially via
field_editor. Persists to `profile.yaml` (`project.layout_type`
+ `layout:` block). Required before decompose.

**Suggestion** — A reviewer's single-lens critique of an action
in the writer's draft. Fields: `id`, `verdict` (fix/missing/remove),
`action_id` or `task_id`, `suggestion`. Lives at
`iterations/<n>/reviews/<role>.<reviewer_tag>.yaml`.

**suggestion_verdicts** — Lead's accept/reject decisions per
reviewer suggestion. Drives what becomes a correction (accepted
ones) vs what gets logged for audit (rejected ones).

**Tag** — Iteration-anchored identifier. Source code tags (e.g.
`[v84-1.3.frontend.1]`) tie code to actions; convention/decision
ids tie rules to their origin iteration.

**Task** — Unit of user-intent in `core.yaml`. Recursive: top-level
= iterations; nested = sub-tasks. Each carries `id` and `task`
prose.

**task_id** — Unique handle for any task in the tree. Top-level
form `v84-N`; nested form `v84-N.M`, `v84-N.M.K`, etc.

**tasks.md** — Implementation handoff document at
`iterations/<n>/tasks.md`, written by `user_review` on the
pure-accept close path. Bundles plan + roles + active conv/dec +
repo layout + tagging convention + per-role action list.
Consumed by an external implementer (Claude Code, Cursor, human)
that writes the actual code on disk.

**user_review** — Iteration-close gate. Walks accepted conv/dec
via `field_editor`; user keeps / picks alternative / writes
custom / declines. Every non-declined entry promotes to
`<project>/v84/{role,global}.{conventions,decisions}.yaml`. If
any KEPT rule's text changed → `_restart_cycle` resets to
`{round: 1, next_step: draft}`. Otherwise → writes `tasks.md`
handoff, advances to `next_step: finish`.

**Validate** — Cycle-end stage. Two jobs: (1) cross-lead
validation of architect's pending globals (fan-out per active
lead, single-veto, captures `rejection_reason`), (2) counts
pending corrections across roles. Pending → next cycle (round++,
next_step=patch); empty → next_step=user_review.

**Verdict** — Lead's accept/reject decision on a suggestion or
proposal. Architect's `verdict` semantics differ — it's an action-
verdict (fix/missing/remove) on its own corrections.

**v84** — The project, as a system. Spelled `v84` (lowercase, no
dot). Tag prefix in source code: `[v84-N.M.role.K]`.

**Writer** — One agent per active role. Drafts (round 1) or
patches (round 2+) the role's actions list. Sees only its own
role's surface. See [four-layer-split.md](four-layer-split.md#writer).

---

## See also

- [concepts.md](concepts.md) — the core model
- [structure.md](structure.md) — folder layout
- [four-layer-split.md](four-layer-split.md) — layer responsibilities
- [iteration-loop.md](iteration-loop.md) — round mechanics
- [cycle-flow.md](cycle-flow.md) — per-stage walkthrough
- [init-flow.md](init-flow.md) — first-run walkthrough
- [roles.md](roles.md) — the eight role templates
- [conventions-and-decisions.md](conventions-and-decisions.md) — rule lifecycle
- [format.md](format.md) — naming + YAML conventions
- [comparison.md](comparison.md) — vs spec-kit / OpenSpec
