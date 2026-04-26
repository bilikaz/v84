"""
checklist — arrow-key navigable multi-select painter.

Used by the roles stage so the user can toggle which roles are
active. Returns the chosen names in option order.
"""

from __future__ import annotations

import sys
import termios
import tty
from typing import Optional

from ._term import alt_screen, read_key


def checklist(
    options: list[dict],
    *,
    prompt: str = "Select items:",
    preselected: Optional[set[str]] = None,
) -> list[str]:
    """Arrow-key navigable checkbox picker.

    Each option is a dict with:
        name    str  — identifier returned in the result
        label   str  — optional display text (falls back to name)
        info    str  — optional description shown after the label

    Controls:
        ↑ / ↓ or k / j   move cursor
        space            toggle current row
        a                check all
        n                uncheck all
        r                reset to preselected
        enter            confirm and return current selection
        q or Ctrl+C      cancel and return preselected unchanged

    Returns the list of selected `name` fields in option order. If
    stdin/stderr is not a TTY, returns preselected unchanged (no
    interactive UI is possible).
    """
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        return [
            o["name"] for o in options
            if preselected is None or o["name"] in preselected
        ]

    original = set(preselected or [])
    selected = set(original)
    cursor = 0
    stream = sys.stderr

    def _lines() -> list[str]:
        out = [prompt]
        out.append("  (↑/↓ move · space toggle · a/n all/none · enter confirm · q cancel)")
        for i, opt in enumerate(options):
            mark = "x" if opt["name"] in selected else " "
            pointer = "›" if i == cursor else " "
            label = opt.get("label", opt["name"])
            info = opt.get("info", "")
            row = f"{pointer} [{mark}] {label:<14}  {info}"
            if i == cursor:
                row = f"\033[7m{row}\033[0m"
            out.append(row)
        out.append(f"Selected: {len(selected)}/{len(options)}")
        return out

    def _paint() -> None:
        # Home + clear screen — robust to wrapped long lines.
        stream.write("\033[H\033[2J")
        for line in _lines():
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
                    cursor = (cursor - 1) % len(options)
                elif key in ("down", "j"):
                    cursor = (cursor + 1) % len(options)
                elif key == "space":
                    name = options[cursor]["name"]
                    if name in selected:
                        selected.remove(name)
                    else:
                        selected.add(name)
                elif key == "a":
                    selected = {o["name"] for o in options}
                elif key == "n":
                    selected = set()
                elif key == "r":
                    selected = set(original)
                elif key == "enter":
                    return [o["name"] for o in options if o["name"] in selected]
                elif key in ("q", "ctrl_c", "eof"):
                    return [o["name"] for o in options if o["name"] in original]
                # Unknown key → no-op redraw.
                _paint()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
