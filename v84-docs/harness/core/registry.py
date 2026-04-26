"""
registry.py — Unified pipeline registry across packages.

Each pipeline package (init, iteration, …) exports its own STAGES
tuple and next_pending(). This module merges them into one
priority-sorted view so the harness driver and state-detection
logic don't need to know which package owns which stage.

Adding a new pipeline package:
    - Define STAGES in <pkg>/__init__.py.
    - Import it here and add its tuple to ALL_STAGES.
    - Done — v84.py and core.state pick it up automatically.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import init
import iteration

from core.stage import Stage


ALL_STAGES: tuple[Stage, ...] = tuple(sorted(
    init.STAGES + iteration.STAGES,
    key=lambda s: s.priority,
))

ALL_STAGES_BY_NAME: dict[str, Stage] = {s.name: s for s in ALL_STAGES}


def next_pending(project_dir: Path) -> Optional[Stage]:
    """First stage that's ready to run.

    A stage is ready when it isn't done yet and every name in its
    `requires` is done. Stages are walked in priority order so the
    first match is the correct next step.
    """
    done = {s.name for s in ALL_STAGES if s.done(project_dir)}
    for stage in ALL_STAGES:
        if stage.name in done:
            continue
        if all(req in done for req in stage.requires):
            return stage
    return None
