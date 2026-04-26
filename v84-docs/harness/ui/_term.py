"""
_term.py — Shared raw-terminal helpers for the painter package.

Two pieces every interactive painter needs:

    alt_screen        context manager that switches stderr into the
                      alt-screen buffer for the duration of an
                      interactive UI, restoring the prior contents
                      on exit (vim/htop/less style). Nesting handled
                      via a class-level depth counter.

    read_key          read one keystroke from a cbreak-mode fd and
                      return a logical name ("up", "enter", "esc", …).
                      Handles standalone-ESC vs ESC-sequence by peeking
                      with select.select.
"""

from __future__ import annotations

import os
import select
import sys


class alt_screen:
    """Context manager: switch stderr into the alt-screen buffer.

    Nested uses (e.g. single_select called from inside field_editor)
    only toggle the actual buffer at the outermost enter/exit; a
    class-level depth counter tracks nesting.

    No-op when stderr is not a TTY, so piped/CI invocations behave
    the same as before.
    """

    _depth = 0

    def __enter__(self) -> "alt_screen":
        if alt_screen._depth == 0 and sys.stderr.isatty():
            sys.stderr.write("\033[?1049h\033[H")
            sys.stderr.flush()
        alt_screen._depth += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        alt_screen._depth -= 1
        if alt_screen._depth == 0 and sys.stderr.isatty():
            sys.stderr.write("\033[?1049l")
            sys.stderr.flush()


def read_key(fd: int) -> str:
    """Read one keystroke from a cbreak-mode fd. Returns a logical name.

    Handles the standalone-ESC vs ESC-sequence ambiguity by peeking
    with select.select() — if no follow-up byte arrives within 50ms,
    treat as plain ESC.
    """
    ch = os.read(fd, 1).decode("utf-8", errors="replace")
    if ch == "\x1b":
        ready, _, _ = select.select([fd], [], [], 0.05)
        if not ready:
            return "esc"
        seq = os.read(fd, 2).decode("utf-8", errors="replace")
        return {
            "[A": "up", "[B": "down", "[C": "right", "[D": "left",
        }.get(seq, "esc")
    if ch in ("\r", "\n"):
        return "enter"
    if ch == " ":
        return "space"
    if ch == "\x03":
        return "ctrl_c"
    if ch == "\x04":
        return "eof"
    return ch
