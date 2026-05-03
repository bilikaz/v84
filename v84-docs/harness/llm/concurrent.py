"""
concurrent.py — Run N LLM calls in parallel up to cfg.max_concurrency.

Used by stages that fan out (writers per active role, reviewers per
lens). Wraps `llm.call_json()` per spec; threads fine since calls are
HTTP-bound. Each call's log_name carries through so per-agent logs
land separately under default_log_dir().

Spec shape:

    CallSpec(
        system="...",          # the agent's instruction
        user_msgs=[...],       # context blocks, multi-message
        response_schema={...}, # JSON Schema for the answer
        log_name="...",        # log_name passed to llm.call_json
        max_tokens=60_000,    # optional, defaults to client default
    )

Returns a list of (CallSpec, response_value, error) — error is None
on success, response is the parsed JSON value (dict/list) matching
the spec's schema. Order matches input order. Exceptions are returned
per spec, not raised, so one failure doesn't kill the rest of the
fan-out.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from ui import spinner

from .client import LLMConfig, call_json


@dataclass
class CallSpec:
    """One LLM call's configuration."""
    system: str
    user_msgs: list[str]
    response_schema: dict
    log_name: str
    max_tokens: int = 60_000


@dataclass
class CallResult:
    """One call's outcome."""
    spec: CallSpec
    response: Any = None
    error: Optional[BaseException] = None


# Grace period after a row's `done` before we unregister it from the
# global spinner, so the operator sees the final ✓/✗ state for a beat
# instead of the row vanishing the instant the call returns.
_DONE_GRACE_S = 0.5


def call_many(
    cfg: LLMConfig,
    specs: list[CallSpec],
    *,
    log_dir: Optional[Path] = None,
    progress: Optional[object] = None,
) -> list[CallResult]:
    """Run every spec against `cfg`, up to cfg.max_concurrency in flight.

    Order of results matches order of specs. A failing call records
    its exception in CallResult.error and the rest of the batch
    continues.

    Progress UI: by default every call registers a row on the
    process-wide `ui.spinner.GLOBAL` spinner. Callers needing a
    custom progress sink (test harness, alternate UI) can pass a
    `progress` object with `started/done/stream_update(idx, ...)`
    methods; the global spinner is bypassed in that case.
    """
    if not specs:
        return []

    workers = max(1, min(cfg.max_concurrency, len(specs)))
    results: list[Optional[CallResult]] = [None] * len(specs)

    # Default progress sink: the process-wide spinner. Each call_many
    # registers its specs as rows; rows are unregistered after the
    # batch completes (with a brief grace so the final ✓ is visible).
    sink = spinner.GLOBAL if progress is None else None
    spinner_ids: list[int] = []
    if sink is not None:
        spinner_ids = [sink.register(s.log_name) for s in specs]

    def _started(local_idx: int) -> None:
        if sink is not None:
            sink.started(spinner_ids[local_idx])
        elif progress is not None:
            try:
                progress.started(local_idx)
            except Exception:  # noqa: BLE001 — UI hiccups must not abort the call
                pass

    def _done(local_idx: int, error: Optional[BaseException]) -> None:
        if sink is not None:
            sink.done(spinner_ids[local_idx], error)
        elif progress is not None:
            try:
                progress.done(local_idx, error)
            except Exception:  # noqa: BLE001
                pass

    def _stream_sink(local_idx: int):
        # Per-call streaming hook plumbed through to call_json → _post.
        # Forwards every kwarg (phase, content, reasoning, tail,
        # loop_ratio, loop_streak, …) so the spinner row stays current.
        if sink is not None:
            rid = spinner_ids[local_idx]
            def on_stream(**kw):
                try:
                    sink.stream_update(rid, **kw)
                except Exception:  # noqa: BLE001
                    pass
            return on_stream
        if progress is not None and hasattr(progress, "stream_update"):
            def on_stream(**kw):
                try:
                    progress.stream_update(local_idx, **kw)
                except Exception:  # noqa: BLE001
                    pass
            return on_stream
        return None

    def _run(idx: int, spec: CallSpec) -> tuple[int, CallResult]:
        _started(idx)
        try:
            value = call_json(
                cfg,
                system=spec.system,
                user_msgs=spec.user_msgs,
                response_schema=spec.response_schema,
                log_name=spec.log_name,
                log_dir=log_dir,
                max_tokens=spec.max_tokens,
                on_stream=_stream_sink(idx),
            )
            result = CallResult(spec=spec, response=value)
        except BaseException as exc:  # noqa: BLE001 — surface per spec
            result = CallResult(spec=spec, error=exc)
        _done(idx, result.error)
        return idx, result

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_run, i, s) for i, s in enumerate(specs)]
            for fut in as_completed(futures):
                i, res = fut.result()
                results[i] = res
    finally:
        # Hold rows briefly so the operator sees the terminal ✓/✗ state,
        # then drop them so the spinner table shrinks.
        if sink is not None and spinner_ids:
            time.sleep(_DONE_GRACE_S)
            for rid in spinner_ids:
                sink.unregister(rid)

    # All slots filled (one CallResult per submitted spec).
    return [r for r in results if r is not None]
