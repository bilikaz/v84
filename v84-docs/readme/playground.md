# Playground

> Local web tool for testing prompts and instructions against the
> configured LLM. Same code paths as the real harness — same
> `call_json`, same streaming, same validator. Two modes: stage-aware
> Preview Request, and freeform Blank.

## When to reach for it

- A stage is failing in production and you want to iterate on the
  instruction prose without re-running the whole pipeline.
- You want to see exactly what context the harness assembles for a
  stage (the rendered `build_user_msgs` output) before sending.
- You want the model to review one of the project's `.md` or
  `.schema.json` files and suggest improvements.
- You want to fan out N parallel runs to check sampling consistency
  ("does this prompt work 4 times in a row?").

## Launching

From a project root:

```
python3 v84-docs/harness/v84.py --test-server          # default port 8000
python3 v84-docs/harness/v84.py --test-server 8765     # override port
```

Then open `http://localhost:8000/` in a browser. The header strip
shows the resolved project context — project dir, current iteration,
parent task, active roles. The LLM endpoint comes from the standard
resolution chain (profile.yaml → user cache → env).

The header carries a mode toggle: **Preview Request** | **Blank**.

## Preview Request mode

Stage-bound. Pick any stage from the left sidebar (grouped by
`init/` and `iteration/`).

The panel shows, top to bottom:

1. **Schema examples** — every `examples[]` entry from the schema,
   each labelled with its title.
2. **`build_user_msgs` spec** — pre-filled with a realistic template
   for the stage (with the picked role swapped in). Edit freely. Pick
   role from the dropdown (active roles from the project).
   - **Render preview** posts to `/api/render/<group>/<stem>` which
     calls `build_user_msgs(project_dir, parent, iteration_n, spec,
     role=role)`. Each rendered message appears as a collapsible.
3. **System message override** — collapsed by default. Defaults to
   the `.md` instruction; click "Load default into editor" to populate,
   then tweak. Empty = use the `.md` as-is.
4. **Augmented system prompt** — collapsed. Read-only preview of
   what the model actually sees: your system override (or the `.md`)
   plus the auto-generated `## Response format` block (shape line,
   per-title examples, full schema).
5. **Run knobs** — tag, concurrency, retries, max_tokens.
6. **Send to LLM** — runs the schema-augmented call through the
   exact same `call_json` path the harness uses.

Each result card shows attempts, parse errors, schema errors, raw
content (collapsible), parsed value, log name per attempt, elapsed
seconds. Schema validation is enforced — same validator the
production path uses.

## Blank mode

Freeform. No stage in the URL, no schema, no validation.

Top to bottom:

1. **System message** — write whatever you want.
2. **`build_user_msgs` spec** — same as Preview Request but
   stage-agnostic. Click **Render preview into messages** and the
   rendered messages populate the user-message list below
   (replacing it). You can keep editing or adding messages after.
3. **Instruction files** — dropdown of every `.md` and
   `.schema.json` under `instructions/`, grouped, with file size.
   Pick one and click **+ Add file as message** — the file content
   appends as a new user message, prefixed with `# instructions/<group>/<name>`
   so the model knows which file it's reading. Useful for
   "review this instruction, suggest improvements" workflows.
4. **User messages list** — starts with one empty box. Add `+ message`
   or remove individual boxes freely.
5. **Run knobs** — same as Preview Request, plus retries here mean
   independent re-runs (no validator to feed back to).
6. **Send to LLM** — posts to `/api/test_raw`. The system message
   goes through verbatim — no `## Response format` block, no schema
   augmentation. JSON parsing is attempted on the raw content
   (informational only); shows parsed view if the model happened to
   return valid JSON.

Total instances per send = `concurrency × retries`.

## Logs

Every run lands under `.v84-logs/<tag>-<group>-<stem>-i<N>-a<attempt>-<ts>.{json,md}`
(Preview Request) or `<tag>-blank-i<N>-<ts>.{json,md}` (Blank). The
tag is whatever you typed in the run knobs — searchable later with
`ls .v84-logs/<tag>-*`.

Per-attempt log names also surface in each result card so you can
jump straight from the UI result to the persisted call envelope.

## Live progress

While the call runs:
- The status next to the Send button shows elapsed seconds (live ticker).
- The result section shows N "pending" placeholder cards immediately
  after click, so a 4× concurrency run shows four cards waiting.
- The terminal where the server is running prints per-call stderr
  lines: `→ [<tag>#1] sent`, periodic streaming snapshots, and
  `✓ [<tag>#1] Xs — content:Nc think:Mc (valid JSON)` on completion.

(The browser UI only shows results once the response comes back —
streaming-to-browser is not wired.)

## HTTP API

For scripting outside the browser:

```
GET  /                          HTML playground
GET  /api/project               { project_dir, active_roles, iteration_n, parent_id, parent_task }
GET  /api/stages                [{group, stem}, ...]
GET  /api/stage/<g>/<s>         { schema, system, augmented_system, examples, spec_template, default_role }
GET  /api/instructions          [{group, name, relpath, kind, size}, ...]
GET  /api/instruction/<g>/<n>   { group, name, relpath, content }
POST /api/render                body {spec, role}                    → { user_msgs }
POST /api/render/<g>/<s>        body {spec, role}                    → { user_msgs } (stage-bound, same impl)
POST /api/test/<g>/<s>          body {user_msgs|spec, role,
                                       system_override, max_tokens,
                                       retries, concurrency, tag}
                                  → { augmented_system, user_msgs,
                                      runs: [{ok, value, attempts}] }
POST /api/test_raw              body {system, user_msgs, max_tokens,
                                       retries, concurrency, tag}
                                  → { system, user_msgs,
                                      runs: [{raw, parse_error,
                                              parsed?, elapsed_s,
                                              log_name}] }
```

Path traversal on `/api/instruction/<g>/<n>` is blocked — `<n>` must
resolve inside `instructions/<g>/`.

## Source

| File | Purpose |
|---|---|
| `harness/test_server.py` | The server, the HTML, the routes |
| `harness/v84.py` (`--test-server`) | CLI entry that launches it |
| `harness/llm/client.py` | The call paths the playground reuses |
| `harness/core/context.py` (`build_user_msgs`) | The render path |
