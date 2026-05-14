"""
iter_status.py — Per-iteration status tracking, per-role pipeline.

A single file at `iterations/<n>/status.yaml` drives the cycle:

    round: 1
    next_step: cycle | architect | architect_validate
                | user_review | done
    roles:                          # populated when next_step == cycle
      frontend: done
      backend:  review
      devops:   lead
      testing:  patch

Each role's value is its current pipeline step:

    draft   — round 1 only, role hasn't started yet
    patch   — round 2+, role hasn't applied corrections yet
    review  — draft/patch landed, awaiting reviewer fan-out
    lead    — review landed, awaiting lead verdict + raise
    done    — lead landed, role parked at the architect barrier

Lifecycle:

    plan         →  status created with {round: 1, next_step: cycle,
                                         roles: {<r>: draft, ...}}
    cycle        →  per-role stages advance each role through
                    draft|patch → review → lead → done. When every
                    role is at `done`, the lead stage that finished
                    last advances next_step → architect.
    architect    →  next_step: architect_validate (always)
    validate     →  decides round-end:
                    - any role's corrections.yaml has entries → start
                      a new cycle: round++, next_step: cycle, roles
                      reset to {<r>: patch} for roles with pending
                      corrections (others omitted = inactive this round).
                    - all corrections.yaml are empty → cycle done:
                      next_step: user_review.
    user_review  →  next_step: done.

Validate is the cycle-end check. If corrections remain to apply,
the next round narrows the role set to those with pending work.

Concurrent-write safety:
    Per-role stages run in parallel. Every read-modify-write of
    status.yaml takes `_FILE_LOCK` (process-local — the harness is
    single-process). On disk we still write atomically (tempfile +
    rename) so a crash mid-write doesn't corrupt the file.

A role is "active" this round iff it appears as a key in `roles:`.
The flat `active_roles:` list from earlier schemas is gone — the
roles map is its replacement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from . import safe_io


# Pipeline step names — what a role's value in `roles:` can hold.
STEP_DRAFT  = "draft"
STEP_PATCH  = "patch"
STEP_REVIEW = "review"
STEP_LEAD   = "lead"
STEP_DONE   = "done"

PIPELINE_STEPS = (STEP_DRAFT, STEP_PATCH, STEP_REVIEW, STEP_LEAD, STEP_DONE)


# Global next_step values — what `next_step:` can hold.
STEP_RULES_LEAD         = "rules_lead"
STEP_RULES_ARCHITECT    = "rules_architect"
STEP_RULES_VALIDATE     = "rules_validate"
STEP_RULES_CONSOLIDATE  = "rules_consolidate"
STEP_USER_RULES_REVIEW  = "user_rules_review"
STEP_CYCLE              = "cycle"
STEP_ARCHITECT          = "architect"
STEP_ARCHITECT_VALIDATE = "architect_validate"
STEP_USER_REVIEW        = "user_review"
STEP_FINISH             = "finish"
STEP_DONE_GLOBAL        = "done"


def path(project_dir: Path, iteration_n: int) -> Path:
    return (
        project_dir / "v84" / "iterations" / str(iteration_n) / "status.yaml"
    )


def read(project_dir: Path, iteration_n: int) -> Optional[dict]:
    """Return the parsed status.yaml, or None when absent."""
    data = safe_io.read_yaml(path(project_dir, iteration_n), default=None)
    return data if isinstance(data, dict) else None


def write(
    project_dir: Path, iteration_n: int, *,
    round: int,
    next_step: str,
    roles: Optional[dict[str, str]] = None,
) -> Path:
    """Replace status.yaml with the given fields. `roles` is a
    role-tag → step mapping; pass None to drop the field entirely."""
    p = path(project_dir, iteration_n)
    payload: dict = {"round": round, "next_step": next_step}
    if roles is not None:
        payload["roles"] = dict(roles)
    return safe_io.write_yaml(p, payload)


# -----------------------------------------------------------------------------
# Per-role pipeline helpers
# -----------------------------------------------------------------------------

def get_roles(project_dir: Path, iteration_n: int) -> dict[str, str]:
    """Role → current pipeline step. Empty dict when no `roles:` key."""
    s = read(project_dir, iteration_n)
    if not s:
        return {}
    roles = s.get("roles")
    if not isinstance(roles, dict):
        return {}
    return {k: str(v) for k, v in roles.items() if isinstance(k, str)}


def get_active_roles(
    project_dir: Path, iteration_n: int, fallback: list[str],
) -> list[str]:
    """Roles in scope this round = keys of `roles:`, in declaration
    order. Falls back to `fallback` (typically the project's full role
    list) when status.yaml has no roles map yet — covers the very
    first call before plan/draft has populated the map."""
    s = read(project_dir, iteration_n)
    if not s:
        return list(fallback)
    roles = s.get("roles")
    if not isinstance(roles, dict) or not roles:
        return list(fallback)
    return [k for k in roles.keys() if isinstance(k, str)]


def get_role_step(
    project_dir: Path, iteration_n: int, role: str,
) -> Optional[str]:
    """Role's current step, or None when role isn't active this round."""
    return get_roles(project_dir, iteration_n).get(role)


def set_role_step(
    project_dir: Path, iteration_n: int, role: str, step: str,
) -> None:
    """Atomically update a single role's step in `roles:`. Other roles'
    steps and the rest of status.yaml are preserved.

    Used by per-role stages (draft, patch, review, lead) to advance
    their own slot when work for that role lands. Concurrent calls from
    different role-threads are serialised by `safe_io`'s per-path lock.
    """
    if step not in PIPELINE_STEPS:
        raise ValueError(f"unknown pipeline step: {step!r}")
    with safe_io.update_yaml(path(project_dir, iteration_n), default={}) as data:
        roles = data.get("roles")
        if not isinstance(roles, dict):
            roles = {}
        roles[role] = step
        data["roles"] = roles


def init_pipeline(
    project_dir: Path, iteration_n: int, *,
    round: int,
    roles: list[str],
    starting_step: str,
) -> Path:
    """Start a fresh cycle: stamp `roles:` with each entry at
    `starting_step`. `next_step` is set to `cycle`. Used by:
        - draft (round 1) with starting_step=draft
        - architect_validate (round N+1) with starting_step=patch and
          a narrowed role list (only those with pending corrections).
    """
    if starting_step not in PIPELINE_STEPS:
        raise ValueError(f"unknown pipeline step: {starting_step!r}")
    return write(
        project_dir, iteration_n,
        round=round,
        next_step=STEP_CYCLE,
        roles={r: starting_step for r in roles},
    )


def all_roles_done(project_dir: Path, iteration_n: int) -> bool:
    """True iff every role in `roles:` is at step `done`. Returns
    False when there is no roles map (cycle hasn't started yet)."""
    roles = get_roles(project_dir, iteration_n)
    if not roles:
        return False
    return all(v == STEP_DONE for v in roles.values())


# -----------------------------------------------------------------------------
# Global next_step transitions
# -----------------------------------------------------------------------------

def advance_to(
    project_dir: Path, iteration_n: int, next_step: str,
    *, roles: Optional[dict[str, str]] = None,
) -> str:
    """Set next_step in the current round (no round change). Pass
    `roles` to also rewrite the per-role map; omit to keep the existing
    map verbatim. Used by architect/validate when stepping through the
    global phases."""
    with safe_io.update_yaml(
        path(project_dir, iteration_n), default={"round": 1},
    ) as data:
        data["next_step"] = next_step
        if roles is not None:
            data["roles"] = dict(roles)
    return next_step


def next_round_to(
    project_dir: Path, iteration_n: int, next_step: str,
    *, roles: Optional[dict[str, str]] = None,
) -> str:
    """Increment round and set next_step. Used by architect_validate
    when starting a new cycle: usually combined with
    `roles={r: 'patch' for r in pending_roles}` to narrow the role
    set to those with corrections to apply."""
    with safe_io.update_yaml(
        path(project_dir, iteration_n), default={"round": 1},
    ) as data:
        data["round"] = int(data.get("round", 1)) + 1
        data["next_step"] = next_step
        if roles is not None:
            data["roles"] = dict(roles)
    return next_step


# -----------------------------------------------------------------------------
# Stage `is_done` predicate helpers
# -----------------------------------------------------------------------------

def stage_is_done(
    project_dir: Path, iteration_n: int, stage_name: str,
) -> bool:
    """A global stage is done when status.yaml exists AND
    `next_step != stage_name`. Use for architect / architect_validate
    / user_review-style stages whose progress lives in next_step.

    Per-role stages (frontend.draft, etc.) check `roles[<r>]` directly
    via `role_step_is_done` — not this helper.
    """
    s = read(project_dir, iteration_n)
    if s is None:
        return False
    return s.get("next_step") != stage_name


def role_step_is_done(
    project_dir: Path, iteration_n: int, role: str, step: str,
) -> bool:
    """A per-role step is done when the role has advanced past it.
    The pipeline order is draft → review → lead → done (round 1) or
    patch → review → lead → done (round 2+).

    A role missing from `roles:` (inactive this round) counts as done
    for every step — its work is already accepted from a prior round.
    """
    roles = get_roles(project_dir, iteration_n)
    cur = roles.get(role)
    if cur is None:
        return True   # role inactive this round → already past every step
    return _step_index(cur) > _step_index(step)


def _step_index(step: str) -> int:
    """Order step names so `done` > `lead` > `review` > `patch`/`draft`.
    `patch` and `draft` share index 0 — in any given round only one of
    them is the entry step (round 1 → draft, round 2+ → patch)."""
    if step in (STEP_DRAFT, STEP_PATCH):
        return 0
    return {STEP_REVIEW: 1, STEP_LEAD: 2, STEP_DONE: 3}.get(step, -1)
