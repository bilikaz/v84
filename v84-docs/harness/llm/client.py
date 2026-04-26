#!/usr/bin/env python3
"""
llm.py — LLM client for the v84 harness.

One wire format: OpenAI-compatible chat completions. Anthropic, OpenAI,
Qwen (via vLLM), Ollama, LM Studio — every provider we care about speaks
this format. No native Anthropic API. Keeps the client small and uniform.

Public API (what the rest of the harness calls):

    detect() -> LLMConfig                — find a reachable endpoint
    call(cfg, system, user_msgs, *,      — chat completion with optional
         marker=True, tools=None, ...)     tool-call loop and marker-retry
                                            extraction; returns text

Zero external dependencies. Standard library only.
"""

# `from __future__ import annotations` delays evaluation of type hints so
# `list[str]` works on Python 3.9+ without importing `List` from typing.
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

# Marker used by pipeline-agent instructions (decompose, writer, reviewer,
# architect). Models emit this as the first non-thinking line, then their
# structured output. call() validates its presence and extracts the body
# after it when marker=True.
MARKER = "====== MY RESPONSE ======"

# Closing tag for reasoning blocks. Thinking models (Qwen3, DeepSeek-R1,
# etc.) end their reasoning with </think> and only sometimes open with
# <think> — several models start reasoning implicitly and just signal the
# end. So we look for the closing tag alone.
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
    """
    url: str
    model: str
    api_key: Optional[str] = None
    max_concurrency: int = 1


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
    tools: Optional[list[dict]] = None,
    max_tokens: int = 150_000,
) -> dict[str, Any]:
    """Construct the JSON body for a chat/completions POST.

    Pulled out of call() so the tool-call loop can reuse the same
    body shape across successive rounds.
    """
    body: dict[str, Any] = {
        "model": cfg.model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
        # vLLM-specific: enable reasoning in the chat template AND keep
        # special tokens in the output so </think> actually appears.
        # Without skip_special_tokens=false, vLLM strips the tags and we
        # can't tell where thinking ends and the real response begins.
        # OpenAI and other hosted providers ignore unknown fields; if a
        # hosted provider complains, set LLM_NO_THINKING=1 to suppress.
        "chat_template_kwargs": {"enable_thinking": True},
        "skip_special_tokens": False,
    }
    if os.getenv("LLM_NO_THINKING"):
        body.pop("chat_template_kwargs", None)
        body.pop("skip_special_tokens", None)
    if tools:
        body["tools"] = tools
    return body


def _post(
    cfg: LLMConfig,
    body: dict[str, Any],
    *,
    log_name: Optional[str] = None,
    log_dir: Optional[Path] = None,
) -> dict:
    """POST a fully-built body to the chat/completions endpoint.

    Writes a pre-call "pending" log before the network call so a hang
    is inspectable, then a full "complete" log after the response.
    """
    endpoint = f"{cfg.url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=data, headers=headers, method="POST",
    )

    if log_name and log_dir:
        _write_log(log_dir, log_name, cfg, body)

    try:
        # 900s ceiling — thinking models on long outputs can take minutes.
        with urllib.request.urlopen(req, timeout=900) as resp:
            response = json.load(resp)
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise RuntimeError(f"LLM API error {exc.code}: {err_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM network error: {exc.reason}") from exc

    if log_name and log_dir:
        _write_log(log_dir, log_name, cfg, body, response)

    return response


# -----------------------------------------------------------------------------
# Calls
# -----------------------------------------------------------------------------

def call(
    cfg: LLMConfig,
    system: str,
    user_msgs: list[str],
    *,
    marker: bool = True,
    tools: Optional[dict[str, dict]] = None,
    retries: int = 3,
    max_tool_iterations: int = 20,
    max_tokens: int = 150_000,
    log_name: Optional[str] = None,
    log_dir: Optional[Path] = None,
) -> str:
    """Run a chat completion. Returns text.

    Tool dispatch:
        If `tools` is provided (dict of {name: {"schema", "call"}}),
        the function loops:
            LLM → tool_calls → harness executes → LLM continues
        until the LLM produces a content-bearing response.

    marker=True (default):
        Expect the final content to contain MARKER. Strip thinking,
        extract post-marker body, return it. Retries up to `retries`
        times on marker-missing or tool-loop-exhaustion.

    marker=False:
        Run the tool loop once, return the stripped text content
        as-is. No marker check, no retry.

    Raises RuntimeError on marker-missing exhausted (only when
    marker=True) or tool-loop-exhaustion.
    """
    base_messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for msg in user_msgs:
        base_messages.append({"role": "user", "content": msg})

    # Tools registry → schema list the LLM sees.
    tool_schemas: Optional[list[dict]] = None
    if tools:
        tool_schemas = [t["schema"] for t in tools.values()]

    attempts = retries if marker else 1
    for marker_attempt in range(1, attempts + 1):
        # Fresh per attempt — tool-call history from a failed attempt
        # shouldn't leak into the next.
        messages = list(base_messages)

        for tool_iter in range(1, max_tool_iterations + 1):
            iter_log = (
                f"{log_name}-a{marker_attempt}-i{tool_iter}"
                if log_name else None
            )
            body = _build_body(
                cfg, messages, tools=tool_schemas, max_tokens=max_tokens,
            )
            response = _post(cfg, body, log_name=iter_log, log_dir=log_dir)

            try:
                msg = response["choices"][0]["message"]
            except (KeyError, IndexError, TypeError):
                msg = {}

            tool_calls = msg.get("tool_calls")
            if tool_calls:
                messages.append(msg)
                for tc in tool_calls:
                    result = _dispatch_tool_call(tc, tools or {})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": result,
                    })
                continue  # next LLM round

            # No tool calls → final text response
            text = msg.get("content", "") or ""
            body_text = _strip_thinking(text)

            if not marker:
                return body_text

            if MARKER in body_text:
                return _extract_after_marker(body_text)

            # Marker missing — break to the outer (retry) loop
            break
        else:
            # for..else: inner loop exhausted without break
            if marker and marker_attempt < attempts:
                print(
                    f"WARN  tool loop exhausted on attempt "
                    f"{marker_attempt}/{attempts} (log: {iter_log}) "
                    f"— retrying...",
                    file=sys.stderr, flush=True,
                )
            continue

        if marker and marker_attempt < attempts:
            preview = _preview(body_text)
            print(
                f"WARN  marker missing on attempt "
                f"{marker_attempt}/{attempts} (log: {iter_log}) "
                f"— retrying...\n"
                f"      response begins: {preview}",
                file=sys.stderr, flush=True,
            )

    raise RuntimeError(
        f"marker missing after {attempts} attempts (last log: {iter_log})"
    )


def _preview(text: str, *, limit: int = 200) -> str:
    """One-line, length-capped preview of model output for WARN logs."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return repr(flat)
    return repr(flat[:limit] + "…")


def _dispatch_tool_call(tool_call: dict, tools: dict[str, dict]) -> str:
    """Execute one tool call, return the result as a plain string.

    Invalid JSON args or unknown tool names are returned as error
    strings so the LLM can see what went wrong and retry — never
    raised into the harness.
    """
    fn_name = tool_call.get("function", {}).get("name", "")
    raw_args = tool_call.get("function", {}).get("arguments", "{}")
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except json.JSONDecodeError as exc:
        return f"Error parsing arguments for {fn_name}: {exc}"

    handler = tools.get(fn_name, {}).get("call")
    if handler is None:
        return (
            f"Error: unknown tool {fn_name!r}. "
            f"Available: {', '.join(sorted(tools))}"
        )

    try:
        result = handler(**args)
    except TypeError as exc:
        return f"Error calling {fn_name} (bad arguments): {exc}"
    except Exception as exc:  # noqa: BLE001 — feed any failure back to the LLM
        return f"Error calling {fn_name}: {exc}"

    return str(result)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

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


def _extract_after_marker(text: str) -> str:
    """Return the text after the first MARKER line, stripped."""
    idx = text.find(MARKER)
    if idx == -1:
        return text
    # Find end of the marker line — that's where the real content starts.
    line_end = text.find("\n", idx)
    if line_end == -1:
        return ""
    return text[line_end + 1:].strip()


def _write_log(log_dir: Path, name: str, cfg: LLMConfig,
               request: dict, response: Optional[dict] = None) -> None:
    """Persist a request (and optionally a response) for audit/debug.

    Without `response`: writes `<name>-pending.json` (stable filename
    so the next call overwrites it). Lets operators inspect the
    in-flight request if the call hangs.

    With `response`: writes `<name>-<ts>.json` AND a sibling
    `<name>-<ts>.md` containing just the assistant's text content
    (easier to skim than the JSON envelope). Removes any leftover
    pending marker.
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
        entry["response"] = response
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = log_dir / f"{name}-{ts}.json"
        pending = log_dir / f"{name}-pending.json"
        if pending.exists():
            pending.unlink()
        # Companion .md with the model's text, verbatim — no stripping,
        # no wrapping. Some servers (vLLM with reasoning models) put
        # the body in `content` and the chain-of-thought in
        # `reasoning_content`; we write whichever is present, untouched.
        try:
            msg_obj = response["choices"][0]["message"]
            content = msg_obj.get("content") or ""
            reasoning = msg_obj.get("reasoning_content") or ""
        except (KeyError, IndexError, TypeError):
            content = ""
            reasoning = ""
        raw = reasoning + content
        if raw:
            md = log_dir / f"{name}-{ts}.md"
            md.write_text(raw, encoding="utf-8")
    else:
        out = log_dir / f"{name}-pending.json"

    out.write_text(json.dumps(entry, indent=2), encoding="utf-8")


# -----------------------------------------------------------------------------
# Self-test CLI
# -----------------------------------------------------------------------------
# Run this file directly to verify the configured endpoint works:
#     python3 harness/llm.py
#     python3 harness/llm.py --test "say hi"
#
# Resolves config via the same path as the harness (profile.yaml +
# bootstrap cache + interactive prompt) — no env vars consulted.

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
            content = call(
                cfg,
                system="You are a helpful assistant. Be concise.",
                user_msgs=[prompt],
                marker=False,
                max_tokens=5000,
            )
            print(f"\nResponse:\n{content}")
        except RuntimeError as exc:
            print(f"Call failed: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
