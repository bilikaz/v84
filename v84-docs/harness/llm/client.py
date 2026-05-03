#!/usr/bin/env python3
"""
client.py — LLM client for the v84 harness.

One wire format: OpenAI-compatible chat completions. Anthropic, OpenAI,
Qwen (via vLLM), Ollama, LM Studio — every provider we care about speaks
this format. No native Anthropic API.

Public API (what the rest of the harness calls):

    detect() -> LLMConfig             — find a reachable endpoint
    call_json(cfg, system, user_msgs, response_schema, ...)
                                       — schema-constrained chat
                                         completion; returns the parsed
                                         JSON value matching the schema

Schema-constrained sampling — vLLM (xgrammar), OpenAI, Anthropic-via-shim
all enforce the JSON Schema at sampling time. The model cannot emit
non-conforming JSON, so there is no marker, no YAML, no post-hoc
validation. Network/transport failures still get the standard
transient-retry treatment.

Zero external dependencies. Standard library only (PyYAML is consulted
elsewhere — not here).
"""

# `from __future__ import annotations` delays evaluation of type hints so
# `list[str]` works on Python 3.9+ without importing `List` from typing.
from __future__ import annotations

import json
import os
import sys
import threading
import time
import zlib

import urllib.error
import urllib.request

import yaml


# -----------------------------------------------------------------------------
# Loop detection — kill calls whose `reasoning_content` keeps recycling.
# -----------------------------------------------------------------------------
# Compress a sliding 3000-char window of the latest reasoning every 1500
# new chars (50% overlap: [0,3000], [1500,4500], [3000,6000], ...). Healthy
# prose compresses ~50–60%; phrase-anchored loops compress under ~25%
# regardless of paraphrasing because zlib's LZ-style backreferences pick
# up on shared n-grams. Three sub-threshold windows in a row = kill.
#
# Why these numbers:
#   - WINDOW = 3000 catches loop cycles up to ~1000 chars (need 2 cycles
#     to compress, plus headroom). Most paraphrase loops cycle every
#     100–500 chars so this is plenty.
#   - STEP = WINDOW/2 makes consecutive checks 50%-overlapping; one bad
#     window passing through the buffer triggers all three checks.
#   - THRESHOLD = 0.30 sits comfortably below dense English prose
#     (typically 0.45–0.60) and well above heavy repetition (0.10–0.20).
#   - STREAK = 3 means the loop must persist across 3000 + 2×1500 = 6000
#     chars before kill — enough to rule out a single compressible chunk.
LOOP_WINDOW = 3000
LOOP_STEP = LOOP_WINDOW // 2
LOOP_RATIO_THRESHOLD = 0.30
LOOP_BAD_STREAK = 3

# Hard wall-clock ceiling on a single SSE stream. Belt-and-suspenders
# against pathological cases the loop detector misses (very-long-cycle
# paraphrase loops, server-side bugs, weird streaming patterns). The
# `urlopen(timeout=...)` only catches idle reads — a server that keeps
# emitting bytes forever never hits it. This check runs once per
# delta inside the SSE loop and aborts when the cap is exceeded.
MAX_STREAM_S = 1200
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# Global tracker for in-flight streams. When only one stream is active
# AND stderr is a tty, the per-call emitter uses `\r` to overwrite a
# single line in place (clean ticker display). When 2+ streams run in
# parallel, the emitter falls back to newline-per-line because in-place
# updates would garble each other.
_STREAM_LOCK = threading.Lock()
_STREAM_COUNT = 0
_STDERR_IS_TTY = sys.stderr.isatty()


# Global in-flight cap. Every `_post` acquires a slot before opening the
# SSE stream and releases when the stream ends. The cap is the largest
# `cfg.max_concurrency` any caller has presented so far (lazy grow). With
# many stages firing call_many concurrently, this prevents each one's
# local pool from stacking on top of the others' — total simultaneous
# requests against the endpoint stay bounded by the multi-tier cap.
_INFLIGHT_COND = threading.Condition()
_INFLIGHT_COUNT = 0
_INFLIGHT_CAP = 0  # 0 means "no cap registered yet" — first call sets it.


def _acquire_inflight(cap: int) -> None:
    """Block until a slot is free under the global cap, then take one.

    `cap` is the caller's `cfg.max_concurrency`. The global cap grows
    monotonically: if a caller arrives with a higher cap than what's
    set, the cap is raised (and waiters are woken) so multi-tier
    fan-outs aren't bottlenecked by an earlier single-tier call.
    """
    global _INFLIGHT_COUNT, _INFLIGHT_CAP
    cap = max(1, cap)
    with _INFLIGHT_COND:
        if cap > _INFLIGHT_CAP:
            _INFLIGHT_CAP = cap
            _INFLIGHT_COND.notify_all()
        while _INFLIGHT_COUNT >= _INFLIGHT_CAP:
            _INFLIGHT_COND.wait()
        _INFLIGHT_COUNT += 1


def _release_inflight() -> None:
    global _INFLIGHT_COUNT
    with _INFLIGHT_COND:
        _INFLIGHT_COUNT -= 1
        _INFLIGHT_COND.notify()


# Closing tag for reasoning blocks. Thinking models (Qwen3, DeepSeek-R1,
# etc.) end their reasoning with </think> and only sometimes open with
# <think> — several models start reasoning implicitly and just signal the
# end. So we look for the closing tag alone. Used defensively in
# call_json: vLLM puts thinking in `reasoning_content` already, but other
# providers may inline it into `content`.
THINK_CLOSE = "</think>"


# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

@dataclass
class LLMConfig:
    """Everything needed to make a call.

    url               base endpoint up to /v1 (e.g. https://api.openai.com/v1)
    model             model id the endpoint reported (or user-overridden)
    api_key           Bearer token; None for unauthenticated local LLMs
    max_concurrency   how many calls may run in parallel against this
                      endpoint. 1 for the single tier; multi tier may
                      raise it via profile.yaml's `llm.<tier>.max_concurrency`.
    retries           how many transient-failure attempts to make per
                      call before giving up (network errors, timeouts,
                      HTTP 5xx, malformed JSON envelope from the server).
                      Schema-constrained calls don't add their own retry
                      layer — the model can't emit invalid output.
                      Set per tier in profile.yaml's `llm.<tier>.retries`.
    """
    url: str
    model: str
    api_key: Optional[str] = None
    max_concurrency: int = 1
    retries: int = 3


# -----------------------------------------------------------------------------
# Endpoint probe — used by config.py to validate a URL and pick a model
# -----------------------------------------------------------------------------

def _probe_models(url: str, api_key: Optional[str]) -> Optional[str]:
    """GET {url}/models → return first model id, or None on any failure.

    We only need the model id; the rest of the response is ignored.
    """
    endpoint = f"{url.rstrip('/')}/models"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(endpoint, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, TimeoutError, OSError):
        return None

    models = data.get("data") or []
    if models and isinstance(models, list):
        first = models[0]
        if isinstance(first, dict):
            return first.get("id")
    return None


# -----------------------------------------------------------------------------
# Request body + HTTP plumbing
# -----------------------------------------------------------------------------

def _build_body(
    cfg: LLMConfig,
    messages: list[dict[str, Any]],
    *,
    response_schema: Optional[dict] = None,
    max_tokens: int = 60_000,
) -> dict[str, Any]:
    """Construct the JSON body for a chat/completions POST."""
    body: dict[str, Any] = {
        "model": cfg.model,
        "messages": messages,
        "max_tokens": max_tokens,
        # Always streamed. `_post` consumes the SSE chunks, accumulates
        # them, and emits periodic tail snapshots to stderr so a long
        # call's progress is visible in the terminal where the harness
        # is running.
        "stream": True,
        # vLLM-specific: enable reasoning in the chat template AND keep
        # special tokens in the output so </think> actually appears.
        # Without skip_special_tokens=false, vLLM strips the tags and we
        # can't tell where thinking ends and the real response begins.
        # OpenAI and other hosted providers ignore unknown fields; if a
        # hosted provider complains, set LLM_NO_THINKING=1 to suppress.
        "chat_template_kwargs": {"enable_thinking": True},
        "skip_special_tokens": False,
        # Qwen3 thinking-mode sampling (per the model card). Sent
        # explicitly so behaviour doesn't drift with server-side
        # defaults (vLLM versions, hosted templates, etc.). Hosted
        # providers that don't recognise some fields generally ignore
        # them; if a provider hard-errors, set LLM_NO_THINKING=1 which
        # also strips the vLLM-only thinking knobs above.
        #
        # `presence_penalty` deviates from Qwen's 0.0 default: their
        # docs say "for longer responses (32K+), consider increasing
        # presence_penalty between 0 and 2 to reduce endless
        # repetitions." We've seen 80k+ thinking runs that wandered
        # without converging; 1.0 sits mid-band and pushes the model
        # to commit instead of re-deliberating.
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 20,
        "min_p": 0.0,
        "presence_penalty": 1.0,
        "repetition_penalty": 1.0,
    }
    if os.getenv("LLM_NO_THINKING"):
        body.pop("chat_template_kwargs", None)
        body.pop("skip_special_tokens", None)
    if response_schema is not None:
        # Basic JSON-validity mode. Qwen docs are explicit: thinking
        # models don't support `json_schema` — schema-constrained
        # sampling blocks tokens during reasoning and the model never
        # emits the final answer (empty content, finish_reason=length).
        # `json_object` mode just enforces "valid JSON", which thinking
        # models handle. The schema goes into the system prompt instead
        # of response_format. The model still sees it; we lose
        # sampling-time enforcement and rely on prompt + parser.
        body["response_format"] = {"type": "json_object"}
    return body


def _post(
    cfg: LLMConfig,
    body: dict[str, Any],
    *,
    log_name: Optional[str] = None,
    log_dir: Optional[Path] = None,
    on_stream: Optional[Any] = None,
) -> dict:
    """POST a chat/completions request and consume the SSE stream.

    Returns a response dict shaped like the non-streaming OpenAI form
    (`{"choices": [{"message": {...}, "finish_reason": ...}]}`) so the
    rest of the harness doesn't need to know streaming happened.

    Side-effect: prints a per-call status line to stderr at start, a
    tail snapshot every ~3s or every ~500 chars of content, and a
    final completion line. Lets you watch long calls in the terminal
    and notice when garbage starts showing up.

    Pending-log is written before the network call so a hang is
    inspectable; the full log is written when the stream completes.
    """
    endpoint = f"{cfg.url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=data, headers=headers, method="POST",
    )

    if log_name and log_dir:
        _write_log(log_dir, log_name, cfg, body)

    label = log_name or "stream"
    # Block here if we're already at the global cap. Acquired before
    # `started` is sampled so wait time isn't charged against the call's
    # observed latency.
    _acquire_inflight(cfg.max_concurrency)
    started = time.monotonic()
    global _STREAM_COUNT
    with _STREAM_LOCK:
        _STREAM_COUNT += 1
    in_place_emitted = False
    # When a per-call streaming hook is supplied (the global spinner
    # via call_many / call_json is the canonical caller), all live
    # output is owned by the spinner. The stderr "sent / tail / done"
    # lines would corrupt the spinner's in-place paint, so we suppress
    # them entirely.
    quiet = on_stream is not None
    if not quiet:
        print(f"  → [{label}] sent", file=sys.stderr, flush=True)

    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    finish_reason: Optional[str] = None
    last_emit_at = started
    last_emit_chars = 0
    EMIT_EVERY_S = 1.0
    EMIT_EVERY_CHARS = 200

    # Loop-detection state. `loop_next_check_at` is the reasoning-length
    # threshold at which the next compression check fires; advances by
    # LOOP_STEP each fire so consecutive windows overlap by 50%. The
    # latest ratio + bad-streak count are surfaced through emit_tail()
    # so the spinner can render them live.
    loop_next_check_at = LOOP_WINDOW
    loop_bad_streak = 0
    loop_last_ratio: Optional[float] = None

    def emit_tail() -> None:
        nonlocal in_place_emitted
        content = "".join(content_parts)
        reasoning = "".join(reasoning_parts)
        elapsed = time.monotonic() - started
        phase = "writing" if content else "thinking"
        tail_src = content if content else reasoning
        # Keep the tail short — the spinner prints one row per call,
        # and a long tail can wrap past the terminal width which breaks
        # the painter's cursor accounting (it walks up `cap` lines but
        # each wrapped row consumed 2+ terminal rows). 10 chars is
        # enough to confirm the call is producing fresh tokens.
        tail = tail_src[-10:].replace("\n", "↵")
        # Spinner-owned mode: hand the snapshot to the caller's hook
        # and emit nothing to stderr.
        if on_stream is not None:
            try:
                on_stream(
                    phase=phase,
                    content=len(content),
                    reasoning=len(reasoning),
                    tail=tail,
                    loop_ratio=loop_last_ratio,
                    loop_streak=loop_bad_streak,
                )
            except Exception:  # noqa: BLE001
                pass
            return

        loop_tag = ""
        if loop_last_ratio is not None:
            loop_tag = (
                f" loop:{loop_last_ratio:.2f}"
                f"({loop_bad_streak}/{LOOP_BAD_STREAK})"
            )
        if content:
            line = (
                f"  ░ [{label}] {elapsed:5.1f}s writing — "
                f"think:{len(reasoning):,}c content:{len(content):,}c"
                f"{loop_tag} ▶ {tail!r}"
            )
        else:
            line = (
                f"  ░ [{label}] {elapsed:5.1f}s thinking — "
                f"think:{len(reasoning):,}c{loop_tag} ▶ {tail!r}"
            )
        with _STREAM_LOCK:
            alone = _STREAM_COUNT == 1
        if alone and _STDERR_IS_TTY:
            sys.stderr.write(f"\r\033[K{line}")
            sys.stderr.flush()
            in_place_emitted = True
        else:
            if in_place_emitted:
                sys.stderr.write("\n")
                in_place_emitted = False
            print(line, file=sys.stderr, flush=True)

    try:
        try:
            # 1200s connect/read ceiling. The stream itself can run as
            # long as the server keeps sending; this caps an idle stall.
            with urllib.request.urlopen(req, timeout=1200) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[len("data:"):].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    try:
                        delta = chunk["choices"][0].get("delta") or {}
                    except (KeyError, IndexError, TypeError):
                        continue
                    c = delta.get("content")
                    # vLLM uses `reasoning` in streaming deltas;
                    # non-streaming uses `reasoning_content`. Accept both.
                    r = delta.get("reasoning_content") or delta.get("reasoning")
                    if c:
                        content_parts.append(c)
                    if r:
                        reasoning_parts.append(r)
                    fr = chunk["choices"][0].get("finish_reason")
                    if fr:
                        finish_reason = fr

                    now = time.monotonic()
                    # Total chars across BOTH streams so the cadence
                    # triggers during pure thinking too.
                    total_chars = (
                        sum(len(p) for p in content_parts)
                        + sum(len(p) for p in reasoning_parts)
                    )

                    # Wall-clock kill — catches active-but-runaway
                    # streams that the urlopen idle timeout misses
                    # (server keeps emitting bytes forever). Fires once
                    # MAX_STREAM_S elapsed, regardless of phase or
                    # whether content has started arriving.
                    if now - started > MAX_STREAM_S:
                        emit_tail()
                        raise StreamTimeoutError(
                            f"stream exceeded MAX_STREAM_S={MAX_STREAM_S}s "
                            f"(elapsed {now - started:.0f}s, "
                            f"think:{sum(len(p) for p in reasoning_parts):,}c "
                            f"content:{sum(len(p) for p in content_parts):,}c)"
                        )

                    # Loop check — only meaningful during pure-thinking
                    # phase (content recycles legit JSON shapes). Fires
                    # once per LOOP_STEP chars of new reasoning, each
                    # check covering the trailing LOOP_WINDOW chars
                    # (50% overlap with previous check).
                    if not content_parts:
                        reasoning_len = sum(len(p) for p in reasoning_parts)
                        if reasoning_len >= loop_next_check_at:
                            loop_next_check_at = (
                                reasoning_len + LOOP_STEP
                            )
                            window = "".join(reasoning_parts)[-LOOP_WINDOW:]
                            buf = window.encode("utf-8")
                            ratio = len(zlib.compress(buf)) / len(buf)
                            loop_last_ratio = ratio
                            if ratio < LOOP_RATIO_THRESHOLD:
                                loop_bad_streak += 1
                            else:
                                loop_bad_streak = 0
                            if loop_bad_streak >= LOOP_BAD_STREAK:
                                # Render one final tail snapshot so the
                                # spinner / stderr shows the kill state
                                # before the exception unwinds.
                                emit_tail()
                                raise LoopAbortError(
                                    f"loop detected after "
                                    f"{reasoning_len:,} chars of reasoning "
                                    f"(ratio {ratio:.2f} for "
                                    f"{loop_bad_streak} consecutive "
                                    f"{LOOP_WINDOW}-char windows)"
                                )

                    if (now - last_emit_at >= EMIT_EVERY_S
                            or total_chars - last_emit_chars >= EMIT_EVERY_CHARS):
                        last_emit_at = now
                        last_emit_chars = total_chars
                        emit_tail()
        except StreamKilledError as exc:
            # Persist what was produced before the kill so we can audit
            # which loops / timeouts survive long enough to trigger and
            # what they looked like. Filename carries a `killed-` prefix
            # so the run sorts away from successful ones at a glance.
            # The reason in `finish_reason` distinguishes the kind so a
            # post-run scan can group them (loop vs timeout).
            if log_name and log_dir:
                kind = (
                    "killed-timeout"
                    if isinstance(exc, StreamTimeoutError)
                    else "killed-loop"
                )
                killed_response = {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": "".join(content_parts),
                            "reasoning_content": "".join(reasoning_parts),
                        },
                        "finish_reason": kind,
                    }],
                }
                _write_log(
                    log_dir, f"killed-{log_name}", cfg, body, killed_response,
                )
            if not quiet:
                if in_place_emitted:
                    sys.stderr.write("\n")
                    in_place_emitted = False
                print(
                    f"  ✗ [{label}] killed: {exc}",
                    file=sys.stderr, flush=True,
                )
            raise
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            if exc.code >= 500 or exc.code in (408, 429):
                raise TransientLLMError(
                    f"LLM API {exc.code}: {err_body}"
                ) from exc
            raise RuntimeError(f"LLM API error {exc.code}: {err_body}") from exc
        except urllib.error.URLError as exc:
            raise TransientLLMError(
                f"LLM network error: {exc.reason}"
            ) from exc
        except (TimeoutError,) as exc:
            raise TransientLLMError(f"LLM transport: {exc}") from exc
    finally:
        # Always close the in-place line (if any) before continuing,
        # and decrement the in-flight counter so other streams in this
        # process can switch back to in-place mode when they're alone.
        if in_place_emitted:
            sys.stderr.write("\n")
            sys.stderr.flush()
        with _STREAM_LOCK:
            _STREAM_COUNT -= 1
        # Release the global concurrency slot last so a waiting caller
        # can immediately take it without racing the spinner cleanup.
        _release_inflight()

    elapsed = time.monotonic() - started
    content = "".join(content_parts)
    reasoning = "".join(reasoning_parts)
    if not quiet:
        print(
            f"  ✓ [{label}] {elapsed:.1f}s — content:{len(content):,}c "
            f"think:{len(reasoning):,}c finish={finish_reason}",
            file=sys.stderr, flush=True,
        )

    response = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": content,
                "reasoning_content": reasoning,
            },
            "finish_reason": finish_reason,
        }],
    }

    if log_name and log_dir:
        _write_log(log_dir, log_name, cfg, body, response)

    return response


class TransientLLMError(RuntimeError):
    """Network / server / transport failure that may succeed on retry.
    Caught + retried by `_post_with_retry` with linear backoff."""


class StreamKilledError(TransientLLMError):
    """Base for in-stream kills (loop detected, wall-clock timeout). All
    subclasses get the same `killed-`-prefixed log treatment so we can
    audit what produced the kill regardless of the trigger."""


class LoopAbortError(StreamKilledError):
    """Reasoning loop detected — the model kept recycling the same phrases
    instead of converging on output. Treated as transient (most loops are
    sampling-variance bugs that don't recur on a fresh roll)."""


class StreamTimeoutError(StreamKilledError):
    """Wall-clock cap (MAX_STREAM_S) exceeded on a single stream. The
    `urlopen` per-read timeout only catches idle sockets — this check
    catches active-but-runaway streams (e.g. paraphrase loops the
    compressor missed)."""


def _post_with_retry(
    cfg: LLMConfig,
    body: dict[str, Any],
    *,
    attempt_label: str,
    log_name: Optional[str],
    log_dir: Optional[Path],
    on_stream: Optional[Any] = None,
) -> dict:
    """Wrap _post with cfg.retries transient-failure retries.

    Backoff between attempts is linear (2s, 4s, 6s, ...). Each retry
    re-runs the same POST; if every attempt raises a TransientLLMError,
    the last one is re-raised as a plain RuntimeError so the caller's
    higher-level loop doesn't keep retrying.
    """
    last: Optional[Exception] = None
    for attempt in range(1, cfg.retries + 1):
        try:
            return _post(
                cfg, body,
                log_name=log_name, log_dir=log_dir,
                on_stream=on_stream,
            )
        except TransientLLMError as exc:
            last = exc
            if attempt < cfg.retries:
                backoff = 2 * attempt
                print(
                    f"WARN  transient LLM failure on {attempt_label} "
                    f"attempt {attempt}/{cfg.retries}: {exc} "
                    f"— retrying in {backoff}s",
                    file=sys.stderr, flush=True,
                )
                time.sleep(backoff)
    raise RuntimeError(
        f"LLM call failed after {cfg.retries} transient retries: {last}"
    ) from last


# -----------------------------------------------------------------------------
# Calls
# -----------------------------------------------------------------------------

def call_json(
    cfg: LLMConfig,
    system: str,
    user_msgs: list[str],
    response_schema: dict,
    *,
    max_tokens: int = 60_000,
    log_name: Optional[str] = None,
    log_dir: Optional[Path] = None,
    on_stream: Optional[Any] = None,
) -> Any:
    """Run a chat completion that returns parsed JSON.

    Returns the parsed JSON value (dict, list, etc.). The schema is
    appended to the system prompt as a JSON block plus a literal
    example. `response_format: json_object` enforces JSON validity at
    the server. Schema shape is hint-only (no sampling constraint)
    because thinking models don't support schema-mode on Qwen/vLLM.

    Retries up to `cfg.retries` times on JSON-parse failure or schema-
    validation failure. Each attempt re-sends the original messages
    verbatim — no feedback, no echo of the bad output. The model
    samples afresh; sampling variance carries us across most one-off
    formatting slips. Network/transport failures are retried
    separately by `_post_with_retry` inside each attempt.

    Reasoning still works: vLLM puts thinking in `reasoning_content`
    (separate field), and the JSON in `content`. If a non-vLLM
    provider inlines `</think>` into `content`, we strip it
    defensively before json.loads.

    Progress UI: if the caller doesn't supply `on_stream`, this
    function auto-attaches a row to `ui.spinner.GLOBAL` for the
    full life of the call (across retries) and unregisters it on
    return/raise after a brief grace period. `call_many` always
    supplies its own `on_stream`, so its rows aren't duplicated here.
    """
    return _call_json_with_spinner(
        cfg, system, user_msgs, response_schema,
        max_tokens=max_tokens,
        log_name=log_name, log_dir=log_dir,
        on_stream=on_stream,
    )


def _call_json_with_spinner(
    cfg: LLMConfig,
    system: str,
    user_msgs: list[str],
    response_schema: dict,
    *,
    max_tokens: int,
    log_name: Optional[str],
    log_dir: Optional[Path],
    on_stream: Optional[Any],
) -> Any:
    """Wrap `_call_json_impl` with auto-attach to the global spinner
    when no `on_stream` is provided. Splitting this out keeps the
    schema/retry logic readable in `_call_json_impl`."""
    auto_rid: Optional[int] = None
    captured_error: Optional[BaseException] = None
    if on_stream is None:
        # Lazy import — avoid pulling ui at module import time.
        from ui import spinner as _sp
        auto_rid = _sp.GLOBAL.register(log_name or "call")
        _sp.GLOBAL.started(auto_rid)

        def _hook(**kw: Any) -> None:
            try:
                _sp.GLOBAL.stream_update(auto_rid, **kw)
            except Exception:  # noqa: BLE001 — UI must not abort the call
                pass
        on_stream = _hook

    try:
        return _call_json_impl(
            cfg, system, user_msgs, response_schema,
            max_tokens=max_tokens,
            log_name=log_name, log_dir=log_dir,
            on_stream=on_stream,
        )
    except BaseException as exc:
        captured_error = exc
        raise
    finally:
        if auto_rid is not None:
            from ui import spinner as _sp
            _sp.GLOBAL.done(auto_rid, error=captured_error)
            # Brief grace so the operator sees the final ✓/✗ before
            # the row disappears, matching call_many's behaviour.
            time.sleep(0.5)
            _sp.GLOBAL.unregister(auto_rid)


def _call_json_impl(
    cfg: LLMConfig,
    system: str,
    user_msgs: list[str],
    response_schema: dict,
    *,
    max_tokens: int = 60_000,
    log_name: Optional[str] = None,
    log_dir: Optional[Path] = None,
    on_stream: Optional[Any] = None,
) -> Any:
    """Schema-checked call_json body. Always invoked through
    `_call_json_with_spinner` (which is what `call_json` exports)."""
    augmented_system = (
        f"{system}\n\n"
        f"## Response format\n\n"
        f"{_response_format_block(response_schema)}"
    )
    base_messages: list[dict[str, Any]] = [{"role": "system", "content": augmented_system}]
    for msg in user_msgs:
        base_messages.append({"role": "user", "content": msg})

    last_failure: Optional[str] = None
    for attempt in range(1, cfg.retries + 1):
        attempt_log = (
            f"{log_name}-a{attempt}" if log_name and cfg.retries > 1 else log_name
        )
        body = _build_body(
            cfg, base_messages,
            response_schema=response_schema,
            max_tokens=max_tokens,
        )
        response = _post_with_retry(
            cfg, body,
            attempt_label=attempt_log or "call_json",
            log_name=attempt_log, log_dir=log_dir,
            on_stream=on_stream,
        )

        try:
            raw = response["choices"][0]["message"].get("content", "") or ""
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(
                f"LLM response missing choices/message (log: {attempt_log})"
            )

        text, fence_tag = _strip_code_fence(_strip_thinking(raw))

        # YAML fallback — the model occasionally mirrors the YAML it
        # received on the input side, either as ```yaml-fenced output
        # or as a bare YAML body. `yaml.safe_load` recovers the same
        # dict shape the schema expects, so we accept it instead of
        # forcing a retry. JSON is a YAML subset, so when the body
        # parses cleanly as JSON we still go through json.loads first
        # for a more precise error on malformed input.
        try:
            if fence_tag == "yaml":
                value = yaml.safe_load(text)
            else:
                try:
                    value = json.loads(text)
                except json.JSONDecodeError:
                    yaml_value = yaml.safe_load(text)
                    if not isinstance(yaml_value, (dict, list)):
                        raise
                    value = yaml_value
        except (json.JSONDecodeError, yaml.YAMLError) as exc:
            last_failure = f"unparseable content ({fence_tag or 'json'}): {exc}"
            if attempt < cfg.retries:
                preview = _preview(text)
                print(
                    f"WARN  {last_failure} on attempt "
                    f"{attempt}/{cfg.retries} (log: {attempt_log}) "
                    f"— retrying...\n"
                    f"      content begins:{preview}",
                    file=sys.stderr, flush=True,
                )
                continue
            preview = _preview(text)
            raise RuntimeError(
                f"call_json got unparseable content after {cfg.retries} "
                f"attempts (log: {attempt_log}): {exc}\n"
                f"      content begins:{preview}"
            ) from exc

        errors = _validate_against_schema(value, response_schema)
        if not errors:
            return value

        joined = "\n      - ".join(errors[:8])
        last_failure = f"schema validation: {len(errors)} error(s)"
        if attempt < cfg.retries:
            print(
                f"WARN  {last_failure} on attempt "
                f"{attempt}/{cfg.retries} (log: {attempt_log}) "
                f"— retrying...\n"
                f"      - {joined}",
                file=sys.stderr, flush=True,
            )
            continue
        raise RuntimeError(
            f"call_json response did not match schema after {cfg.retries} "
            f"attempts (log: {attempt_log}):\n      - {joined}"
        )

    # Defensive — loop body either returns or raises.
    raise RuntimeError(
        f"call_json exhausted {cfg.retries} attempts (log: {log_name}): {last_failure}"
    )


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _validate_against_schema(value: Any, schema: dict) -> list[str]:
    """Validate a parsed JSON value against our JSON Schema subset.

    Returns a list of human-readable error messages (each pointing at
    the failing path); empty list means the value matches.

    Subset supported (covers every v84 stage schema):
        type:                 object | array | string | integer |
                              number | boolean | null
        properties:           per-key sub-schemas
        required:             list of property names
        additionalProperties: bool (false → unknown keys reject)
                              or sub-schema (each unknown key validated)
        items:                sub-schema for every element
        enum:                 list of allowed literal values
        $ref / $defs:         #/$defs/<name> for recursive definitions

    Format keywords like minLength/pattern/format are NOT enforced.
    Lost server-side because thinking models can't use json_schema mode;
    this restores the equivalent post-hoc check on what came back.
    """
    return list(_iter_validate(value, schema, schema, "$"))


def _iter_validate(
    value: Any, schema: dict, root: dict, path: str,
):
    # $ref → resolve against the root and recurse.
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/"):
        target: Any = root
        for part in ref[2:].split("/"):
            if not isinstance(target, dict) or part not in target:
                yield f"{path}: unresolved $ref {ref!r}"
                return
            target = target[part]
        yield from _iter_validate(value, target, root, path)
        return

    # enum constrains all types — check first.
    if "enum" in schema and value not in schema["enum"]:
        yield f"{path}: {value!r} not in {schema['enum']!r}"
        return

    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, dict):
            yield f"{path}: expected object, got {_typename(value)}"
            return
        props = schema.get("properties") or {}
        required = schema.get("required") or []
        for key in required:
            if key not in value:
                yield f"{path}.{key}: required field missing"
        addl = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in props:
                yield from _iter_validate(item, props[key], root, f"{path}.{key}")
            elif addl is False:
                yield f"{path}.{key}: unexpected field (additionalProperties=false)"
            elif isinstance(addl, dict):
                yield from _iter_validate(item, addl, root, f"{path}.{key}")
        return

    if expected == "array":
        if not isinstance(value, list):
            yield f"{path}: expected array, got {_typename(value)}"
            return
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(value):
                yield from _iter_validate(item, item_schema, root, f"{path}[{i}]")
        return

    if expected == "string":
        if not isinstance(value, str):
            yield f"{path}: expected string, got {_typename(value)}"
        return
    if expected == "integer":
        # bool is a subclass of int — exclude it explicitly.
        if isinstance(value, bool) or not isinstance(value, int):
            yield f"{path}: expected integer, got {_typename(value)}"
        return
    if expected == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            yield f"{path}: expected number, got {_typename(value)}"
        return
    if expected == "boolean":
        if not isinstance(value, bool):
            yield f"{path}: expected boolean, got {_typename(value)}"
        return
    if expected == "null":
        if value is not None:
            yield f"{path}: expected null, got {_typename(value)}"
        return
    # No `type` keyword — accept anything (after enum check above).


def _typename(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _response_format_block(schema: dict) -> str:
    """Build the system-prompt suffix that tells the model to emit JSON.

    Components, in order:
        1. The hard rule: return only JSON.
        2. A one-line shape summary listing top-level keys.
        3. A literal example response (from schema.examples[0]) when
           present — much more concrete than the schema alone for
           weak models.
        4. The full JSON Schema as a fenced block, for the cases the
           example doesn't cover.
    """
    parts: list[str] = [
        "Return only JSON. No prose, no explanation, no markdown "
        "fences around the response.",
        "",
        _shape_summary(schema),
    ]

    examples = schema.get("examples") or []
    for entry in examples:
        title = entry.get("title", "")
        example_json = json.dumps(entry.get("example"), indent=2)
        parts.extend([
            "",
            f"### {title}" if title else "### Example",
            "",
            f"```json\n{example_json}\n```",
        ])

    # Strip `examples` from the dump — they're already shown above as
    # the labelled example block. Including them here would just bloat
    # the prompt with the same JSON twice.
    schema_for_dump = {k: v for k, v in schema.items() if k != "examples"}
    schema_json = json.dumps(schema_for_dump, indent=2)
    parts.extend([
        "",
        "Full schema (every field, every constraint):",
        "",
        f"```json\n{schema_json}\n```",
    ])
    return "\n".join(parts) + "\n"


def _shape_summary(schema: dict) -> str:
    """Explicit description of the top-level shape and required keys.

    Models tend to wrap top-level arrays in an object (e.g.
    `{"items": [...]}`) when asked for "JSON" with no other signal.
    The array case is spelled out with an example to make the wrapper
    instinct backfire.
    """
    t = schema.get("type")
    if t == "object":
        props = schema.get("properties") or {}
        if not props:
            return "Top-level: a single JSON object."
        keys = ", ".join(f"`{k}`" for k in props.keys())
        return f"Top-level: a JSON object with keys {keys}."
    if t == "array":
        item = schema.get("items") or {}
        item_props = item.get("properties") or {}
        if item.get("type") == "object" and item_props:
            keys = ", ".join(f"`{k}`" for k in item_props.keys())
            return (
                "Top-level: a bare JSON array. Do NOT wrap the array "
                "in an object. The very first character of your "
                "response must be `[`. Each array element is an "
                f"object with keys {keys}.\n"
                "Example shape: `[{...}, {...}]`."
            )
        return (
            "Top-level: a bare JSON array. Do NOT wrap the array in "
            "an object. The very first character of your response "
            "must be `[`."
        )
    return f"Top-level: {t or 'see schema below'}."


def _strip_code_fence(text: str) -> tuple[str, str]:
    """Remove a leading ```<tag> fence and trailing ``` if present.

    Returns `(body, tag)` — `tag` is the lowercased fence label
    (`json`, `yaml`, …) or `""` when no fence (or no label) was
    found. The tag drives parser selection in `call_json`: models
    trained on YAML inputs occasionally mirror the format on output,
    and `yaml.safe_load` recovers the dict at zero retry cost
    instead of forcing a re-roll.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped, ""
    # Tag = whatever follows ``` up to the first newline. Empty when
    # the model emits a bare ``` fence with no label.
    first_newline = stripped.find("\n")
    if first_newline == -1:
        return stripped, ""
    tag = stripped[3:first_newline].strip().lower()
    body = stripped[first_newline + 1:]
    body = body.rstrip()
    if body.endswith("```"):
        body = body[:-3].rstrip()
    return body, tag


def _strip_thinking(text: str) -> str:
    """Drop everything up to and including </think>, left-trim the rest.

    Many thinking models (Qwen3, several DeepSeek variants) emit only
    the closing tag — they begin reasoning implicitly and mark its end
    with </think>. So we search for the close tag alone, not paired
    with <think>. If the close tag is absent (non-thinking model, or
    the response came back directly), we return the text unchanged
    apart from left-trimming.
    """
    idx = text.find(THINK_CLOSE)
    if idx == -1:
        return text.lstrip()
    return text[idx + len(THINK_CLOSE):].lstrip()


def _preview(text: str, *, limit: int = 400) -> str:
    """Length-capped preview of model output for WARN/error messages.

    Keeps newlines so multiline/single-line shape is visible — tabs and
    other whitespace runs are collapsed to a single space per line, so
    a model that emits one giant unwrapped line stays distinguishable
    from one that uses proper indentation.
    """
    cleaned = "\n".join(
        " ".join(line.split()) for line in text.splitlines()
    ).strip()
    if len(cleaned) > limit:
        cleaned = cleaned[:limit] + "…"
    return "\n      | " + cleaned.replace("\n", "\n      | ")


def _write_log(log_dir: Path, name: str, cfg: LLMConfig,
               request: dict, response: Optional[dict] = None) -> None:
    """Persist a request (and optionally the response streams) for audit.

    Without `response`: writes `<name>-pending.json` (stable filename so
    the next call overwrites it). Lets operators inspect the in-flight
    request if the call hangs.

    With `response`: writes three sibling files keyed by the same
    timestamp:
        <name>-<ts>.json          ← the request (what we sent)
        <name>-<ts>.md            ← message.content verbatim
        <name>-<ts>.thinking.md   ← message.reasoning_content verbatim

    No concatenation, no markers, no transformation — each file is
    exactly the bytes of one source field, so a reviewer can tell
    request from content from thinking by filename alone. Removes any
    leftover pending marker.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": cfg.model,
        "url": cfg.url,
        "status": "complete" if response is not None else "pending",
        "request": request,
    }
    if response is not None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = log_dir / f"{name}-{ts}.json"
        pending = log_dir / f"{name}-pending.json"
        if pending.exists():
            pending.unlink()
        try:
            msg_obj = response["choices"][0]["message"]
            content = msg_obj.get("content") or ""
            reasoning = msg_obj.get("reasoning_content") or ""
        except (KeyError, IndexError, TypeError):
            content = ""
            reasoning = ""
        if content:
            (log_dir / f"{name}-{ts}.md").write_text(content, encoding="utf-8")
        if reasoning:
            (log_dir / f"{name}-{ts}.thinking.md").write_text(
                reasoning, encoding="utf-8",
            )
    else:
        out = log_dir / f"{name}-pending.json"

    out.write_text(json.dumps(entry, indent=2), encoding="utf-8")


# -----------------------------------------------------------------------------
# Self-test CLI
# -----------------------------------------------------------------------------
# Run this file directly to verify the configured endpoint works:
#     python3 harness/llm/client.py
#     python3 harness/llm/client.py --test "say hi in five words"
#
# Resolves config via the same path as the harness (profile.yaml +
# bootstrap cache + interactive prompt) — no env vars consulted.

_SELF_TEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["reply"],
    "properties": {"reply": {"type": "string"}},
}


def _main(argv: list[str]) -> int:
    from .config import resolve_llm  # local import — avoid cycle at module load
    try:
        cfg = resolve_llm(interactive=sys.stdin.isatty())
    except RuntimeError as exc:
        print(f"Resolve failed: {exc}", file=sys.stderr)
        return 1

    print(f"Resolved: {cfg.model} @ {cfg.url}")
    if cfg.api_key:
        print("Auth: Bearer token set (LLM_API_KEY)")

    if len(argv) >= 2 and argv[0] == "--test":
        prompt = argv[1]
        print(f"\nTest call with prompt: {prompt!r}")
        try:
            result = call_json(
                cfg,
                system=(
                    "You are a helpful assistant. Be concise. "
                    "Put your response in the `reply` field."
                ),
                user_msgs=[prompt],
                response_schema=_SELF_TEST_SCHEMA,
                max_tokens=5000,
            )
            print(f"\nResponse:\n{result.get('reply', result)}")
        except RuntimeError as exc:
            print(f"Call failed: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
