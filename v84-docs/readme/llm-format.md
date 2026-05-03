# LLM format

> JSON on the wire, YAML on disk. Each stage is a `.md` + `.schema.json`
> pair. The harness auto-builds the response-format block, validates
> the parsed JSON, retries on failure, and streams progress so long
> calls stay visible.

This doc covers everything that crosses the LLM boundary. For on-disk
state files, see `format.md`.

## Why JSON for the wire

Old v84 used YAML responses gated by a `====== MY RESPONSE ======`
marker. That worked but was brittle:

- YAML is whitespace-significant; weak models break indentation
  often.
- Markers needed retry / extraction / fallback paths.
- Thinking models occasionally inlined free-form prose before the
  marker.

The current path: ask for JSON, parse with `json.loads`, validate
against a JSON Schema. JSON has rigid syntax (every `{` needs `}`,
every key is quoted) so it's easier for the model to get right and
trivial for us to parse.

`response_format: {"type": "json_object"}` is sent on every call. The
provider enforces basic JSON validity; the schema goes into the system
prompt as guidance (and our validator catches drift after parse).

Note on schema enforcement: vLLM with thinking models does NOT support
`response_format: {"type": "json_schema", ...}` — the constraint blocks
tokens during reasoning and the model never emits the answer. So the
schema is hint-only on the wire; we enforce it ourselves post-parse.

## Stage layout: a pair per stage

Every stage owns two files under `instructions/<group>/<stem>.{md,schema.json}`:

```
instructions/iteration/
  review_validate.md           ← semantics
  review_validate.schema.json  ← shape
  lead.md
  lead.schema.json
  …
```

- `.md` = pure prose. What the model is, what it receives, when to
  accept / reject, what to think about. No JSON examples, no schema
  details, no "respond with JSON" instructions.
- `.schema.json` = JSON Schema describing the response shape, plus an
  `examples` array of titled valid responses.

The harness loads the pair via `core.util.load_instruction(group,
stem)` which returns `(prose, schema)`. The prose becomes the system
prompt; the schema becomes the response-format guidance.

## Schema shape

Standard JSON Schema with one v84-specific convention: `examples` is
a list of `{title, example}` objects (not bare values).

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["corrections", "rules"],
  "properties": {
    "corrections": { ... },
    "rules": { ... }
  },
  "examples": [
    {
      "title": "One or more concerns to raise",
      "example": {
        "corrections": [{ "verdict": "missing", ... }],
        "rules": []
      }
    },
    {
      "title": "Nothing to raise (the common case)",
      "example": {
        "corrections": [],
        "rules": []
      }
    }
  ]
}
```

Each title is the situation the example covers. The renderer emits
one `### <title>` block per example so the model can match its
situation to a concrete shape.

The validator subset supported (`llm.client._validate_against_schema`):
- `type`: `object` | `array` | `string` | `integer` | `number` | `boolean` | `null`
- `properties` per-key sub-schemas
- `required` list
- `additionalProperties`: `false` (reject extras) or sub-schema
  (validate every extra)
- `items` for arrays
- `enum` literal whitelist
- `$ref` / `$defs` for recursive shapes (used by `plan.schema.json`)

`format` keywords (minLength, pattern, etc.) are not enforced.

## Auto-augmented system prompt

`call_json` prepends a `## Response format` block to the caller's
system prompt. The block is built by `_response_format_block(schema)`
and contains, in order:

1. `Return only JSON. No prose, no explanation, no markdown fences …`
2. A one-line shape summary (`Top-level: a JSON object with keys
   corrections, rules.`).
3. Each `examples[]` entry rendered as `### <title>\n```json\n…```\n`.
4. The full schema (with `examples` stripped — already shown above)
   as a fenced JSON block.

Stage authors don't write any of this. The schema drives the prompt
content; change the schema, the prompt updates everywhere.

## Retry semantics

`call_json` retries up to `cfg.retries` times on:
- JSON parse failure (model emitted invalid JSON despite the format)
- Schema validation failure (parsed but the wrong shape)

Each attempt re-sends the **original** messages verbatim — no echo of
the bad response, no "you got it wrong because X" feedback. Sampling
variance carries us across most one-off slips. The bad output isn't
fed back because it could be junk that pollutes context.

Network/transport failures (timeouts, 5xx, connection refused) are
retried separately by `_post_with_retry` inside each attempt.

If `cfg.retries` exhaust, raises `RuntimeError` with the last failure
mode and the attempt log name.

## Streaming and live tails

Every call uses `stream: true`. `_post` consumes the SSE stream
chunk-by-chunk, accumulates `content` + `reasoning_content`
(vLLM streams the latter as `reasoning` in deltas — both keys
accepted), and emits a tail snapshot every 1s OR every 200 chars
(whichever first).

Snapshot format:

```
░ [<log_name>] <elapsed>s thinking — think:N,Nc ▶ '...last 60 chars of reasoning'
░ [<log_name>] <elapsed>s writing  — think:N,Nc content:M,Mc ▶ '...last 60 chars of content'
```

Phase is whichever stream is currently growing. Tail is the last 60
characters of that stream, with newlines replaced by `↵` so a
multi-line tail still fits on one line.

Lets you spot when a long thinking phase wandered into nonsense
(`'10df32r409sdf23423'` instead of plausible reasoning) without
waiting for the call to finish and the log to be readable.

### Display modes

`_post` picks where the snapshot lands based on what's around it:

| Situation | Where the tail goes |
|---|---|
| `on_stream` callback supplied (MultiSpinner is the caller) | Routed to the spinner via `stream_update`; **no stderr output** |
| Single in-flight call + stderr is a tty | In-place `\r` overwrite — same line redraws |
| 2+ in-flight calls without spinner, OR non-tty | Newline per snapshot |

The `_STREAM_COUNT` global tracks in-flight calls so the in-place
mode auto-disables when a second call joins the pool.

## MultiSpinner integration

When a stage uses `call_many` with a `MultiSpinner` as `progress`,
each call's stream snapshot lands on its track's line:

```
  ⠋ backend.entities  (60s)   thinking — think:25,591c content:0c ▶ 'dAt with @default(now())) enforcing single…'
  ⠋ backend.services  (58s)   writing — think:24,123c content:412c ▶ '"v84-1.2.backend.1", "verdict": "accept"},'
  ✓ devops.deps       (12.5s)   think:5,341c content:892c
    testing.unit                 (queued)
```

- In-flight tracks show phase + counts + tail.
- Finished tracks keep the final char counts as a stats footnote
  (no phase, no tail) so a post-run scan shows which calls burned
  the most thinking and which produced the most content.
- Queued tracks just say `(queued)`.

Plumbing: `concurrent.py:call_many` detects `progress.stream_update`
and threads a per-call closure through to `call_json` →
`_post_with_retry` → `_post` as `on_stream`. When it's set, `_post`
quiets its stderr emits entirely and routes everything through the
spinner.

## Final completion line

When `on_stream` is not set (single calls outside the spinner), each
call ends with:

```
✓ [<log_name>] 132.4s — content:1,847c think:5,892c finish=stop
```

`finish` of `length` means the model hit `max_tokens` mid-response.
That's the "garbage starts arriving" signal — the response is
truncated and probably won't parse.

## What stays YAML

On-disk state is still YAML — `core.yaml`, `profile.yaml`, every
`<role>.corrections.yaml`, every `<role>.rules.yaml`, `plan.yaml`,
`status.yaml`. Block scalars + comments matter for human-edited
files. JSON output from the model gets converted to YAML at persist
time.

YAML in / JSON out / YAML out — the harness owns the two boundaries.

## Quick reference

| File | Role |
|---|---|
| `instructions/<g>/<s>.md` | Stage prose (semantics) |
| `instructions/<g>/<s>.schema.json` | Stage shape + titled examples |
| `harness/llm/client.py` | `call_json`, `_post`, validator, streaming |
| `harness/llm/concurrent.py` | `call_many`, `CallSpec`, spinner plumbing |
| `harness/ui/multi_spinner.py` | Per-track progress + live tail |
| `harness/core/util.py:load_instruction` | Reads the `.md` + `.schema.json` pair |
