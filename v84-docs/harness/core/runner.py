"""
runner.py — Stage-loop driver.

Extracted from v84.py so menu actions and CLI flags can both
trigger "run pending stages" without duplicating the loop.

The loop walks the unified stage registry: dispatch one stage,
then keep dispatching whatever `registry.next_pending` returns
until the queue empties, the user cancels, or a stage fails.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from core import registry, state


def run_pending_stages(
    project_dir: Path,
    cfg: Any,
    args: Any,
    *,
    force: Optional[str] = None,
    dispatch: Any,
) -> int:
    """Run stages until the registry has nothing pending.

    `force` overrides state detection for the FIRST stage only;
    subsequent stages flow from `registry.next_pending`.

    `dispatch` is a callable `(stage_name, project_dir, cfg, args) -> int`
    — passed in to keep this module independent of v84.py's stage-
    dispatch helper (which knows about briefs, instruction loading,
    etc.).
    """
    current = state.detect(project_dir)
    print(f"project:  {project_dir}", file=sys.stderr)
    print(f"summary:  {current.summary}", file=sys.stderr)
    print(f"next:     {current.next_action}", file=sys.stderr)

    target = force or current.next_stage_name
    if target is None:
        print("\n✓ all stages complete.", file=sys.stderr)
        return 0

    try:
        rc = dispatch(target, project_dir, cfg, args)
        if rc != 0:
            return rc
        while True:
            nxt = registry.next_pending(project_dir)
            if nxt is None:
                print("\n✓ all stages complete.", file=sys.stderr)
                return 0
            print(f"\n→ continuing to {nxt.name!r} ({nxt.title.lower()})",
                  file=sys.stderr)
            rc = dispatch(nxt.name, project_dir, cfg, args)
            if rc != 0:
                return rc
    except KeyboardInterrupt:
        print("\n  cancelled — re-run to resume.", file=sys.stderr)
        return 130
