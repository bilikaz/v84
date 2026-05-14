"""
cycle.py — Per-role pipeline orchestrator.

One stage that runs every active role's pipeline (draft|patch →
review → lead → done) concurrently. As each role finishes a step,
its next step is dispatched immediately — fast roles don't wait
for slow ones. Architect waits for the join (every role at `done`).

Concurrency model:
    - One thread per active role. Each role's pipeline is sequential
      (a step starts only after its predecessor finished).
    - Across roles, all currently-pending steps run in parallel.
    - The LLM client caps total in-flight requests via a global
      semaphore (see llm/client.py:_acquire_inflight). Each step's
      internal fan-out (e.g. review's reviewer calls) submits without
      its own concurrency cap; the global semaphore throttles.
    - Failure of one role's step leaves the role at that step in
      status.yaml. Other roles keep moving. After the wait, the
      orchestrator surfaces failures and exits non-zero so the
      operator re-runs to retry only the failed slots.

Status state machine (per role, in `iterations/<n>/status.yaml`):
    draft  → review → lead → done    (round 1)
    patch  → review → lead → done    (round 2+)

When every role is at `done`, the orchestrator advances global
`next_step` to `architect`.
"""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Callable, Optional

from core import coreyaml, iter_status
from core.context import active_roles
from core.stage import Stage
from llm import LLMConfig
from ui import spinner

from .draft      import draft_role
from .lead_round import lead_role
from .patch      import patch_role
from .review     import review_role


# Step → handler. The handler signature is uniform:
#     fn(project_dir, parent, iteration_n, role, *, cfg) -> None
# Each handler advances the role's status to its successor step on
# success and raises on failure (leaving the role at the current step).
_STEP_HANDLERS: dict[str, Callable[..., None]] = {
    iter_status.STEP_DRAFT:  draft_role,
    iter_status.STEP_PATCH:  patch_role,
    iter_status.STEP_REVIEW: review_role,
    iter_status.STEP_LEAD:   lead_role,
}


def cycle(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Drive every active role's pipeline to `done`, then advance
    global next_step to `architect`."""
    if cfg is None:
        raise ValueError("LLMConfig required — call via v84.py or pass cfg=")

    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        raise RuntimeError(
            "no current_iteration set in core.yaml — run plan first"
        )
    parent = coreyaml.find_by_id(data, parent_id)
    if parent is None:
        raise RuntimeError(f"current_iteration {parent_id!r} not found")

    iteration_n = _iteration_number(parent_id)
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    iter_dir.mkdir(parents=True, exist_ok=True)

    # Roles map should already be populated — by plan (round 1) or
    # architect_validate (round 2+). Defensive fallback: if missing,
    # initialise to the project's full role set at draft.
    roles = iter_status.get_roles(project_dir, iteration_n)
    if not roles:
        profile_path = project_dir / "v84" / "profile.yaml"
        all_roles = active_roles(profile_path)
        if not all_roles:
            raise RuntimeError("no active roles in profile.yaml")
        iter_status.init_pipeline(
            project_dir, iteration_n,
            round=int(iter_status.read(project_dir, iteration_n).get("round", 1)),
            roles=all_roles,
            starting_step=iter_status.STEP_DRAFT,
        )
        roles = iter_status.get_roles(project_dir, iteration_n)

    active = [r for r, s in roles.items() if s != iter_status.STEP_DONE]
    if not active:
        # Every role is already done — just promote next_step.
        iter_status.advance_to(
            project_dir, iteration_n, iter_status.STEP_ARCHITECT,
        )
        return iter_dir

    spinner.log(
        f"  cycle: dispatching {len(active)} role pipeline(s): "
        f"{', '.join(f'{r}@{s}' for r, s in roles.items() if s != iter_status.STEP_DONE)}"
    )

    # Per-role pipeline runner: blocks until the role hits `done` (or a
    # step fails). Submitted to a worker pool so all role pipelines run
    # concurrently. The LLM client's global semaphore caps total
    # in-flight requests, so this can't oversaturate the endpoint.
    def _run_role_to_done(role: str) -> None:
        while True:
            step = iter_status.get_role_step(project_dir, iteration_n, role)
            if step is None or step == iter_status.STEP_DONE:
                return
            handler = _STEP_HANDLERS.get(step)
            if handler is None:
                raise RuntimeError(
                    f"role {role!r}: unknown pipeline step {step!r}"
                )
            handler(project_dir, parent, iteration_n, role, cfg=cfg)

    failed: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=len(active)) as pool:
        futures: dict[Future, str] = {
            pool.submit(_run_role_to_done, role): role for role in active
        }
        # Drain as they complete so any failure is reported promptly.
        # Other roles keep running to completion regardless — partial
        # progress lands on disk via per-role status updates.
        pending = set(futures.keys())
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for fut in done:
                role = futures[fut]
                try:
                    fut.result()
                    spinner.log(f"  ✓ {role} pipeline → done")
                except Exception as exc:
                    failed.append((role, repr(exc)))
                    spinner.log(f"  ✗ {role} pipeline failed: {exc!r}")

    if failed:
        # Status.yaml already reflects how far each role got; re-running
        # picks up the failed roles at their current step.
        raise RuntimeError(
            f"cycle: {len(failed)} role pipeline(s) failed — re-run to retry"
        )

    iter_status.advance_to(
        project_dir, iteration_n, iter_status.STEP_ARCHITECT,
    )
    return iter_dir


# -----------------------------------------------------------------------------
# Stage glue
# -----------------------------------------------------------------------------

def _iteration_number(task_id: str) -> int:
    return int(task_id.split(".")[0].split("-")[1])


_POST_CYCLE_STEPS = frozenset({
    iter_status.STEP_ARCHITECT,
    iter_status.STEP_ARCHITECT_VALIDATE,
    iter_status.STEP_USER_REVIEW,
    iter_status.STEP_FINISH,
    iter_status.STEP_DONE_GLOBAL,
})


def _is_done(project_dir: Path) -> bool:
    """Done when status.yaml's next_step is in a post-cycle phase
    (architect / validate / user_review / finish / done). Legacy
    mid-pipeline values (the old draft/review/lead_round/patch)
    count as not-done so a stale in-flight iteration is picked up
    by cycle on resume."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        return False
    iteration_n = _iteration_number(parent_id)
    s = iter_status.read(project_dir, iteration_n)
    if s is None:
        return False
    return s.get("next_step") in _POST_CYCLE_STEPS


STAGE = Stage(
    name="cycle",
    title="Per-role pipeline (draft|patch → review → lead, parallel)",
    priority=1100,
    produces="iterations/<n>/<role>.yaml + corrections + rules",
    requires=("plan",),
    needs_brief=False,
    is_done=_is_done,
    call=cycle,
)
