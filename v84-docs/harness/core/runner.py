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
        last_dispatched = target
        while True:
            nxt = registry.next_pending(project_dir)
            if nxt is None:
                print("\n✓ all stages complete.", file=sys.stderr)
                return 0
            # If the same stage is still pending after we just ran it,
            # it didn't advance — manual intervention is needed (e.g.
            # finish wrote fix.md and waits for the implementer to
            # patch gaps before re-running v84). Halt the loop, surface
            # the message above already printed by the stage, and wait
            # for the user before exiting so the message stays visible.
            if nxt.name == last_dispatched:
                print(
                    f"\n⏸  stage {nxt.name!r} did not advance — "
                    f"manual step required (see message above).",
                    file=sys.stderr,
                )
                _wait_for_keypress()
                return 1
            print(f"\n→ continuing to {nxt.name!r} ({nxt.title.lower()})",
                  file=sys.stderr)
            rc = dispatch(nxt.name, project_dir, cfg, args)
            if rc != 0:
                return rc
            last_dispatched = nxt.name
    except KeyboardInterrupt:
        print("\n  cancelled — re-run to resume.", file=sys.stderr)
        return 130


def _wait_for_keypress() -> None:
    """Block until the user presses Enter (or the input stream closes).

    Used after a stage halts the cycle so the operator has time to
    read the gap report before the harness exits.
    """
    try:
        input("Press Enter to exit (then take the manual step "
              "and re-run v84). ")
    except (EOFError, KeyboardInterrupt):
        # EOF (Ctrl+D) or Ctrl+C both mean "I'm done reading" — fall
        # through to exit cleanly.
        print("", file=sys.stderr)
