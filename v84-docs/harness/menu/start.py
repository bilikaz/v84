"""
menu.start — "Start / resume" action.

Wraps core.runner.run_pending_stages, threading the project's
stage dispatcher through. The dispatcher itself lives in v84.py
(it knows about brief loading and instruction paths) and is
attached to args here as `args._dispatch_stage` to keep the
import direction clean.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.runner import run_pending_stages


def start(project_dir: Path, cfg: Any, args: Any) -> int:
    """Run the next pending stage and continue until the registry is
    exhausted, the user cancels, or a stage fails. Always returns 0
    so control comes back to the main menu — long-running pipelines
    are expected and the user shouldn't get kicked out of the harness
    on a transient stage failure."""
    dispatch = getattr(args, "_dispatch_stage", None)
    if dispatch is None:
        raise RuntimeError(
            "menu.start: args._dispatch_stage not wired — v84.py must "
            "attach its stage dispatcher before invoking the menu"
        )
    rc = run_pending_stages(
        project_dir, cfg, args,
        force=getattr(args, "force", None),
        dispatch=dispatch,
    )
    if rc != 0:
        import sys
        print(
            f"  ⚠ stage runner exited with code {rc} — returning to menu",
            file=sys.stderr,
        )
        input("  press Enter to return to the menu...")
    return 0
