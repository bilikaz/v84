"""
confirm_modal — small two-button modal painter.

Slip-protection guard in front of any commit-style action. Vertical
Yes/No stack, ↑/↓ to switch focus, enter to fire focused button,
esc to cancel.

Used by review_list for `commit` actions that carry a `confirm`
spec, and by any caller that needs a uniform "are you sure?"
prompt.
"""

from __future__ import annotations

import sys
import termios
import textwrap
import tty
from typing import Optional

from ._term import alt_screen, read_key


_BOX_WIDTH = 64    # outer width including the box characters
_INNER_W = _BOX_WIDTH - 4   # text width inside left+right padding
_HORIZ = "─"
_VERT = "│"
_TL = "┌"
_TR = "┐"
_BL = "└"
_BR = "┘"


def confirm_modal(
    *,
    title: str,
    bullets: Optional[list[str]] = None,
    body: str = "",
    yes_label: str = "Yes",
    no_label: str = "No",
    default: str = "yes",
) -> bool:
    """Show a Yes/No modal. Returns True on Yes, False on No or ESC.

    Args:
        title: short header shown in the box top border.
        bullets: optional list of bulleted consequences; rendered as
            `• <line>` and word-wrapped to the box's interior width.
        body: optional one-paragraph elaboration shown below the
            bullets, also word-wrapped.
        yes_label, no_label: button text.
        default: which button starts focused — "yes" or "no".

    Non-TTY: returns the default's truth value (True if default ==
    "yes", False otherwise) without prompting. Lets piped/CI callers
    pass through deterministically.
    """
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        return default == "yes"

    bullets = bullets or []
    focus = "yes" if default == "yes" else "no"

    stream = sys.stderr

    def _paint() -> None:
        out: list[str] = []

        # Top border with title inset: ┌─ title ────────┐
        title_segment = f" {title} " if title else " "
        fill = _BOX_WIDTH - 2 - len(title_segment) - 1   # leading dash + segment + trailing dashes
        # Form: ┌─ title ────...─┐
        top = f"{_TL}{_HORIZ}{title_segment}{_HORIZ * max(0, fill)}{_TR}"
        out.append(top)
        out.append(_blank_row())

        # Bullets — wrap each to inner width, prefix with "• " on
        # first line and "  " on continuation lines.
        for b in bullets:
            wrapped = textwrap.wrap(b, width=_INNER_W - 2) or [""]
            for i, line in enumerate(wrapped):
                prefix = "• " if i == 0 else "  "
                out.append(_text_row(f"{prefix}{line}"))
        if bullets:
            out.append(_blank_row())

        # Body paragraph — wrap to inner width.
        if body.strip():
            for line in textwrap.wrap(body.strip(), width=_INNER_W) or [""]:
                out.append(_text_row(line))
            out.append(_blank_row())

        # Buttons stacked vertically with cursor pointer.
        for name, label in (("yes", yes_label), ("no", no_label)):
            pointer = "›" if name == focus else " "
            btn = f"{pointer} [ {label} ]"
            if name == focus:
                # Inverse-video the focused button; manually place the
                # ANSI codes so they don't break the right-pad math.
                pad = _INNER_W - len(btn)
                out.append(
                    f"{_VERT}  \033[7m{btn}\033[0m{' ' * pad}  {_VERT}"
                )
            else:
                out.append(_text_row(btn))

        out.append(_blank_row())

        # Help line at the bottom of the body.
        hint = "enter confirm  ·  ↑/↓ switch  ·  esc cancel"
        out.append(_text_row(hint))

        # Bottom border.
        out.append(f"{_BL}{_HORIZ * (_BOX_WIDTH - 2)}{_BR}")

        stream.write("\033[H\033[2J")
        # Add a top margin so the modal doesn't sit flush against
        # whatever painted underneath us.
        stream.write("\n\n")
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
                if key in ("up", "down", "k", "j"):
                    focus = "no" if focus == "yes" else "yes"
                elif key == "enter":
                    return focus == "yes"
                elif key in ("esc", "ctrl_c", "eof"):
                    return False
                _paint()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)


# -----------------------------------------------------------------------------
# Internal: row formatters
# -----------------------------------------------------------------------------

def _blank_row() -> str:
    return f"{_VERT}{' ' * (_BOX_WIDTH - 2)}{_VERT}"


def _text_row(text: str) -> str:
    """Pad text to the inner width and wrap with side borders.
    Caller is responsible for keeping `text` within `_INNER_W` chars."""
    padded = text + " " * max(0, _INNER_W - len(text))
    return f"{_VERT}  {padded}  {_VERT}"
