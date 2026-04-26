"""
init — init-flow stages + self-describing registry.

Every stage module in this package exports two things:

    STAGE               a Stage metadata constant (from stage.py)
    <the function>      callable with signature (project_dir, brief,
                        *, cfg=None) -> Path

This file imports both from every stage and collects them into a
priority-sorted tuple. The harness (v84.py, state.py) iterates
through `STAGES` or asks `next_pending(project_dir)` — no stage
is ever hardcoded in the dispatcher.

Adding a new stage:

    1. Create init/<stage>.py with a function and a `STAGE` constant.
    2. Import both here and append to the STAGES tuple.
    3. Done — state detection + dispatch wire up automatically.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.stage import Stage

# Import each stage's STAGE metadata and its public function.
# Using `STAGE as _xxx_stage` pattern — rename-on-import so the
# registry variable doesn't shadow the function name we also expose.
from .decompose import STAGE as _decompose_stage, decompose
from .roles     import STAGE as _roles_stage,     select_roles
from .stack     import STAGE as _stack_stage,     suggest_stack
from .structure import STAGE as _structure_stage, suggest_structure


# Registry — priority-sorted tuple. Adding a stage: import its STAGE
# above, include it in the tuple here. `sorted(...)` keeps ordering
# honest even if someone reshuffles the declarations.
STAGES: tuple[Stage, ...] = tuple(sorted(
    (_roles_stage, _stack_stage, _structure_stage, _decompose_stage),
    key=lambda s: s.priority,
))

# Convenience lookup table
STAGES_BY_NAME: dict[str, Stage] = {s.name: s for s in STAGES}


def next_pending(project_dir: Path) -> Optional[Stage]:
    """Return the first stage that can run now, or None if all done.

    A stage is "ready to run" when:
        - it's not done yet (per `Stage.done()`, which falls back to
          file-existence on `produces` unless the stage overrides it
          with a custom `is_done` callable), AND
        - every stage in its `requires` list is done.

    Stages are walked in priority order, so the first match is the
    correct next step even if `requires` alone would permit several.
    """
    done = {s.name for s in STAGES if s.done(project_dir)}

    for stage in STAGES:
        if stage.name in done:
            continue
        if all(req in done for req in stage.requires):
            return stage
    return None


__all__ = [
    # public registry
    "Stage",
    "STAGES",
    "STAGES_BY_NAME",
    "next_pending",
    # stage functions (kept exported for direct testing / scripting)
    "decompose",
    "select_roles",
    "suggest_stack",
    "suggest_structure",
]
