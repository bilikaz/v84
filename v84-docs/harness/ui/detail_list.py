"""
detail_list — navigable items + toggleable details + action row.

Used by the decompose stage so the user can walk the proposed task
list, expand any task to read its description, and pick an action
(accept / revise) from a row block at the bottom. Generic enough
to reuse for any "list of things with details, finish with an
action" review.
"""

from __future__ import annotations

import sys
import termios
import tty
from typing import Optional

from ._term import alt_screen, read_key


def detail_list(
    items: list[dict],
    *,
    actions: list[dict],
    prompt: str = "",
    summary: str = "",
    item_hint: str = "more details",
) -> Optional[str]:
    """Navigable list with toggleable per-item details + bottom actions.

    Each `items` entry has:
        label   one-line text shown on the row
        detail  multi-line prose shown below the row when expanded

    Each `actions` entry has:
        name    string returned to the caller when the row is selected
        label   text shown on the action row
        info    optional secondary description after the label

    Layout (top to bottom):
        summary block (if any) — printed above the prompt
        prompt + controls hint
        item rows; each expanded item shows its detail indented
        a separator line
        action rows

    Controls:
        ↑/↓     move cursor between item rows and action rows
        space   toggle current item's detail, OR select current action
        enter   same as space on action rows; on item rows behaves
                like a toggle (matches the user's muscle memory from
                the rest of the harness)
        esc     return None (cancel)

    `item_hint` shows next to collapsed items as a visual cue for
    the toggle, so the reusable component can be customised per
    stage ("more details", "see review", etc.).

    Returns the chosen action's `name`, or None on cancel.
    """
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        return actions[0]["name"] if actions else None

    n_items = len(items)
    n_actions = len(actions)
    if n_items + n_actions == 0:
        return None

    # Cursor walks the union of item rows + action rows. Items first,
    # then actions; index 0..n_items-1 are items, the rest are actions.
    cursor = 0 if n_items else n_items  # land on first action if no items
    expanded: set[int] = set()

    stream = sys.stderr

    def _paint() -> None:
        lines: list[str] = []
        if summary:
            for line in summary.splitlines():
                lines.append(line)
            lines.append("")
        if prompt:
            lines.append(prompt)
        lines.append(
            "  (↑/↓ move · space toggle/select · enter accept · esc cancel)"
        )
        lines.append("")

        for i, item in enumerate(items):
            pointer = "›" if i == cursor else " "
            label = item.get("label", "")
            indicator = "▾" if i in expanded else "▸"
            hint = "" if i in expanded else f"  [{indicator} {item_hint}]"
            row = f"{pointer} {label}{hint}"
            if i == cursor:
                row = f"\033[7m{row}\033[0m"
            lines.append(row)
            if i in expanded:
                detail = (item.get("detail") or "").rstrip()
                for d in detail.splitlines():
                    lines.append(f"      {d}")
                lines.append("")

        if n_items and n_actions:
            lines.append("  ─────")
        for j, action in enumerate(actions):
            idx = n_items + j
            pointer = "›" if idx == cursor else " "
            label = action.get("label", action["name"])
            info = action.get("info", "")
            row = f"{pointer} {label}"
            if info:
                row = f"{row}  — {info}"
            if idx == cursor:
                row = f"\033[7m{row}\033[0m"
            lines.append(row)

        # Home + clear screen — robust to wrapped long lines.
        stream.write("\033[H\033[2J")
        for line in lines:
            stream.write(f"{line}\n")
        stream.flush()

    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        with alt_screen():
            _paint()
            while True:
                key = read_key(fd)
                if key in ("up", "k"):
                    cursor = (cursor - 1) % (n_items + n_actions)
                elif key in ("down", "j"):
                    cursor = (cursor + 1) % (n_items + n_actions)
                elif key == "space":
                    if cursor < n_items:
                        if cursor in expanded:
                            expanded.remove(cursor)
                        else:
                            expanded.add(cursor)
                    else:
                        return actions[cursor - n_items]["name"]
                elif key == "enter":
                    if cursor < n_items:
                        # Treat enter on items as a toggle too — keeps the
                        # mental model consistent with field_editor where
                        # space is the "act" key.
                        if cursor in expanded:
                            expanded.remove(cursor)
                        else:
                            expanded.add(cursor)
                    else:
                        return actions[cursor - n_items]["name"]
                elif key in ("esc", "q", "ctrl_c", "eof"):
                    return None
                _paint()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
