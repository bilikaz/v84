"""
concurrent.py — Run N LLM calls in parallel up to cfg.max_concurrency.

Used by stages that fan out (writers per active role, reviewers per
lens). Wraps `llm.call()` per spec; threads fine since calls are
HTTP-bound. Each call's log_name carries through so per-agent logs
land separately under default_log_dir().

Spec shape:

    CallSpec(
        system="...",        # the agent's instruction
        user_msgs=[...],     # context blocks, multi-message
        log_name="...",      # log_name passed to llm.call
        max_tokens=150_000,  # optional, defaults to client default
    )

Returns a list of (CallSpec, response_text, error) — error is None
on success. Order matches input order. Exceptions are returned per
spec, not raised, so one failure doesn't kill the rest of the fan-out.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .client import LLMConfig, call


@dataclass
class CallSpec:
    """One LLM call's configuration."""
    system: str
    user_msgs: list[str]
    log_name: str
    max_tokens: int = 150_000


@dataclass
class CallResult:
    """One call's outcome."""
    spec: CallSpec
    response: Optional[str] = None
    error: Optional[BaseException] = None


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

    `progress` is an optional callback object with two methods:
        started(idx: int) -> None
        done(idx: int, error: BaseException | None) -> None
    Used by ui.MultiSpinner to render per-call status. Anything with
    those two methods works.
    """
    if not specs:
        return []

    workers = max(1, min(cfg.max_concurrency, len(specs)))
    results: list[Optional[CallResult]] = [None] * len(specs)

    def _run(idx: int, spec: CallSpec) -> tuple[int, CallResult]:
        if progress is not None:
            try:
                progress.started(idx)
            except Exception:  # noqa: BLE001 — UI hiccups must not abort the call
                pass
        try:
            text = call(
                cfg,
                system=spec.system,
                user_msgs=spec.user_msgs,
                log_name=spec.log_name,
                log_dir=log_dir,
                max_tokens=spec.max_tokens,
            )
            result = CallResult(spec=spec, response=text)
        except BaseException as exc:  # noqa: BLE001 — surface per spec
            result = CallResult(spec=spec, error=exc)
        if progress is not None:
            try:
                progress.done(idx, result.error)
            except Exception:  # noqa: BLE001
                pass
        return idx, result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run, i, s) for i, s in enumerate(specs)]
        for fut in as_completed(futures):
            i, res = fut.result()
            results[i] = res

    # All slots filled (one CallResult per submitted spec).
    return [r for r in results if r is not None]
