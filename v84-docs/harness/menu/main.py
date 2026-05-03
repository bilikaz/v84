"""
menu.main — Single-select main loop + dispatch.

Each menu action is a `(project_dir, cfg, args) -> int` callable
that returns 0 to come back to the menu or non-zero to exit the
harness with that return code. Add a new option by registering
its callable in `_ITEMS`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

from core import state
from ui import single_select

from .start import start
from .setup_llm import setup_llm
from .manage_rules import manage_rules


# Registry of menu items. `name` is the value returned by
# single_select; `label` and `info` show in the picker; `action`
# is the callable invoked when the row is selected.
_MenuAction = Callable[[Path, Any, Any], int]

_ITEMS: list[dict] = [
    {
        "name": "start",
        "label": "Start / resume",
        "info": "run the next pending stage",
        "action": start,
    },
    {
        "name": "setup_llm",
        "label": "Setup LLM",
        "info": "change endpoint or re-probe model",
        "action": setup_llm,
    },
    {
        "name": "manage_rules",
        "label": "Manage rules",
        "info": "review/edit project-promoted rules",
        "action": manage_rules,
    },
    {
        "name": "quit",
        "label": "Quit",
        "info": "exit the harness",
        "action": None,    # special: returns from the loop
    },
]


def run_main_menu(project_dir: Path, cfg: Any, args: Any) -> int:
    """Show the menu, dispatch the chosen action, repeat until quit
    or an action returns non-zero."""
    actions: dict[str, _MenuAction | None] = {
        item["name"]: item["action"] for item in _ITEMS
    }
    rows = [
        {"name": item["name"], "label": item["label"], "info": item["info"]}
        for item in _ITEMS
    ]

    while True:
        current = state.detect(project_dir)
        summary = (
            f"v84 — main menu\n"
            f"project: {project_dir}\n"
            f"status:  {current.summary}\n"
            f"next:    {current.next_action}"
        )
        pick = single_select(
            rows,
            prompt="Choose an action:",
            summary=summary,
            preselected="start",
            allow_custom=False,
        )
        if pick is None or pick == "quit":
            return 0
        action = actions.get(pick)
        if action is None:
            return 0
        rc = action(project_dir, cfg, args)
        if rc != 0:
            return rc
