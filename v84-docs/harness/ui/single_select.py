"""
single_select — pick exactly one option (or type custom).

Used standalone for accept/revise pickers and as the inner picker
that field_editor opens for each field.
"""

from __future__ import annotations

import sys
import termios
import tty
from typing import Optional

from ._term import alt_screen, read_key


def single_select(
    options: list[dict],
    *,
    prompt: str = "Pick one:",
    preselected: Optional[str] = None,
    allow_custom: bool = True,
    custom_label: str = "type custom...",
    summary: str = "",
) -> Optional[str]:
    """Single-pick keyboard navigable list. Returns the chosen `name`,
    a typed custom string, or None if the user cancelled (ESC / q).

    Each option is a dict with one of two shapes:

        Selectable row:
            name   str  — identifier returned in the result
            label  str  — optional display text (falls back to name)
            info   str  — optional secondary description

        Header (visual grouping; cursor skips):
            kind   "header"
            title  str  — section title shown bold with leading blank

    When `allow_custom=True`, an extra row appears below the options;
    selecting it drops out of raw mode and prompts for a free-text
    value. An empty entry is treated as cancel.

    `summary` is a multi-line block printed above the prompt — handy
    for showing context (e.g. the proposed plan) the user is picking
    from. Blank lines preserved.
    """
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        return preselected

    rows = list(options)
    if allow_custom:
        rows.append({"name": "__custom__", "label": custom_label, "info": ""})

    custom_idx = (
        next((i for i, r in enumerate(rows) if r.get("name") == "__custom__"), None)
        if allow_custom else None
    )

    def _is_selectable(r: dict) -> bool:
        return r.get("kind") != "header"

    def _first_selectable() -> int:
        for i, r in enumerate(rows):
            if _is_selectable(r):
                return i
        return 0

    cursor = _first_selectable()
    if preselected is not None:
        for i, r in enumerate(rows):
            if r.get("name") == preselected and _is_selectable(r):
                cursor = i
                break

    def _move(delta: int) -> None:
        nonlocal cursor
        n = len(rows)
        for _ in range(n):
            cursor = (cursor + delta) % n
            if _is_selectable(rows[cursor]):
                return

    stream = sys.stderr

    def _paint() -> None:
        out: list[str] = []
        if summary:
            for line in summary.splitlines():
                out.append(line)
            out.append("")
        out.append(prompt)
        out.append("  (↑/↓ move · space/enter pick · esc back)")
        out.append("")
        for i, r in enumerate(rows):
            if r.get("kind") == "header":
                out.append("")
                out.append(f"  \033[1m{r.get('title', '')}\033[0m")
                continue
            pointer = "›" if i == cursor else " "
            label = r.get("label", r.get("name", ""))
            info = r.get("info", "")
            row = f"  {pointer} {label}"
            if info:
                row = f"{row}  — {info}"
            if i == cursor:
                row = f"\033[7m{row}\033[0m"
            out.append(row)

        # Home + clear screen — robust to wrapped long lines.
        stream.write("\033[H\033[2J")
        for line in out:
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
                    _move(-1)
                elif key in ("down", "j"):
                    _move(1)
                elif key in ("enter", "space"):
                    if custom_idx is not None and cursor == custom_idx:
                        # Drop out of raw mode for the text prompt.
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
                        print("", file=stream)
                        try:
                            text = input("custom value: ").strip()
                        except (EOFError, KeyboardInterrupt):
                            text = ""
                        return text or None
                    return rows[cursor]["name"]
                elif key in ("esc", "q", "ctrl_c", "eof"):
                    return None
                _paint()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
