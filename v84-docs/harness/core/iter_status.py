"""
iter_status.py — Per-iteration status tracking.

A single file at `iterations/<n>/status.yaml` drives the cycle:

    round: 1
    next_step: draft | review | lead | architect
                | validate | patch | user_review | done

Lifecycle:

    plan         →  status created with {round: 1, next_step: draft}
    draft        →  next_step: review            (round 1 only)
    patch        →  next_step: review            (round 2+; replaces draft)
    review       →  next_step: lead
    lead         →  next_step: architect
    architect    →  next_step: validate          (always)
    validate     →  decides round-end:
                    - any role's corrections.yaml has entries → start
                      a new cycle: round++, next_step: patch
                    - all corrections.yaml are empty → cycle done:
                      next_step: user_review
                    (Phase A: no cross-lead validation; pure check.
                    Phase B: cross-lead approval of architect's global
                    proposals also runs here.)
    user_review  →  next_step: done
                    (Phase A: not implemented; Phase B: gate that lets
                    the user accept/reject all conv/dec and promotes
                    accepted ones to <project>/v84/{conventions,
                    decisions}.yaml, then closes the iteration.)

Validate is the cycle-end check. If corrections remain to apply,
patch starts a new cycle (round++). Patch moves applied corrections
to <role>.corrections-applied.yaml so the next round's reviewers
can verify what was honored.

Stage `is_done` checks read this file: a stage is done when its
name no longer matches `next_step`. Absent file means the
iteration hasn't started yet (only plan can run).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml


def path(project_dir: Path, iteration_n: int) -> Path:
    return (
        project_dir / "v84" / "iterations" / str(iteration_n) / "status.yaml"
    )


def read(project_dir: Path, iteration_n: int) -> Optional[dict]:
    p = path(project_dir, iteration_n)
    if not p.exists():
        return None
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else None


def write(
    project_dir: Path, iteration_n: int, *,
    round: int, next_step: str,
) -> Path:
    p = path(project_dir, iteration_n)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(
            {"round": round, "next_step": next_step},
            default_flow_style=False, sort_keys=False, allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return p


def advance_to(
    project_dir: Path, iteration_n: int, next_step: str,
) -> str:
    """Set next_step in the current round (no round change)."""
    cur = read(project_dir, iteration_n) or {"round": 1}
    write(project_dir, iteration_n,
          round=cur.get("round", 1), next_step=next_step)
    return next_step


def next_round_to(
    project_dir: Path, iteration_n: int, next_step: str,
) -> str:
    """Increment round and set next_step (used by validate when starting
    a new cycle with patch)."""
    cur = read(project_dir, iteration_n) or {"round": 1}
    write(project_dir, iteration_n,
          round=cur.get("round", 1) + 1, next_step=next_step)
    return next_step


def stage_is_done(
    project_dir: Path, iteration_n: int, stage_name: str,
) -> bool:
    """A stage is done when status.yaml exists AND next_step != stage_name."""
    s = read(project_dir, iteration_n)
    if s is None:
        return False
    return s.get("next_step") != stage_name
