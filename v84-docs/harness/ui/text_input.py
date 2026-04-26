"""
text_input — multi-line text input painter.

Used wherever a stage needs free-text from the user (e.g. the
"revise with a comment" path in decompose). Renders on the
alt-screen so ESC can cancel cleanly — plain `input()` can't
intercept ESC.
"""

from __future__ import annotations

import sys
import termios
import tty
from typing import Optional

from ._term import alt_screen, read_key


def text_input(
    *,
    prompt: str = "Type your input:",
    summary: str = "",
    hint: Optional[str] = None,
) -> Optional[str]:
    """Multi-line text editor on the alt-screen. Returns the typed
    string (newline-joined), or None if the user pressed ESC.

    Controls:
        printable    appended to the current line
        enter        newline; on an empty line with content above,
                     confirms and returns the joined text
        backspace    delete previous char (crosses line boundaries)
        esc          cancel — return None

    `summary` is a multi-line block printed above the prompt.
    `hint` overrides the default controls hint when set.
    """
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        # Non-interactive: read whole stdin, single-shot, no ESC.
        try:
            text = sys.stdin.read().strip()
        except (EOFError, KeyboardInterrupt):
            return None
        return text or None

    if hint is None:
        hint = (
            "  (type · enter for new line · empty line confirms · esc cancels)"
        )

    lines: list[str] = [""]
    stream = sys.stderr

    def _paint() -> None:
        out: list[str] = []
        if summary:
            for line in summary.splitlines():
                out.append(line)
            out.append("")
        out.append(prompt)
        out.append(hint)
        out.append("")
        # Render typed lines with a block cursor on the active line.
        for i, line in enumerate(lines):
            if i == len(lines) - 1:
                out.append(f"> {line}█")
            else:
                out.append(f"> {line}")
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
                if key in ("esc", "ctrl_c"):
                    return None
                if key == "enter":
                    # Empty current line + at least one prior non-empty line
                    # → confirm. Otherwise start a new line.
                    if not lines[-1] and any(l.strip() for l in lines[:-1]):
                        text = "\n".join(lines).strip()
                        return text or None
                    lines.append("")
                elif key == "eof":
                    # Treat Ctrl+D the same as confirm if we have content,
                    # else cancel — keeps muscle memory for terminal users.
                    text = "\n".join(lines).strip()
                    return text or None
                elif key in ("backspace", "\x7f", "\x08"):
                    if lines[-1]:
                        lines[-1] = lines[-1][:-1]
                    elif len(lines) > 1:
                        lines.pop()
                else:
                    # read_key returns logical names for some keys
                    # ("space", "enter", ...) — translate space back
                    # to the literal char for text accumulation. Other
                    # printable single-char keys append as-is.
                    if key == "space":
                        lines[-1] += " "
                    elif len(key) == 1 and key.isprintable():
                        lines[-1] += key
                _paint()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
