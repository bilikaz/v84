# Screens

> Visual + behavioural reference for every interactive screen v84
> puts in front of the user. One screen per painter, plus the
> shared modal patterns. Keep this in sync when adding or rewiring
> a painter; it's the canonical place for "what does that screen
> look like and what does it do?"

All painters share the conventions in
[feedback_painter_ux memory](../../) — alt-screen takeover, clear-and-redraw
on every keystroke, `↑/↓` for all navigation (never `←/→`), `space`
acts on the current row, `esc` cancels, `enter` drills in (never a
global commit). See "Cross-cutting rules" at the bottom of this
file for the consolidated keymap.

Sections:

1. Pickers (the five core painters)
2. Progress displays (spinner, multi_spinner)
3. Confirm modal (shared yes/no slip-protection guard)
4. `review_list` (generic tick + drill + edit + action-bar painter;
   rule review under user_review is the first concrete caller)
5. Cross-cutting rules

---

## 1. Pickers

### `single_select` — pick exactly one option from a list

Used by: main menu, plan revise loop's "accept / revise" picker,
init structure's per-role layout picker action, anywhere we need
"pick one of these named options."

**Signature**

```python
def single_select(
    options: list[dict],
    *,
    prompt: str = "Pick one:",
    preselected: Optional[str] = None,
    allow_custom: bool = True,
    custom_label: str = "type custom...",
    summary: str = "",
) -> Optional[str]
```

`options[i]` is one of:

- Selectable: `{"name": str, "label"?: str, "info"?: str}`
- Header (visual; cursor skips):
  `{"kind": "header", "title": str}`

Returns the chosen option's `name`, the typed custom string when
`allow_custom=True` and the user picked the custom row, or `None`
on cancel.

**Keymap**

| Key   | Action                                  |
|-------|------------------------------------------|
| `↑/↓` | Move cursor                              |
| `space` / `enter` | Pick the cursor row              |
| `esc` | Cancel (returns `None`)                  |

**Visual**

```
  v84 — main menu
  project: /var/www/myapp
  status:  iteration 1, round 2 (next: review)

  ↑/↓ move · enter pick · esc cancel

  Project
  ─────────

  ›  Start / resume     run the next pending stage
     Setup LLM          change endpoint or re-probe model
     Manage rules       review/edit project-promoted rules

  Session
  ─────────

     Quit               exit the harness
```

Header rows (`{"kind": "header", "title": ...}`) render bold and
non-selectable. Rows have a `›` cursor on the focused entry and
inverse-video the focused row.

**Notes**

- `allow_custom: true` adds a "type custom..." row at the bottom
  that opens a text_input on selection.

---

### `checklist` — pick zero or more from a list

Used by: roles stage (which roles to activate).

**Signature**

```python
def checklist(
    options: list[dict],
    *,
    prompt: str = "Select items:",
    preselected: Optional[set[str]] = None,
) -> list[str]
```

`options[i]` is `{"name": str, "label"?: str, "info"?: str}`.

Returns the list of ticked `name`s in option order. On non-TTY
(piped/CI), returns `preselected` unchanged.

**Keymap**

| Key   | Action                                |
|-------|----------------------------------------|
| `↑/↓` | Move cursor                            |
| `space` | Toggle the cursor row                |
| `enter` | Confirm — return all ticked rows     |
| `esc` | Cancel                                 |

**Visual**

```
  Activate roles for this project
  ↑/↓ move · space toggle · enter confirm · esc cancel

  AI suggests: Frontend, Backend, DevOps based on the brief.

  ›  [✓] Frontend     pages, primitives, services, api-boundary
     [✓] Backend      entities, services, api, security
     [ ] Mobile       ui-ux, services, entities, security
     [✓] DevOps       infra, deps, ci-cd, observability
     [ ] Testing      unit, integration, e2e, quality
     [ ] Brand        visual, voice, copy, consistency
     [ ] Data         schema, queries, migrations, analytics
     [ ] Integrations contracts, flows, resilience, sync
```

`[✓]` ticked / `[ ]` unticked. Pre-selection comes from the
caller; user toggles to override.

---

### `field_editor` — walk fields grouped in sections, pick / type / skip per field

Used by: stack stage (per-role tech picks), structure stage (per-
role + global section paths), plan stage (clarifying-question
answers). The user_review screen no longer uses field_editor —
it now drives `review_list` (see §4).

**Signature**

```python
def field_editor(
    sections: list[dict],
    *,
    prompt: str = "Review proposal:",
    summary: str = "",
) -> Optional[list[dict]]
```

`sections[i]` is:

```python
{
    "title": str,                 # section header (e.g. "Frontend")
    "fields": list[dict],         # one entry per editable field
    "_meta": dict,                # caller's metadata, untouched
}
```

`fields[j]` is:

```python
{
    "label":              str,    # row label (e.g. "language")
    "value":              str,    # current value (also used as the
                                  # initial "recommendation" if absent)
    "recommendation":     str,    # top-of-picker option, preselected
    "recommendation_label": str,  # optional inline tag on rec row
    "alternatives":       list[str],  # other picker options
    "alternative_label":  str,    # optional inline tag on alt rows
    "optional":           bool,   # offer "none" / decline
    "optional_tag":       str,    # inline tag in row list ("(optional)"
                                  # default; "" suppresses entirely)
    "skip_label":         str,    # label for the "none" option
    "custom_label":       str,    # label for the custom-text row
    # caller may attach arbitrary "_*" keys; preserved on return
}
```

Returns the same `sections` list with each field's `value` updated
to the user's pick (or `"none"` when declined). Fields not touched
keep their original `value`. Returns `None` on top-level ESC.

**Keymap**

The painter has three internal modes (`review` / `pick` / `custom`)
sharing the same alt-screen.

Review mode (the list of fields):

| Key   | Action                                            |
|-------|---------------------------------------------------|
| `↑/↓` | Move cursor                                       |
| `space` | Open the picker for the cursor field            |
| `enter` | Confirm all fields and return                   |
| `esc` | Cancel                                            |

Pick mode (alternatives for one field):

| Key   | Action                                            |
|-------|---------------------------------------------------|
| `↑/↓` | Move cursor                                       |
| `space` / `enter` | Commit highlighted option           |
| `esc` | Back to review                                    |

Custom mode (free-text for one field):

| Key   | Action                                            |
|-------|---------------------------------------------------|
| `enter` | Commit the typed text                          |
| `esc` | Back to pick                                      |

**Visual (review mode)**

```
  Pick the project's stack
  ↑/↓ move · space change · enter confirm · esc cancel

  Frontend
  ────────

  ›  language        TypeScript
     framework       React 18 (optional)
     build           Vite 5
     ui              shadcn/ui
     styling         Tailwind 3

  Backend
  ───────

     language        Python 3.12
     framework       FastAPI
     ...
```

**Visual (pick mode)**

```
  Pick the project's stack
  ↑/↓ move · space/enter pick · esc back

  Frontend
  ────────
     language: TypeScript

     ›  TypeScript      recommended
        JavaScript      simpler, no types
        type custom...
```

**Known issue (motivating the rule_review redesign)**

`enter` in review mode commits everything. Users reaching for "drill
in" semantics on a row hit `enter` and accidentally commit the whole
form. New screens use `enter` for drill-in only; commit lives behind
a confirm modal.

---

### `detail_list` — walk items with toggleable detail, finish via action picker

Used by: decompose revise loop (review the proposed task list,
accept-or-revise).

**Signature**

```python
def detail_list(
    items: list[dict],
    *,
    actions: list[dict],
    prompt: str = "",
    summary: str = "",
    item_hint: str = "more details",
) -> Optional[str]
```

`items[i]` is `{"label": str, "detail": str}` — `detail` is
multi-line prose shown indented when the row is expanded.

`actions[i]` is `{"name": str, "label": str, "info"?: str}` —
mirrors single_select's selectable shape.

Returns the chosen action's `name`, or `None` on cancel. Does NOT
return which items were expanded — expansion is a read-only UX
state, not a result.

**Keymap**

| Key      | Action                                          |
|----------|-------------------------------------------------|
| `↑/↓`    | Move cursor                                     |
| `space`  | Toggle detail expansion on the cursor row       |
| `enter`  | Open the action picker (Accept / Revise / etc.) |
| `esc`    | Cancel                                          |

**Visual (collapsed)**

```
  Review the task plan
  ↑/↓ move · space expand · enter actions · esc cancel

  ›  v84-1: Scaffold the monorepo shell                    (more details)
     v84-2: Add user registration                          (more details)
     v84-3: Add session token rotation                     (more details)
     v84-4: Add the export endpoint with rate limiting     (more details)
```

**Visual (one row expanded)**

```
  ›  v84-1: Scaffold the monorepo shell                    (less)

       Set up the monorepo skeleton — pnpm workspace, root
       package.json, root tsconfig path mapping, .gitignore,
       .nvmrc. Create apps/ and services/ with placeholder
       README files. Wire CI for lint + typecheck + test.

     v84-2: Add user registration                          (more details)
```

The `enter` → action-picker pattern shows up here because
"continue" is itself a deliberate action (accept the plan or
revise with a comment) — there's no risk of slip-commit since the
user has to navigate into a sub-picker.

---

### `text_input` — multi-line text entry

Used by: custom field values, decompose revise comments, free-form
briefs.

**Signature**

```python
def text_input(
    *,
    prompt: str = "Type your input:",
    summary: str = "",
    hint: Optional[str] = None,
) -> Optional[str]
```

Returns the typed string (newlines preserved as `\n`), or `None`
on ESC. Empty input + enter on a blank line confirms `""` (caller
treats empty-or-None as cancel by convention).

On non-TTY: reads stdin in one shot and returns the stripped
content (no ESC available).

**Keymap**

| Key       | Action                                       |
|-----------|----------------------------------------------|
| (printable) | Append to buffer                          |
| `backspace` | Delete previous char                      |
| `enter`   | Confirm (or newline — depends on the call)   |
| `esc`     | Cancel                                       |

**Visual**

```
  Type a custom path for frontend.app
  press Enter on empty line to confirm · esc cancel

  Current recommendation: apps/web

  > apps/marketing-site█
```

The block-character caret marks insertion. Multi-line mode lets
the user press enter once for newline; double-enter on an empty
line confirms.

---

## 2. Progress displays

### `spinner` — single LLM call live elapsed

Used during single-call stages (architect, classify-rules, plan,
decompose).

**Signature**

```python
class Spinner:
    def __init__(self, message: str, stream: Optional[TextIO] = None)
    def __enter__(self) -> Spinner
    def __exit__(self, exc_type, exc, tb) -> None
```

Context manager; runs a daemon thread for the animation. On TTY
stderr: animated braille frame + live elapsed `(Ns)`; on exit
clears and prints `✓ message (Xs)` or `✗ message (error)`. On
non-TTY: emits one-shot `→ message` then `✓/✗ ...(Xs)`.

**Visual**

```
  architecting iteration 1 — model qwen3.6-27b @ http://192.168.1.66:8000/v1
✓ calling qwen3.6-27b @ http://192.168.1.66:8000/v1 (313.1s)
```

In-flight: braille spinner cycling, elapsed seconds counting up.
On completion: `✓` plus final elapsed.

### `multi_spinner` — N parallel calls, one row each

Used during fan-out stages (draft, review, lead, patch, validate).

**Signature**

```python
class MultiSpinner:
    def __init__(self, labels: list[str], stream: Optional[TextIO] = None)
    def __enter__(self) -> MultiSpinner
    def __exit__(self, exc_type, exc, tb) -> None

    # progress callbacks (called by llm.call_many)
    def started(self, idx: int) -> None
    def done(self, idx: int, error: Optional[BaseException]) -> None
```

Pass to `call_many(..., progress=ms)` — the threadpool calls
`started(i)` when worker `i` picks up its job and `done(i, err)`
when it finishes. Renders one row per label, padded so the spinner
column aligns. On non-TTY: emits start + finish lines without ANSI.

**Visual**

```
  reviewing 16 (role × lens) — workers: 4

    ✓ backend.entities       (493.3s)
    ✓ backend.services       (430.9s)
    ✓ backend.api            (238.7s)
    ✓ backend.security       (486.2s)
    ⠋ devops.infra            145.2s
    ⠋ devops.deps             203.7s
      devops.ci-cd            (queued)
      devops.observability    (queued)
    ...
```

Each row: state glyph (`✓` done, `⠋…` spinning, blank queued),
label, elapsed (or `(queued)` for waiting workers).

---

## 3. Confirm modal — shared slip-protection guard

> A small two-button modal painter at `harness/ui/confirm_modal.py`.
> Used in front of any commit-style action — currently
> review_list's commit actions (`continue`, `regenerate`).

**Signature**

```python
def confirm_modal(
    *,
    title: str,                 # short title shown in the box header
    bullets: list[str] = (),    # consequences as a bulleted list
    body: str = "",             # one-paragraph elaboration below bullets
    yes_label: str = "Yes",
    no_label: str = "No",
    default: str = "yes",       # which button starts focused
) -> bool
```

Returns `True` on Yes-confirmed, `False` on No-or-ESC. No
asymmetric return types — the caller already knows what action it
was guarding.

**Keymap**

| Key   | Action                                       |
|-------|----------------------------------------------|
| `↑/↓` | Switch focus between Yes / No                |
| `enter` | Activate the focused button                |
| `esc` | Cancel (returns `False`)                     |

**Visual (regenerate)**

```
┌─ Promote and regenerate ─────────────────────────┐
│                                                  │
│  • Promote 12 rules to project root              │
│  • Clear cycle artifacts (drafts, corrections,   │
│    reviewer files)                               │
│  • Reset to round 1 / draft                      │
│                                                  │
│  This redrafts every action against the new      │
│  rule set. ~Cost: full cycle re-run.             │
│                                                  │
│  ›  [ Yes ]                                      │
│     [ No ]                                       │
│                                                  │
│  enter confirm  ·  ↑/↓ switch  ·  esc cancel     │
└──────────────────────────────────────────────────┘
```

**Visual (continue)**

```
┌─ Promote and continue ───────────────────────────┐
│                                                  │
│  • Promote 12 rules to project root              │
│  • Write tasks.md handoff                        │
│  • Advance to finish                             │
│                                                  │
│  Existing actions stay; iteration closes after   │
│  finish verifies coverage.                       │
│                                                  │
│  ›  [ Yes ]                                      │
│     [ No ]                                       │
│                                                  │
│  enter confirm  ·  ↑/↓ switch  ·  esc cancel     │
└──────────────────────────────────────────────────┘
```

**Notes**

- Default focus on `[ Yes ]` since the user pressed the trigger
  key (`c` / `r`) deliberately. Quick path: trigger → enter = two
  keystrokes.
- Manual user can `↑/↓` to read both buttons before deciding.
- Buttons stack vertically so the keystroke matches the visual —
  rule 8 (no `←/→` navigation in v84).
- The body bullets the consequences in the same shape every time:
  what gets written, what state changes, what the cost is.

---

## 4. `review_list` — generic tick + drill + edit painter

> Look at sectioned records, optionally tick a subset, optionally
> drill into per-row alternatives, optionally inline-edit the
> row's text, then take one of N caller-defined actions from the
> bottom bar. Lives at `harness/ui/review_list.py`. First concrete
> caller is the user_review rule-review screen (see §4a); other
> existing painters could fold in over time (see §4b).

**Signature**

```python
def review_list(
    sections: list[dict],
    *,
    actions: list[dict],          # bottom action bar (caller-defined)
    summary: str = "",            # multi-line context above the list
    enable_tick: bool = True,     # space toggles row's `ticked`
    enable_pick: bool = False,    # enter opens row's alternatives picker
    enable_edit: bool = False,    # e opens inline editor on row's text
) -> Optional[dict]
```

`sections[i]`:

```python
{
    "title":  str,                # section header (e.g. "Frontend rules")
    "_meta":  dict,                # caller's metadata — preserved on return
    "rows":   list[dict],          # one row per record
}
```

`rows[j]` — every key beyond `text` is optional; populate the ones
relevant to the features you enabled:

```python
{
    "label":         str,          # row identifier shown on the header line
                                   # (e.g. "v84-1.frontend.rule.1")
    "text":          str,          # multi-line body shown indented
    "ticked":        bool,         # initial tick state (when enable_tick)
    "alternatives":  list[str],    # picker options (when enable_pick)
    "tag":           str,          # short inline tag on header line
                                   # (e.g. "AI: promote", "edited")
    "_record":       dict,         # caller's full source record — untouched
}
```

`actions[i]` — the bottom bar:

```python
{
    "name":    str,                # returned to caller on commit
    "label":   str,                # shown on the bar (e.g. "promote & continue")
    "key":     str,                # single-char hotkey (e.g. "c")
    "kind":    "commit" | "mutate",
    "confirm": Optional[dict],     # commit-only: opens confirm_modal first
                                   # {title, bullets, body}
    "handler": Optional[callable], # mutate-only: handler(sections) → sections
                                   # called when key fires; result replaces
                                   # the current sections, screen stays open
}
```

`esc` is implicit — always returns the cancel result, never bound
as an action.

**Returns:**

```python
# user pressed a commit action
{
    "action":   <commit action's name>,
    "sections": <mutated sections>,
}

# user pressed esc
None
```

`<mutated sections>` carries each row's final `ticked` and `text`
state plus any rows added by mutate actions, so the caller has
the post-edit state in one place.

**Two regions, `tab` to switch focus.** Every screen
review_list paints has a list region above and a horizontal action
bar below, separated by a divider. `tab` toggles which region has
focus. The header keymap line redraws to show whichever region is
currently focused.

**Keymap (list region focused)** — auto-built from enabled features:

| Key       | Action                                                  | Shown when            |
|-----------|---------------------------------------------------------|-----------------------|
| `↑/↓`     | Move cursor                                             | always                |
| `space`   | Tick / untick the cursor row                            | `enable_tick=True`    |
| `enter`   | Open alternatives picker for the cursor row             | `enable_pick=True`    |
| `e`       | Inline-edit the cursor row's text                       | `enable_edit=True`    |
| `<key>`   | Fire one of the `actions[]` entries directly            | per action            |
| `tab`     | Move focus → action bar                                 | always                |
| `esc`     | Cancel — return `None`                                  | always                |

**Keymap (action bar focused via `tab`)**

| Key       | Action                                                  |
|-----------|---------------------------------------------------------|
| `←/→`     | Move between buttons (horizontal layout matches axis)   |
| `enter`   | Activate the focused button (commit or mutate)          |
| `tab`     | Move focus → list                                       |
| `esc`     | Cancel — return `None`                                  |

**Keymap (alternatives picker — internal mode, drilled in via `enter`)**

The picker has the same two-region layout: alts above, action bar below.

List region:

| Key       | Action                                                      |
|-----------|-------------------------------------------------------------|
| `↑/↓`     | Move cursor between alternatives                            |
| `space`   | Select cursor alt as the row's text, return to main list    |
| `e`       | Inline-edit cursor alt as starting text → edit mode         |
| `tab`     | Move focus → action bar                                     |
| `esc`     | Back to the main list, no change                            |

Action bar (focused via `tab`): horizontal row of `[space] select`,
`[e] edit`, `[esc] back`. `←/→` to move, `enter` to fire.

**Why `space` (not `enter`) selects the alternative:** `space` is
"act on the cursor row" everywhere in v84 (rule 3). Reserving
`enter` for "confirm input" (its meaning in edit mode and in the
action bar) keeps every screen's `enter` semantics identical —
finalize / save / activate, never "pick a row."

**`esc` semantics by region (per rule 10):**

| Region | When dirty (≥1 tick/edit/add since open) | When clean |
|--------|------------------------------------------|------------|
| Main list | Pop confirm_modal: `Discard your changes?` with bullets counting ticks differing, edits made, rows added → yes returns `None`, no stays | Silent exit, return `None` |
| Alt picker | (always clean — `space` commits + exits, esc backs out without state) | Silent back to list |
| Edit mode | Pop confirm_modal: `Discard edit?` → yes returns to caller (list or picker), no stays | Silent back |

State equality, not journal. Tick → untick → tick reads as clean.
Snapshot the initial sections when the painter enters; compare on
every `esc`.

**Visual (list region focused — all features enabled)**

```
  <summary block, multi-line, caller-provided>                          12 of 18 ticked
  ↑/↓ move · space tick · enter alternatives · e edit · <action keys> · tab actions · esc cancel

  <section title>
  ─────────────

  [✓] <row label>                                          <row tag>
      <row text, indented, multi-line>

  [ ] <row label>                                          <row tag>
      <row text, indented>

  ────────────────────────────────────────────────────────────────
  [<key>] <action label>     [<key>] <action label>     [esc] cancel
  <optional caller-provided status line beneath the bar>
```

**Visual (action bar focused via `tab`)**

```
  <summary block, multi-line, caller-provided>                          12 of 18 ticked
  ←/→ select · enter run · tab back · esc cancel

  <section title>
  ─────────────

  [✓] <row label>                                          <row tag>
      <row text, indented, multi-line>

  ...

  ────────────────────────────────────────────────────────────────
  ‹ [<key>] <action label> ›   [<key>] <action label>     [esc] cancel
  <optional caller-provided status line beneath the bar>
```

Header keymap line swaps to the action-bar bindings; the focused
button gets `‹ … ›` brackets so the user sees which one will fire
on `enter`.

**Visual (alternatives picker — same painter, internal mode)**

```
  <row label> — pick or edit
  ↑/↓ move · space select · e edit · tab actions · esc back

  ›  [✓] <row's current text>

     [ ] <alt #1>

     [ ] <alt #2>

  ────────────────────────────────────────────────────────────────
  [space] select   [e] edit   [esc] back
```

`[✓]` marks the option whose text matches the row's current `text`
(radio-style — only one is ticked at a time). `›` is the cursor.
`space` on a `[ ]` row moves the tick to that row and exits the
picker (the row's `text` becomes that option). `space` on the
already-`[✓]` row is a no-op exit. `e` on any row loads it into
`text_input` pre-populated for tweaking. `tab` shifts focus to the
action bar; `←/→` moves between buttons, `enter` activates.

**Visual (inline edit — internal mode, `e` from list or picker)**

```
  Edit <row label>
  type · enter save · esc cancel

  > <pre-populated text, edits in place>█
```

Pre-populated with the current text. User tweaks; `enter` saves
into the row's `text`; `esc` discards and returns to wherever they
came from (list or picker).

**Design rationale**

- **Tick/untick is the most common action** when present → `space`
  on the fastest possible keystroke.
- **Alternatives are second-most-common** → `enter` drills in,
  matching universal "open detail" semantics across painters.
- **Edit is third** (people are lazy to retype, want to tweak) →
  `e` from anywhere short-circuits the alt-picker drill-in.
- **Commit lives behind a divider + a confirm modal** —
  belt-and-suspenders against slip-keypress disasters.
- **Tags surface caller metadata** on each row (e.g. AI bucket,
  edited flag) so users see signal without drilling in.
- **`mutate` actions stay in screen** — used for "Add row" or
  "Drop row" flows where the user is still working on the list.

### 4a. Example caller — rule review

The user_review stage's "review accepted rules" screen is just
`review_list` configured for rules. It replaces the field_editor-
based screen currently in `user_review.py`.

**Caller call (rough shape):**

```python
result = review_list(
    sections=_build_rule_sections(...),
    summary=f"Iteration {n} — review accepted rules",
    enable_tick=True,
    enable_pick=True,
    enable_edit=True,
    actions=[
        {
            "name":  "continue",
            "key":   "c",
            "label": "promote & continue",
            "kind":  "commit",
            "confirm": {
                "title": "Promote and continue",
                "bullets": [
                    "Promote ticked rules to project root",
                    "Write tasks.md handoff",
                    "Advance to finish",
                ],
                "body": "Existing actions stay; iteration closes "
                        "after finish verifies coverage.",
            },
        },
        {
            "name":  "regenerate",
            "key":   "r",
            "label": "promote & regenerate",
            "kind":  "commit",
            "confirm": {
                "title": "Promote and regenerate",
                "bullets": [
                    "Promote ticked rules to project root",
                    "Clear cycle artifacts (drafts, corrections, reviewer files)",
                    "Reset to round 1 / draft",
                ],
                "body": "This redrafts every action against the new "
                        "rule set. ~Cost: full cycle re-run.",
            },
        },
        {
            "name":    "add",
            "key":     "a",
            "label":   "add rule",
            "kind":    "mutate",
            "handler": _add_rule_handler,  # opens text_input + scope picker,
                                           # appends a new row, returns sections
        },
    ],
)
```

**Visual (rule review, concrete):**

```
  Iteration 1 — review accepted rules                           12 of 18 ticked
  ↑/↓ move · space tick · enter alternatives · e edit · c continue · r regenerate · a add · tab actions · esc cancel

  Global rules
  ─────────────

  [✓] v84-1.architect.rule.1                              AI: promote
      Every CSS animation block is wrapped in @media
      (prefers-reduced-motion: no-preference) so the page degrades
      to a static scene when the user opts out.

  [✓] v84-1.architect.rule.2                              AI: promote · edited
      Stay fully self-contained — system fonts only, no third-party
      requests.

  Frontend rules
  ──────────────

  [ ] v84-1.frontend.rule.1                               AI: iteration-only
      Defer Storybook; use inline render tests during the scaffold
      phase.

  [✓] v84-1.frontend.rule.2                               AI: promote
      All external UI primitives are wrapped in a local export layer
      that enforces design tokens.

  ────────────────────────────────────────────────────────────────
  [c] promote & continue   [r] promote & regenerate   [a] add rule   [esc] cancel
  3 rules edited from lead's wording — `r` regen redrafts to honour them
```

When the user presses `tab` from this screen, the header line
collapses to `←/→ select · enter run · tab back · esc cancel`,
the focused button gets `‹ … ›` brackets, and `enter` will fire it
(routing through the action's confirm modal if defined).

The promotion / restart machinery in `user_review.py` stays put;
it just dispatches on the explicit returned action (`continue` /
`regenerate` / cancel via `None`) instead of inferring restart
from "did any kept rule's text change."

### 4b. Other screens `review_list` could replace

Pre-survey of existing painters that fit the shape:

| Today's painter        | Used by                     | Switch to `review_list` with                                                |
|------------------------|-----------------------------|-----------------------------------------------------------------------------|
| `single_select`-based `manage_rules` | manage promoted rules menu | `enable_edit=True`, actions for `[s]ave`, `[a]dd`, `[d]rop`, `[esc]cancel` |
| `checklist` (roles stage) | activate roles at init    | `enable_tick=True`, single `[c]onfirm` action                               |
| `detail_list` (decompose revise) | review proposed task list | all features off; actions `[a]ccept`, `[r]eject` (caller opens text_input on reject) |

All three are clean swaps. `detail_list` doesn't need a "toggle
detail" feature flag — `review_list`'s rows already render the
full text inline, so "more details" was working around field-list
truncation that doesn't exist in this painter. Decompose's revise
flow becomes: paint plan → user accepts or rejects → on reject,
caller opens `text_input` for the revise comment, fires the LLM
with `(prior plan + comment) → new plan`, re-paints. Loop until
accept or esc.

`field_editor` (stack, structure stages) is NOT a candidate — its
review/pick/custom three-mode interaction is genuinely different
shape from review_list's tick-and-act model. Keep separate.

---

## 5. Cross-cutting rules

Locked-in across every painter (per
[feedback_painter_ux memory](../../) rules 1-9):

| Convention                          | Rule                                                               |
|-------------------------------------|--------------------------------------------------------------------|
| **Alt-screen takeover**             | Painter enters `\033[?1049h` on enter, restores on exit           |
| **Clear-and-redraw**                | `\033[H\033[2J` on every keystroke; no cursor-up arithmetic        |
| **`space` = act on current row**    | Toggle / open / pick — never global commit                         |
| **`esc` = cancel everywhere**       | Including text_input; nested modes walk back one mode at a time    |
| **`esc` confirms when it would lose work** | Dirty state (≥1 tick/edit/add since open) → confirm_modal; clean state → silent exit |
| **Nav axis matches visual axis**    | `↑/↓` for vertical lists; `←/→` for horizontal action bars only. `tab` switches focus between regions |
| **`enter` ≠ global commit**         | Drill into row / activate focused control only                     |
| **Header constant across modes**    | Prompt + controls hint + summary stay; only body changes           |
| **`read_key` returns logical names**| `up`, `down`, `enter`, `space`, `esc`, `ctrl_c`, `eof`, `backspace`|
| **Non-TTY fallback mandatory**      | Every painter checks `isatty()`; non-TTY returns sensible default  |

When adding a new painter: drop it as `harness/ui/<name>.py`, import
`alt_screen, read_key` from `._term`, follow these rules, add to
`ui/__init__.py`. Reference the closest existing painter for
shape; the conventions above are the contract.
