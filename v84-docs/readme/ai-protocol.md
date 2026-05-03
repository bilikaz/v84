# AI Integration Protocol

> **Status: forward-looking design — not yet implemented.** The
> `--ai` and `--answer` flags described below do NOT exist on
> `v84.py` today. The current `v84.py` has `--auto` (skip
> confirmations), `--start` (skip menu), `--call` (direct
> dispatch) and `--force` (re-run a specific stage), but no
> file-based question/answer surface. Treat this doc as the
> design we'd implement when a non-TTY orchestrator concretely
> needs to drive v84; the section below is the proposed shape,
> not current behaviour.

> File-based question/answer protocol for non-TTY orchestration of
> v84. Any agent that can read/write JSON can drive the harness —
> a Telegram bot relaying questions to a chat, an OpenClaw skill,
> a CI runner, a Python script, a person editing JSON in a text
> editor.

## Why a protocol

v84 is heavily UI-driven (menu pickers, field editors, checklists,
text input). Those UIs assume a TTY. To let an external agent
drive v84 — Forward each question to a Telegram chat, post it to
Slack, hand it to OpenClaw's chat layer, route it through any
multi-step automation — the harness needs to publish its
questions as data and accept answers as data.

The protocol below is that bridge. One flag (`--ai`), one
question-and-answer file pair, five question kinds. Any agent
that handles those five kinds can drive any v84 stage that asks
for input.

## Activating

Two invocations:

```bash
python3 v84.py --ai            # start / resume; emit question + exit 42 when input needed
python3 v84.py --ai --answer   # consume pending answer.json, then continue as --ai
```

`--ai` swaps every interactive UI primitive (`single_select`,
`checklist`, `field_editor`, `detail_list`, `text_input`) to
file-protocol mode. Stages that don't need UI input (draft,
review, lead, architect, validate, patch, finish) run as normal
until they hit a stage that does.

`--ai` also **bypasses the main menu and the manage_rules action**
— those are TTY-only conveniences for interactive sessions.
Pipeline stages (init + iteration cycle + finish) are the only
things AI orchestrators need; menu management can stay
human-only.

`--answer` tells the harness "I wrote `answer.json` since you
last exited; consume it before continuing." Without `--answer`,
a pending answer.json is ignored — the harness will simply
re-emit the same `question.json` and exit again. This makes
`--ai` idempotent (you can re-run it to inspect "what's pending"
without progressing) and `--answer` explicit (the orchestrator
must opt-in to advancing the pipeline).

## Exit codes

| Code | Meaning | What's on disk |
|------|---------|----------------|
| `0` | Pipeline complete OR ready for next iteration cycle (no question pending) | last stdout event has `phase: done` (or no events) |
| `42` | Waiting for an answer | `question.json` present; last stdout event has `phase: waiting` + `question_id` |
| `1` | Fatal error | last stdout event has `phase: error` + `message`; full traceback on stderr |
| `130` | User cancelled (Ctrl-C in interactive use only — not relevant for AI orchestration) | — |

## File locations

Two files under `<project>/v84/.ai/`:

```
<project>/v84/.ai/
├── question.json    ← harness writes when input is needed; consumed on next --answer
└── answer.json      ← orchestrator writes in response; consumed by harness
```

Path is fixed. The `.ai/` directory is created automatically by
the harness when `--ai` is passed.

There is **no `state.json` file**. State is conveyed by exit code
and the presence/absence of `question.json`:

- exit `0` + no `question.json` → done
- exit `42` + `question.json` present → waiting for an answer
- exit `1` → error (details on stderr; optionally on stdout
  via the NDJSON stream — see below)

Optional progress visibility comes from stdout (see "Status
events on stdout" below) — but it's purely informational. The
authoritative signal is exit code + question.json.

## Lifecycle (exit / restart per question)

The harness does NOT stay alive between questions. Every time it
needs input, it writes `question.json` and exits 42. The
orchestrator decides, writes `answer.json`, and re-launches the
harness with `--answer`. This cycle repeats until the harness
exits 0 (done).

Why exit/restart instead of a long-running daemon:
- No race conditions — harness only reads `answer.json` after the
  orchestrator explicitly says (via `--answer`) that it's ready.
- No file-lock issues — exclusive writer at any moment.
- Crash-safe — every restart resumes from disk state. The
  in-flight question persists between exits via `question.json`.
- Natural fit for chat-triggered orchestration — user message →
  one v84 invocation → response. No daemon to keep alive.

## Status events on stdout (NDJSON)

While the harness is running, it emits one JSON line per status
change to stdout — newline-delimited JSON (NDJSON). The
orchestrator captures stdout if it cares about live progress;
consumers that just want the final state read **the last line**
of stdout (most recent status wins).

Each event line is a self-contained snapshot:

```json
{"phase": "running",  "stage": "draft",     "iteration": 1, "round": 1, "detail": "drafting frontend (parallel)"}
{"phase": "running",  "stage": "draft",     "iteration": 1, "round": 1, "detail": "drafting backend (parallel)"}
{"phase": "running",  "stage": "review",    "iteration": 1, "round": 1, "detail": "reviewing 16 (role × lens)"}
{"phase": "running",  "stage": "lead",      "iteration": 1, "round": 1, "detail": "leading 4 role(s)"}
{"phase": "running",  "stage": "structure", "iteration": null, "detail": "AI proposing layout..."}
{"phase": "waiting",  "stage": "structure", "iteration": null, "question_id": "01HV..."}
```

On exit:
- exit `0` — last line has `"phase": "done"` (or no events at all,
  if the invocation was a no-op)
- exit `42` — last line has `"phase": "waiting"` and a
  `question_id` matching the on-disk `question.json`
- exit `1` — last line has `"phase": "error"` and a `message`

### Phase semantics

- **`running`** — harness is actively working (between status
  events). Purely informational; the orchestrator doesn't need
  to act.
- **`waiting`** — harness exited 42. `question.json` is on disk.
  Read it, decide an answer, write `answer.json` atomically,
  re-launch with `--answer`.
- **`done`** — harness exited 0. No more questions in this
  invocation. The pipeline is complete OR ready for the next
  iteration cycle (re-launching with `--ai` would either return 0
  again or start the next cycle).
- **`error`** — harness exited 1 with a fatal error. The `message`
  field carries a one-line summary; full traceback (if any)
  remains on stderr. The pipeline can be re-run after the issue
  is addressed.

### Stdout vs stderr

- **stdout** carries the NDJSON event stream — clean, parseable,
  newline-delimited.
- **stderr** carries the existing human-readable progress lines
  (spinner output, multi-call progress, file-write confirmations).
  Orchestrators may ignore stderr or redirect it to a log file.

If the orchestrator only cares about the final state:
```bash
last=$(python3 v84.py --ai --dir /proj | tail -n 1)
phase=$(echo "$last" | jq -r .phase)
```

If it wants live progress (e.g. forwarding to chat as the cycle
progresses):
```python
proc = subprocess.Popen(["python3", "v84.py", "--ai", "--dir", "/proj"],
                        stdout=subprocess.PIPE, text=True)
for line in proc.stdout:
    event = json.loads(line)
    forward_to_chat(event)
proc.wait()
```

## The question protocol

When the harness needs input, it writes `question.json` and waits.
Every question carries:

```json
{
  "v84_protocol": "1",
  "id": "ulid-or-uuid",
  "kind": "single_select" | "checklist" | "field_editor" | "detail_list" | "text_input",
  "stage": "structure",
  "iteration": 1,
  "intent": "one-line summary of what answering this affects",
  "prompt": "the harness's user-facing prompt line",
  "summary": "multi-line context, may be empty",
  "data": { ... kind-specific payload ... }
}
```

- **`id`** — unique per question. Echo it back in `answer.json` so
  the harness can verify "this answer is for the question I asked"
  and reject stale answers.
- **`stage`** — which v84 stage is asking. Useful for routing
  (e.g. forward `user_review` questions to the human-in-the-loop;
  auto-accept `plan` questions on subsequent iterations).
- **`intent`** — single sentence explaining what the answer
  decides. Lets a Telegram-bot orchestrator forward "Pick a path
  for `frontend/app` — lands in profile.yaml's layout." instead
  of just dumping the raw JSON.
- **`prompt`** — the human prompt the harness would have shown
  on a TTY.
- **`summary`** — additional multi-line context (often empty).
  When non-empty, render verbatim above the choice.

Answers must echo `v84_protocol`, `id`, and `kind`, plus carry
the kind-specific answer payload:

```json
{
  "v84_protocol": "1",
  "id": "<echoed from question>",
  "kind": "<echoed from question>",
  "data": { ... kind-specific answer ... }
}
```

If the orchestrator wants to cancel (equivalent to ESC in the
TTY), it writes `{"data": null}`. The harness raises a
cancellation error, emits a final `phase: error` event on stdout,
and exits 1.

## Question kinds

### `single_select`

Pick exactly one option from a list, or type a custom string.
Equivalent of `ui.single_select`.

**Question `data`:**
```json
{
  "options": [
    {"name": "start", "label": "Start / resume", "info": "run the next pending stage"},
    {"name": "manage_rules", "label": "Manage rules", "info": "review/edit project rules"},
    {"name": "quit", "label": "Quit", "info": "exit"}
  ],
  "preselected": "start",
  "allow_custom": false
}
```

Header rows (visual grouping) appear as `{"kind": "header", "title": "..."}` items in `options`. Skip them when picking.

**Answer `data`:**
```json
{
  "name": "start"
}
```

For `allow_custom: true` and a custom value:
```json
{
  "name": "__custom__",
  "custom_value": "free-text the orchestrator typed"
}
```

### `checklist`

Pick zero or more items from a list. Equivalent of
`ui.checklist`. Used for `roles` stage.

**Question `data`:**
```json
{
  "items": [
    {"name": "frontend", "label": "Frontend", "info": "..."},
    {"name": "backend", "label": "Backend", "info": "..."},
    {"name": "devops", "label": "DevOps", "info": "..."}
  ],
  "preselected": ["frontend", "backend"]
}
```

**Answer `data`:**
```json
{
  "selected": ["frontend", "backend", "devops"]
}
```

### `field_editor`

Walk through fields grouped in sections. For each field: keep
the value, pick an alternative, type custom, or skip (when
optional). Equivalent of `ui.field_editor`. Used for `stack`,
`structure`, `user_review`, manage-rules edit.

**Question `data`:**
```json
{
  "sections": [
    {
      "title": "Frontend",
      "fields": [
        {
          "id": "frontend.app",
          "label": "app",
          "value": "apps/web",
          "recommendation": "apps/web",
          "alternatives": [],
          "optional": true,
          "skip_label": "drop this section",
          "custom_label": "type a custom path"
        },
        {
          "id": "frontend.pages",
          "label": "pages",
          "value": "apps/web/src/pages",
          "recommendation": "apps/web/src/pages",
          "alternatives": [],
          "optional": true
        }
      ]
    }
  ]
}
```

`id` is the harness-assigned stable handle for the field.
`alternatives` lists picker options other than the recommendation.
`optional: true` means the orchestrator may answer with `none`
(skip / drop).

**Answer `data`:**
```json
{
  "fields": [
    {"id": "frontend.app", "value": "apps/web"},
    {"id": "frontend.pages", "value": "apps/web/src/pages"}
  ]
}
```

Each field's `value`:
- A string equal to `recommendation` → keep as-is
- A string equal to one of `alternatives` → pick that alternative
- The literal string `"none"` (only valid when `optional: true`)
  → skip this field
- Any other string → custom value (treated as if user typed it)

Fields not echoed in the answer are treated as kept-unchanged.

### `detail_list`

Walk through items with toggleable details, finish by picking an
action. Equivalent of `ui.detail_list`. Used for the `decompose`
revise loop.

**Question `data`:**
```json
{
  "items": [
    {"label": "v84-1: Scaffold the monorepo shell...", "detail": "full task prose..."},
    {"label": "v84-2: Add user registration...", "detail": "full task prose..."}
  ],
  "actions": [
    {"name": "accept", "label": "Accept", "info": "settle the plan as-is"},
    {"name": "revise", "label": "Revise", "info": "type a comment, regenerate"}
  ],
  "item_hint": "more details"
}
```

**Answer `data`** — the `action` value must echo one of the
question's `actions[].name`. Some actions carry extra fields:

```json
{"action": "accept"}
```
```json
{"action": "revise", "comment": "Group auth back+front into one task"}
```

When the chosen action is `revise` (or any "recycle" action), the
harness re-runs the stage's LLM call with the answer's payload
folded in, then emits a NEW question (new `id`) with the revised
output. The orchestrator answers again. Loop until an action like
`accept` commits the result.

This is the recycle pattern — see "One question per invocation"
above.

### `text_input`

Multi-line text entry. Equivalent of `ui.text_input`. Used for
custom field values, decompose revise comments, free-form briefs.

**Question `data`:**
```json
{
  "hint": "press Enter on empty line to confirm, ESC to cancel"
}
```

**Answer `data`:**
```json
{
  "text": "the orchestrator's free-form input"
}
```

## Atomic writes

The orchestrator MUST write `answer.json` atomically — write to
`answer.json.tmp` first, then rename to `answer.json`:

```python
tmp = ai_dir / "answer.json.tmp"
tmp.write_text(json.dumps(answer))
tmp.rename(ai_dir / "answer.json")   # POSIX-atomic rename
```

This guarantees the harness (on the next `--answer` invocation)
either sees no answer.json (file rename hasn't happened yet — the
orchestrator should not have re-launched yet) or a fully-formed
answer.json. Never a half-written file.

Same rule applies to the harness writing `question.json` (it
does so internally via the same rename pattern).

## One question per invocation

Every stage emits AT MOST ONE question per harness invocation.
No multi-pause stages, no progress checkpoint files, no internal
mid-stage state to thread between exits.

Two patterns to handle stages that conceptually want multiple
questions:

### Pattern 1 — fold into a single field_editor

A stage that historically asked N sub-questions (one per role, or
one per field) packs all the data into a single `field_editor`
question with N sections. The orchestrator answers all sections
in one shot.

Example: `structure` doesn't ask per-role sequentially. It emits
ONE question with sections for `global` + each active role; each
section's fields are that scope's section paths. Orchestrator
returns one answer covering every field across every section.
Harness commits, advances, done.

### Pattern 2 — loop in the orchestrator (recycle via answer)

A stage that needs to iterate (re-call the LLM with new input,
re-prompt the user) puts the loop in the orchestrator's re-launch
cycle. The answer carries a discriminator field — `action` —
that tells the harness either "commit" or "recycle with this
input."

Example: `decompose`'s revise loop. The harness emits one
`detail_list` question showing the proposed task list and
offering two actions:

```json
{
  "kind": "detail_list",
  "stage": "decompose",
  "data": {
    "items": [{"label": "v84-1: ...", "detail": "..."}],
    "actions": [
      {"name": "accept", "label": "Accept the plan"},
      {"name": "revise", "label": "Revise with a comment"}
    ]
  }
}
```

Orchestrator's answer is one of:

```json
{"data": {"action": "accept"}}
```
or
```json
{"data": {"action": "revise", "comment": "Group auth back+front..."}}
```

On `accept` → commit core.yaml, advance, exit 0.
On `revise` → harness re-calls the LLM with the comment appended
to its input, emits a NEW question (new id) with the revised
plan, exits 42. The orchestrator decides again. Loop continues
until `accept`.

The harness MAY persist minimal stage-scoped state to drive the
loop (e.g. accumulated revise comments) in
`<project>/v84/iterations/<n>/<stage>_state.json` or similar —
this is internal to the stage and not part of the protocol the
orchestrator sees. Each question/answer cycle remains atomic
from the orchestrator's view.

### Action field convention

When a question's data carries an `actions` list (typical for
`detail_list` and any future "review-or-recycle" UI), the
answer's `data.action` must echo one of those `name` values.
Additional fields (like `comment` for revise) are answer-shape
specifics documented per question kind.

### Why this matters

Single-question-per-invocation keeps:
- The protocol surface tiny (no progress files, no mid-stage
  state visible to the orchestrator)
- Each invocation atomic (write answer → re-launch → exit)
- Recycle flows transparent to the orchestrator (just answer
  again with the next question's content)
- The harness side simple (no checkpoint loading, no resume
  logic — every stage call is a fresh run that either commits
  or asks)

## Orchestrator skeleton

```python
import subprocess, json
from pathlib import Path

ai_dir = Path("/path/to/project/v84/.ai")

def write_answer(question, answer_data):
    """Atomically write answer.json with the right id."""
    tmp = ai_dir / "answer.json.tmp"
    tmp.write_text(json.dumps({
        "v84_protocol": "1",
        "id": question["id"],
        "kind": question["kind"],
        "data": answer_data,
    }))
    tmp.rename(ai_dir / "answer.json")

def my_decide(question):
    """Forward to chat / LLM / human / static policy."""
    # ... your integration logic here ...
    return { ... kind-specific answer payload ... }

# Initial launch
flags = ["--ai"]
while True:
    proc = subprocess.run(
        ["python3", "v84-docs/harness/v84.py", "--dir", "/proj"] + flags,
        capture_output=True, text=True,
    )
    rc = proc.returncode
    last_event = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "{}"
    last = json.loads(last_event)

    if rc == 0:
        break  # done — no more questions
    if rc != 42:
        raise RuntimeError(f"v84 error: {last.get('message', proc.stderr)}")

    # rc == 42 → answer the question, then continue with --answer
    q = json.loads((ai_dir / "question.json").read_text())
    write_answer(q, my_decide(q))
    flags = ["--ai", "--answer"]
```

`my_decide(q)` is where the orchestrator's smarts live. It might:
- Forward to a Telegram chat and wait for the user
- Call an LLM with the question + project state and accept its
  decision
- Apply a static policy ("on `roles` always pick the AI's
  suggestion as-is")
- Defer to a stored answer cache from a prior run

The harness doesn't care. It just needs a syntactically valid
answer of the right kind for the question's `id`.

## Error handling

**Malformed answer:** harness writes a new `question.json` with
the same `id`, `kind: "error"`, and `data: {"reason": "..."}`. The
orchestrator should re-derive a valid answer.

**Stale answer (id mismatch):** harness deletes it silently and
keeps waiting.

**Cancel:** orchestrator writes `{"data": null}`. Harness emits
a final `phase: error` event on stdout and exits 1.

**Harness crash:** last stdout event has `phase: error` with a
`message` (full traceback on stderr). No `question.json` written
on disk. Orchestrator surfaces the error and lets the user re-run.

## Example end-to-end exchange

Stage: `roles` (the first init stage).

1. **Orchestrator launches** `python3 v84.py --ai --dir /proj`.
   Harness runs the roles stage's AI-propose call, then needs
   the user to confirm. Writes `question.json`:
   ```json
   {
     "v84_protocol": "1",
     "id": "01HV...",
     "kind": "checklist",
     "stage": "roles",
     "intent": "Choose which roles ship in this project",
     "prompt": "Select active roles:",
     "summary": "AI suggests: Frontend, Backend, DevOps based on the brief.",
     "data": {
       "items": [
         {"name": "frontend", "label": "Frontend", "info": "..."},
         {"name": "backend", "label": "Backend", "info": "..."},
         {"name": "mobile", "label": "Mobile", "info": "..."},
         {"name": "devops", "label": "DevOps", "info": "..."}
       ],
       "preselected": ["frontend", "backend", "devops"]
     }
   }
   ```
   Emits a final `{"phase": "waiting", "stage": "roles", "question_id": "01HV..."}`
   line to stdout. **Exits 42.**

2. **Orchestrator sees rc=42**, reads `question.json`, forwards
   to wherever (Telegram chat, Slack, OpenClaw, terminal user,
   own LLM, static policy). Gets back a decision.

3. **Orchestrator writes `answer.json` atomically:**
   ```json
   {
     "v84_protocol": "1",
     "id": "01HV...",
     "kind": "checklist",
     "data": {"selected": ["frontend", "backend", "devops"]}
   }
   ```
   Via `tmp.rename()` — no half-written file ever exists.

4. **Orchestrator re-launches** `python3 v84.py --ai --answer
   --dir /proj`. Harness verifies the answer's `id` matches the
   pending question's id, consumes it (deletes `question.json`
   and `answer.json`), processes the selection, copies role
   templates, writes `profile.yaml` with the chosen roles,
   advances `next_step`.

5. The roles stage is done. Harness continues — `stack` stage
   runs, AI-proposes stack picks, emits a new `question.json`
   (kind: `field_editor`, walking each role's stack fields),
   exits 42 again.

6. Loop continues. Each question/answer pair = one orchestrator
   iteration. Eventually the pipeline reaches a no-input phase
   (cycle running, finish stage, etc.) — harness exits 0,
   the harness exits 0 with a final `{"phase": "done"}` event on
   stdout. Orchestrator stops the loop.

## Compatibility notes

- The `v84_protocol` field is currently `"1"`. Future incompatible
  changes will bump this. Orchestrators should reject questions
  with unknown protocol versions and surface a clear error.
- Adding new fields to a question is backwards-compatible. Adding
  new question kinds is not — orchestrators should treat unknown
  kinds as errors, not silently accept them.
- The `intent` field is informational; orchestrators may render it
  to humans verbatim, but should not parse it for control flow.

