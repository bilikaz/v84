# Running v84 with Scripts

> Full pipeline via bash scripts — any LLM provider. In a normal AI session the executor's `run.md` skill dispatches these for you; this doc covers the scripts themselves for direct invocation.

## Prerequisites

- `bash`, `curl`, `jq` installed.
- Access to an LLM:
  - Anthropic / OpenAI / Groq / Together / local vLLM / LM Studio (all via the `openai` or `anthropic` provider), **or**
  - local Ollama.

## How provider / model / URL are resolved

None of the scripts take a `provider` or `model` argument any more. They read three environment variables — `LLM_API_URL`, `LLM_PROVIDER`, `LLM_MODEL` — and fill in whatever's missing by probing with [`detect-llm.sh`](../scripts/detect-llm.sh):

1. If `LLM_API_URL` is set, probe only that URL.
2. Otherwise probe, in order, `http://localhost:11434` (Ollama), `http://localhost:11434/v1`, `http://localhost:8000/v1` (vLLM default), `http://localhost:1234/v1` (LM Studio).
3. First URL whose `/models` (OpenAI-compat) or `/api/tags` (Ollama) returns 200 wins. `LLM_PROVIDER` is inferred (`openai` or `ollama`) and `LLM_MODEL` is the first id the endpoint reports.
4. Any of `LLM_API_URL` / `LLM_PROVIDER` / `LLM_MODEL` you've already exported wins over whatever the probe finds — set one, two, or all three.

Net effect: export once, then just run the scripts. No flags, no arguments, no re-typing the model on every call.

## Environment setup

### Hosted Anthropic

```bash
export LLM_API_KEY=sk-ant-xxx
export LLM_PROVIDER=anthropic
export LLM_MODEL=claude-sonnet-4-5       # or claude-haiku-4-5-20251001
```

### Hosted OpenAI (or Groq / Together / anything OpenAI-compatible)

```bash
export LLM_API_KEY=sk-xxx
# Default host is api.openai.com; override for a compatible provider:
export LLM_API_URL=https://api.groq.com/openai/v1
export LLM_MODEL=llama-3.3-70b-versatile  # optional — first /models id wins
```

### Local vLLM / LM Studio on this machine

Nothing to set — the detector finds `localhost:8000/v1` or `localhost:1234/v1` on its own. Just run the script.

### Local LLM on another machine (the common "one variable" case)

This is the minimum call: export the URL, let detect-llm.sh figure out the rest.

```bash
export LLM_API_URL=http://192.168.1.66:8000/v1
# LLM_PROVIDER auto-resolves to "openai" (OpenAI-compat probe succeeds).
# LLM_MODEL auto-resolves to whatever the endpoint serves right now.

scripts/architect/run.sh plan 2 "Add email verification and forgot-password flows"
scripts/cycle/run.sh 2 15
```

If the remote model changes (e.g. the vLLM host swaps it out), `detect-llm.sh` picks the new one up on the next call without any edits here.

### Local Ollama

```bash
# Nothing to set — scripts default to http://localhost:11434 and infer "ollama".
# To pin a specific model, export:
export LLM_MODEL=llama3.1:70b
```

## Scripts at a glance

| Script | Purpose |
|---|---|
| `scripts/build-context.sh {n}` | Rebuild `context/` from current state (conventions, trees, packages, plan, corrections). Safe to run any time — auto-runs from other scripts. |
| `scripts/generate-trees.sh` | Regenerate `trees/*.tree` from source files that carry `[v84-*]` tags. |
| `scripts/generate-missing.sh [n]` | Produce `plan/missing.md` (whole-repo) or `plan/{n}/missing.md` (single iteration) — four-bucket plan-vs-code drift report: exists-untagged, missing-on-disk, tagged-but-orphaned, and fully-untagged source files. |
| `scripts/architect/run.sh <skill> {n} [user_request]` | Run architect — `plan` (needs the request as 3rd arg) or `review`. Handles call + parse + post-review extraction. |
| `scripts/agents/run.sh {n} [skill] [agents]` | Run every active topic agent in parallel. `skill` is `draft` (default) or `patch`. `agents` is an optional comma-separated `role:topic` list. |
| `scripts/leads/run.sh {n}` | Run each role's lead review in parallel. |
| `scripts/cycle/run.sh {n} [max_rounds]` | One-stop cycle: drafts (initial round) or patches (subsequent rounds), then leads, then architect — loops until `approved.md` is created (or max rounds hit, default 10). |
| `scripts/executor/extract.sh {n}` | Pull `task:` entries from drafts into `plan/{n}/tasks.md`. |
| `scripts/executor/finish.sh {n} [--commit]` | Promote `plan/{n}/` into `final/`, regenerate trees, optionally commit. |
| `scripts/executor/finish-all.sh [--commit]` | Nuke `final/` and replay `finish.sh` for every iteration discovered from `plan/{n}.md`. Use after hand-editing drafts (new entries, renamed tags, path fixes) so `final/` matches the current drafts exactly. |
| `scripts/detect-llm.sh` | Probe LLM endpoints and emit `export` lines. Sourced by every runner; you can `eval "$(scripts/detect-llm.sh)"` yourself to see what it picked. |
| `scripts/llm-api.sh` | Shared API caller. Sourced by the runners; not run directly. |

## Full pipeline for an iteration

Export the LLM vars once per shell session (see above), then:

```bash
ITER=2

# 1. Plan — architect decomposes the request into plan/$ITER.md
scripts/architect/run.sh plan $ITER \
  "I need an admin user who can log in and manage other users"

# 2. Cycle — draft → lead → architect → patch, loops until approved.md exists.
#    Keep the max-rounds high — most iterations converge in 3–5 rounds but
#    25 leaves plenty of headroom.
scripts/cycle/run.sh $ITER 25

# 3. Extract executable task list
scripts/executor/extract.sh $ITER

# 4. Execute — run the executor agent (not a bash step)
#    Claude Code:   invoke the executor agent pointing at plan/$ITER/tasks.md
#    Agent SDK:     build a harness that reads tasks.md and writes source

# 5. Promote to final/ and optionally commit
scripts/executor/finish.sh $ITER --commit
```

## Individual steps

### Architect — plan or review

```bash
# Plan (request becomes the third arg)
scripts/architect/run.sh plan 2 "Add email verification and forgot-password flows"

# Review
scripts/architect/run.sh review 2
```

Outputs:

- `plan/{n}/raw/architect:{skill}.md` — full LLM response (audit trail)
- `plan/{n}.md` (for `plan`) OR
- `plan/{n}/corrections-verdict.md` + `plan/{n}/corrections.md` + `plan/{n}/decisions.md` (for `review`)
- `plan/{n}/approved.md` if the review found nothing to fix.

### Topic agents — draft or patch

```bash
# Draft every active topic agent in parallel
scripts/agents/run.sh 2

# Patch — only agents that have corrections in plan/{n}/{role}/lead.md
scripts/agents/run.sh 2 patch

# Draft just a subset (comma-separated role:topic list)
scripts/agents/run.sh 2 draft back-nestjs:api,front-nextjs:pages

# Rate-limited providers — cap parallelism and add a delay
MAX_PARALLEL=4 DELAY=3 scripts/agents/run.sh 2
```

Outputs:

- `plan/{n}/raw/{role}:{topic}.md` — full LLM response
- `plan/{n}/{role}/{topic}.md` — parsed entries (the working draft)

### Lead reviews

```bash
scripts/leads/run.sh 2
```

Runs one lead per role in parallel. Each lead reads its role's drafts and writes `plan/{n}/{role}/lead.md` (removed when clean).

### Cycle — patch loop until APPROVED

```bash
# Up to 5 rounds: patch → leads → architect → repeat
scripts/cycle/run.sh 2 5
```

Stops when `plan/{n}/approved.md` is created. Round-by-round logs live under `plan/{n}/logs/`.

### Executor extract / finish

```bash
scripts/executor/extract.sh 2          # drafts → tasks.md
scripts/executor/finish.sh  2 --commit # drafts → final/, regenerate trees, commit
```

`finish.sh --commit` runs `git add . && git commit -m "v84-${ITER}: promoted N entries"`.

When you hand-edit a draft after-the-fact (new entry, renamed tag, fixed path), a single-iteration `finish.sh` appends to `final/` without removing the now-stale prior entry. To rebuild the whole promoted history so it matches the drafts exactly:

```bash
scripts/executor/finish-all.sh             # nuke final/, replay every iteration
scripts/executor/finish-all.sh --commit    # same, with --commit per iteration
```

Iterations are discovered from `plan/{n}.md` files in numeric order, so new iterations are picked up automatically.

## Mix models per step (per-invocation overrides)

Inline the env var in front of the single call you want to route differently — no need to re-export for the rest of the shell. Cheap model for high-volume draft/patch, stronger model for architect-grade thinking:

```bash
# Session default: cheap fast model
export LLM_API_URL=http://192.168.1.66:8000/v1

# Drafts — use the session default (cheap local model)
scripts/agents/run.sh 2

# Plan + review — override to hosted Sonnet for this call only
LLM_PROVIDER=anthropic LLM_MODEL=claude-sonnet-4-5 LLM_API_KEY=$ANTHROPIC_KEY \
  scripts/architect/run.sh plan 2 "…"

LLM_PROVIDER=anthropic LLM_MODEL=claude-sonnet-4-5 LLM_API_KEY=$ANTHROPIC_KEY \
  scripts/architect/run.sh review 2

# Patches — back to the cheap session default
scripts/agents/run.sh 2 patch
```

`cycle/run.sh` detects once on its first round and reuses the detected values for every subsequent round, so a cycle command runs under one consistent provider without re-probing.

## Providers reference

| Provider value | Host | Notes |
|---|---|---|
| `anthropic` | `api.anthropic.com` | `LLM_API_KEY` required. Set `LLM_MODEL` (no auto-detect for Anthropic). |
| `openai` | `api.openai.com` (default) | `LLM_API_KEY` recommended. Set `LLM_API_URL` to point at Groq / Together / vLLM / LM Studio / any OpenAI-compatible host. |
| `ollama` | `localhost:11434` | no key; native Ollama API. |

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `LLM_API_URL` | auto-detected | Base URL of the LLM endpoint. First of `localhost:11434`, `localhost:11434/v1`, `localhost:8000/v1`, `localhost:1234/v1` that responds wins. Set explicitly to point at a remote host. |
| `LLM_PROVIDER` | auto-detected | `anthropic` / `openai` / `ollama`. Inferred from whichever endpoint probe succeeded. |
| `LLM_MODEL` | auto-detected | First model id the endpoint reports. Set explicitly to pin a specific model. |
| `LLM_API_KEY` | — | API key (required for `anthropic`, optional for `openai`, unused for `ollama`). |
| `MAX_PARALLEL` | 30 (agents), 4 (leads) | Concurrent LLM calls. |
| `MAX_TOKENS` | script-defined | Max output tokens per call. |
| `DELAY` | 0 | Seconds to wait between launching agents — useful for rate-limited APIs. |

## How the call path works

```
scripts/agents/run.sh
  ├── detect-llm.sh             # resolves LLM_API_URL / PROVIDER / MODEL (once)
  ├── build-context.sh          # ensures context/ is current
  ├── for each active topic (in parallel):
  │     ├── scripts/agents/call.sh   # sources llm-api.sh; calls the model
  │     │     → writes plan/{n}/raw/{role}:{topic}.md
  │     └── scripts/agents/parse.sh  # extracts clean entries
  │           → writes plan/{n}/{role}/{topic}.md
  └── done

scripts/leads/run.sh   — same call/parse pattern, one per role
scripts/architect/run.sh — same pattern, single call + post-review parsing
scripts/cycle/run.sh   — detects once, then loops agents → leads → architect
                         until approved.md appears (or max rounds hit)
```

No LLM reads files directly. All IO happens in bash; the model only sees text that the scripts pass in, and only writes text that the scripts parse.
