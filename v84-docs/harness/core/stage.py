"""
stage.py — Shared Stage dataclass.

Every stage in every package (init, cycle, …) exports a `STAGE`
constant of this type so the harness can discover, order, and
dispatch stages without any package-specific glue.

Ordering rule:
    priority            numeric, sorted ascending. Convention: start
                        at 1, increment by 100. Leaves 99 gaps for
                        insertions without renumbering neighbours.
                        Init: 1, 101, 201, 301, …
                        Cycle (future): 1001, 1101, 1201, …
    requires            list of prerequisite stage names. Hard gate
                        on top of priority — even if a stage has
                        lower priority, it won't run until its
                        requirements are marked done.

Packages collect their stages into a tuple sorted by priority and
expose a `next_pending(project_dir)` helper that returns the first
stage whose requires are done but whose `produces` file is missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


@dataclass(frozen=True)
class Stage:
    """Metadata describing one executable stage.

    `frozen=True` makes instances immutable — stages are declared
    once at import time and shouldn't be mutated at runtime.

    Fields
    ------
    name         Short identifier used in CLI flags and status
                 output. Must be unique within a package.
    title        Human-readable description (short sentence fragment).
    priority     Integer for ordering. Lower runs first.
                 Convention: start at 1 and increment by 100.
    produces     Conceptual artefact the stage writes — used for
                 status display ("produces: profile.yaml#stack").
                 By default state detection treats this as a
                 filesystem path under <project>/v84/ and checks
                 for its existence; stages that store output
                 elsewhere (e.g. a key inside profile.yaml) provide
                 their own `is_done` callable.
    requires     Names of stages that must be done before this one
                 can run. Tuple (hashable, immutable).
    needs_brief  Whether v84.py should ensure the project brief is
                 available (from cache or prompt) before calling.
    is_done      Optional callable (project_dir → bool) that overrides
                 the default file-existence check. Use when the
                 stage's output lives inside another file (e.g.
                 stack picks under profile.yaml's `stack:` key) so
                 that "done" is a content check, not a path check.
    call         The function to execute. Signature:
                     call(project_dir: Path, brief: str, *,
                          cfg: Optional[LLMConfig] = None) -> Path
                 None means "stage declared but not yet implemented";
                 the dispatcher reports and exits cleanly.
    """
    name: str
    title: str
    priority: int
    produces: str
    requires: tuple[str, ...] = ()
    needs_brief: bool = True
    is_done: Optional[Callable[[Path], bool]] = None
    call: Optional[Callable] = None

    def done(self, project_dir: Path) -> bool:
        """Has this stage's output been produced?"""
        if self.is_done is not None:
            return self.is_done(project_dir)
        return (project_dir / "v84" / self.produces).exists()
