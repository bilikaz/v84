#!/usr/bin/env python3
"""
state.py — Project state detection.

Thin layer on top of the init package's stage registry. For "where
are we in init?" we delegate to `init.next_pending()` — the registry
knows everything about its own stages.

This file handles the coarser questions:
    - Does v84/ exist at all?
    - Has init completed entirely?
    - Is an iteration currently running? (future — iterations not
      wired into a stage registry yet)

Returns a ProjectState dataclass that v84.py consumes directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core import registry


@dataclass
class ProjectState:
    """What we know about a project from looking at disk."""
    project_dir: Path
    summary: str                           # one-line human description
    next_action: str                       # hint for the operator
    next_stage_name: Optional[str] = None  # stage to dispatch next, if any
    running_iteration: Optional[int] = None  # for later (iteration resumption)


def detect(project_dir: Path) -> ProjectState:
    """Classify the project's current stage. Never raises.

    Asks the unified registry what's pending across init + iteration
    + future packages. If it returns a stage, that's our next action;
    if not, the project is fully caught up.
    """
    v84 = project_dir / "v84"

    if not v84.exists():
        first = registry.ALL_STAGES[0]
        return ProjectState(
            project_dir=project_dir,
            summary=f"fresh project — no v84/ folder yet",
            next_action=f"run '{first.name}' ({first.title.lower()})",
            next_stage_name=first.name,
        )

    pending = registry.next_pending(project_dir)
    if pending is not None:
        return ProjectState(
            project_dir=project_dir,
            summary=f"pipeline in progress — needs {pending.title.lower()}",
            next_action=f"run '{pending.name}'",
            next_stage_name=pending.name,
        )

    running = _find_running_iteration(v84 / "iterations")
    if running is not None:
        return ProjectState(
            project_dir=project_dir,
            summary=f"iteration {running} in progress",
            next_action=f"resume iteration {running} (not yet implemented)",
            running_iteration=running,
        )

    return ProjectState(
        project_dir=project_dir,
        summary="all stages complete",
        next_action="nothing pending",
    )


# -----------------------------------------------------------------------------
# Helpers for iteration state (used when init is done)
# -----------------------------------------------------------------------------

def _find_running_iteration(iterations_dir: Path) -> Optional[int]:
    """Return N of iterations/N/ whose status.yaml is not 'closed', else None.

    Loose text scan — avoids pulling in a YAML dep. Good enough for
    state detection; real parsing happens where the data is used.
    """
    if not iterations_dir.exists():
        return None

    candidates: list[int] = []
    for sub in iterations_dir.iterdir():
        if not sub.is_dir() or sub.name == "archive":
            continue
        try:
            n = int(sub.name)
        except ValueError:
            continue
        status = sub / "status.yaml"
        if not status.exists():
            # folder exists but no status — treat as running (never finalised)
            candidates.append(n)
            continue
        text = status.read_text(encoding="utf-8", errors="replace")
        if "state: closed" not in text:
            candidates.append(n)

    if not candidates:
        return None
    return max(candidates)
