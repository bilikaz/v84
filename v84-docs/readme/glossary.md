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
bundle (writer draft + lead corrections + accepted role rules),
emits cross-role corrections + global rule proposals + can reject
lead corrections that create cross-role conflict. See
[four-layer-split.md](four-layer-split.md#architect).

**architect_validate** — The cycle-end stage. Fans one call out
per active lead voting accept/reject on (1) architect-proposed
globals (single-veto across leads) and (2) architect's
cross-role corrections targeting that role (only that lead's
vote counts). Then counts pending corrections; if any → next
round at `patch` with narrowed `active_roles`, else hands off
to `user_review`. Replaces the older single-purpose `validate`
stage.

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

**Corrections** — The next round's writer's punch list. Stored at
`iterations/<n>/<role>.corrections.yaml`. Each entry carries
`id`, `verdict` (fix/missing/remove), `action_id` or
`task_id`, and `correction` prose. Sources: lead-accepted
reviewer corrections + lead's own raises (from `lead_round`),
plus lead-accepted architect cross-role corrections (from
`architect_validate`). See
[cycle-flow.md](cycle-flow.md#stage-4-lead_round).

**corrections-pending.yaml** — Staging file at
`iterations/<n>/<role>.corrections-pending.yaml` holding reviewer
corrections (from `review`) and architect cross-role corrections
(from `architect`) before the role's lead votes them into
`<role>.corrections.yaml` or `<role>.corrections-rejected.yaml`.
Cleared after `lead_round` Phase A and after `architect_validate`
Job 1.

**corrections-applied.yaml** — Audit file where patch moves
applied corrections so the next round's reviewers can verify what
was honored. See [cycle-flow.md](cycle-flow.md#stage-7-patch-round-2).

**core.yaml** — `<project>/v84/core.yaml`. The recursive task
tree + iteration pointer (`current_iteration`,
`completed_iterations`). Source of truth for "what's being built."

**Cycle** — One round of writer → reviewer → lead_round →
architect → architect_validate inside an iteration. Round 1's
first stage is draft; round 2+ starts with patch. See
[iteration-loop.md](iteration-loop.md).

**classify-rules** — LLM call inside `user_review` that
pre-buckets every accepted rule into `promote` (binds future
iterations) or `iteration_only` (one-shot scope). Result cached
at `iterations/<n>/rule_classifications.yaml`; reused on re-entry
when the accepted-id set hasn't changed. Falls back to
deterministic defaults (everything → promote) if the call fails.

**confirm_modal** — Shared yes/no slip-protection painter at
`harness/ui/confirm_modal.py`. Used in front of `review_list`
commit actions (continue / regenerate) so a stray keystroke
doesn't promote rules and close the iteration.

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

**Globals** — Rule records that apply across all roles.
Architect-emitted; pending in `iterations/<n>/global.rules.yaml`;
promoted to `<project>/v84/global.rules.yaml` at user_review.

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
corrections for the role, votes on role-scoped rule proposals,
and may author its own role-scoped corrections and rules. Runs
as two parallel LLM calls under `lead_round`: `review_validate`
(verdicts) + `lead.md` (raises). Lead's verdict on items is
provisional — accepted reviewer items stay in
`corrections-pending.yaml` and lead-blessed pending rules stay
`status: pending` until the architect's `lead_validate` makes
the final call. Lead also fires once during `architect_validate`
to vote on architect-proposed globals + architect cross-role
corrections targeting the role. See
[four-layer-split.md](four-layer-split.md#lead).

**lead_validate** — The architect's verdict half of the architect
stage. Runs in parallel with `architect.md` (the raise half),
gated to fire only when scope is non-empty. Votes `accept` /
`reject` on every lead-blessed correction in scope (id NOT
`architect.c.<m>`) and every role-scoped rule with
`status: pending` or `status: accepted`. Phase A of the
architect stage applies the verdicts: accepts move pending
items to their final binding location (corrections.yaml /
status: accepted with synth apply-correction); rejects move to
the rejected file / status: rejected with synth retracted.
Schema at `instructions/iteration/lead_validate.schema.json`.

**lead_round** — Stage that fires the lead's verdict call
(`review_validate.md`) and raise call (`lead.md`) in parallel for
every active role. Two-phase write applies verdicts (Phase A) then
raises (Phase B). Replaces the older single-call `lead` stage.

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
sub-tasks under the parent in `core.yaml`, and creates
`iterations/<n>/status.yaml` with `next_step: rules_lead` to
start the pre-pass.

**Pre-pass / Rule initial session** — Five stages between `plan`
and the per-role cycle that front-load the iteration's binding
rules: `rules_lead` (per role, fan-out) → `rules_architect`
(single, cross-role) → `rules_validate` (per lead, single-veto
on globals) → `rules_consolidate` (single, dedup over surviving
lead rules) → `user_rules_review` (review_list user gate, with
continue → start cycle or regenerate → re-run pre-pass). See
[rule-initial-session.md](rule-initial-session.md).

**rules_lead** — Pre-pass stage. Per active role, the lead
proposes 5–7 starting role-internal rules (file/folder
conventions, naming, stack-driven patterns, structural
patterns, role-internal contracts). Lead is the role's
authority — proposals land `status: accepted` immediately.
Schema at `instructions/iteration/rules_lead.schema.json`.

**rules_architect** — Pre-pass stage. Single architect call;
proposes 8–12 cross-role globals (inter-role contracts, shared
file ownership, env-var conventions, dependency conventions,
shared paths). Each may carry `promotes_from: [<lead_rule_id>...]`
to retire role-internal rules it generalises. Globals land
`status: pending`. Schema at
`instructions/iteration/rules_architect.schema.json`.

**rules_validate** — Pre-pass stage. Fan-out per active role's
lead; single-veto vote on each pending global from
`rules_architect`. Drift checks against root rules; reject when
the role's stack/layout cannot honor the global, or when a
global's `promotes_from` cited rule isn't actually subsumed.
Accepted globals retire any cited lead rules. Schema at
`instructions/iteration/rules_validate.schema.json`.

**rules_consolidate** — Pre-pass stage. Single architect call;
votes accept/reject on every surviving lead rule from
`rules_lead` against the now-settled globals. Reject when a
lead rule conflicts with a settled global, drifts from a root
rule, is subsumed by a global, or is a same-scope duplicate of
another role's lead rule. Schema at
`instructions/iteration/rules_consolidate.schema.json`.

**user_rules_review** — Pre-pass user gate. Same `review_list`
painter and `classify-rules` LLM bucket as iter-close
`user_review`. Continue → promote ticked rules to project root
+ initialise the cycle pipeline (round 1, draft). Regenerate →
promote ticked rules + clear pre-pass artifacts + reset to
`rules_lead` for another pre-pass round against the freshly
promoted root rules.

**promotes_from** — Optional field on architect-proposed
globals. List of role-internal lead-rule ids the global fully
subsumes. When the global is accepted, the cited lead rules are
retired (`status: superseded`, `superseded_by: <global_id>`)
so no duplicate survives. Set only when the global's wording
covers the lead rule's full scope; partial overlap should
propose the global as additive instead.

**superseded** — Rule status set on a role-internal record when
a cross-role global subsumes it via `promotes_from`. Carries
`superseded_by: <global_id>` for audit. Filtered out of
verdict scopes (rules_consolidate, lead_validate) and of
user-facing review lists.

**Profile** — `<project>/v84/profile.yaml`. Active roles, llm
tier endpoints + concurrency, model_tiers, loop knobs,
`project.layout_type`, and the `layout:` block (per-role + global
section paths). Read at the start of every stage.

**Proposal** — A pending rule raised by writer, reviewer, or
architect. Becomes a `text`-bearing accepted rule once the lead
(for role-scoped) or user_review (for promoted) accepts it. Lead
may also raise its OWN role-scoped proposals that settle directly
accepted (no in-iteration verdicting — lead is the role's
authority).

**Rejected by** — `rejected_by: lead | architect | <role>.lead`
field on entries in `<role>.corrections-rejected.yaml` and on
rejected globals. Distinguishes which layer rejected. The
`<role>.lead` form appears when a lead vetoes an architect global
during cross-lead validation.

**rejection_reason** — Free-form prose recorded on rejected rule
records (and on lead-rejected architect globals). Set by the
lead's verdict; surfaced to next round's architect via
`rejected_rules_block` so the architect doesn't re-propose blindly.

**Review** — Stage 3 in round 1 (and after patch in round 2+).
Per-role-per-lens parallel calls; each reviewer emits corrections
+ optional rule proposals. Round-2+ review only runs for roles
in `status.yaml`'s `active_roles` (set by `architect_validate`).

**review_validate** — The verdict half of `lead_round`. Per-role
LLM call that votes accept/reject on every pending reviewer
correction and every pending rule proposal for the role. Schema
at `instructions/iteration/review_validate.schema.json`. Runs in
parallel with the raise call (`lead.md`); the harness applies
verdicts first (Phase A) then raises (Phase B).

**review_list** — Generic painter at `harness/ui/review_list.py`.
Sectioned rows that the user can tick / drill into alternatives /
inline-edit, plus a horizontal action bar of caller-defined
commit + mutate actions. First concrete caller is
`user_review`'s rule-promotion screen. See [screens.md](screens.md#4-review_list--generic-tick--drill--edit-painter).

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

**Rule** — Durable ruling the project lives by — pattern-rules
("all DB columns use snake_case") and factual choices ("session
timeout = 30 min") alike — settled via the verdict/raise
lifecycle. Lives at `iterations/<n>/{<role>,global}.rules.yaml`
(pending / accepted / rejected) and at
`<project>/v84/{<role>,global}.rules.yaml` (post-promotion). By
definition approved; pending and rejected variants live behind
their own `pending_rules_block` / `rejected_rules_block` helpers.
See [rules.md](rules.md).

**text** — Canonical field name for the active wording of an
accepted rule. Lead emits it on accept verdicts. Used by
`_render_records` when building the rules context block. Prose
can call it "the rule's wording" — just the YAML key is `text`.

**status.yaml** — `iterations/<n>/status.yaml`. Two fields:
`round` (current round) and `next_step` (the stage that should
run next). Drives the iteration's state machine. See
[iteration-loop.md](iteration-loop.md#statusyaml-drives-everything).

**structure (init stage)** — Stage 3 of init. Single LLM call
proposes layout type + per-role section paths + (for monorepo)
a `global` section list. User reviews each scope sequentially via
field_editor. Persists to `profile.yaml` (`project.layout_type`
+ `layout:` block). Required before decompose.

**Reviewer correction** — A reviewer's single-lens critique of
an action in the writer's draft. Same shape as any correction:
`id` (`v84-<n>.<role>.<reviewer_tag>.c.<m>`), `verdict`
(fix/missing/remove), `action_id` or `task_id`, `correction`.
All reviewers' corrections for one role merge into
`iterations/<n>/<role>.corrections-pending.yaml` (no per-lens
review files anymore). The lead then votes accept/reject in
`review_validate`.

**Tag** — Iteration-anchored identifier. Source code tags (e.g.
`[v84-1.3.frontend.1]`) tie code to actions; rule ids tie rules to
their origin iteration.

**Task** — Unit of user-intent in `core.yaml`. Recursive: top-level
= iterations; nested = sub-tasks. Each carries `id` and `task`
prose.

**task_id** — Unique handle for any task in the tree. Top-level
form `v84-N`; nested form `v84-N.M`, `v84-N.M.K`, etc.

**tasks.md** — Implementation handoff document at
`iterations/<n>/tasks.md`, written by `user_review` on the
pure-accept close path. Bundles plan + roles + active rules + repo
layout + tagging convention + per-role action list. Consumed by an
external implementer (Claude Code, Cursor, human) that writes the
actual code on disk.

**user_review** — Iteration-close gate. Pre-classifies every
accepted rule via `classify-rules` (promote vs iteration-only),
then shows them via `review_list` — user ticks rules to promote,
optionally drills into alternatives, optionally inline-edits.
Two terminal commit actions: `[c] continue` (promote ticked
entries, write `tasks.md`, advance to `finish`) or `[r]
regenerate` (promote ticked entries, clear cycle artefacts, reset
to round 1 / draft). Both run through `confirm_modal` before
firing.

**Validate** — Renamed to `architect_validate` to disambiguate
from the lead's `review_validate` call. See **architect_validate**
above.

**versioning** — Opt-in archival of mutating LLM-output files.
Set `project.logging: true` in `profile.yaml` and the harness
will archive `iterations/<n>/<role>.yaml` as `<role>.yaml.<n>`
on every overwrite (round 1 draft → round 2 patch → round 3
patch, …). Implementation: `harness/core/versioning.py`.

**Verdict** — Two senses, depending on context:
- **Lead verdict** (in `review_validate`, `architect_validate`):
  accept/reject on a pending reviewer correction, pending rule
  proposal, or pending architect item.
- **Action verdict** (writer's correction shape): one of `fix` /
  `missing` / `remove` describing what to do to a draft action.
  Used by reviewers, leads, and the architect when they raise
  corrections.

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
- [rules.md](rules.md) — rule lifecycle
- [format.md](format.md) — naming + YAML conventions
- [comparison.md](comparison.md) — vs spec-kit / OpenSpec
