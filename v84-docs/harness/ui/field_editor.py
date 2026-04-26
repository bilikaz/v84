"""
field_editor — three-mode review UI for a structured proposal.

Used by the stack stage so the user can walk a list of fields, open
a single_select-style picker for any one of them, and type custom
values in-place. State machine is internal: review → pick → custom,
with ESC walking back one mode at a time.
"""

from __future__ import annotations

import sys
import termios
import tty
from typing import Any, Optional

from ._term import alt_screen, read_key


def field_editor(
    sections: list[dict],
    *,
    prompt: str = "Review proposal:",
    summary: str = "",
) -> Optional[list[dict]]:
    """Three-mode review UI for a structured proposal.

    Modes (top-to-bottom on screen, header always visible):

        review   list of fields grouped by section (default).
        pick     options for one field (recommendation + alternatives
                 + "none" when optional + "type custom"). Selecting
                 commits the value and returns to review.
        custom   single-line text input for the current field. Empty
                 input cancels back to pick.

    Header is always: prompt line, mode-specific controls hint, blank
    line, summary block (if provided). Body below the header swaps
    per mode.

    Keys:
        ↑/↓      move cursor (review: between fields; pick: between
                 options; custom: ignored)
        space    review→pick; pick: commit current option
        enter    review: confirm whole proposal and return; pick:
                 commit current option; custom: confirm typed value
        esc      go back one mode (custom→pick→review→exit)

    Returns the (mutated) sections list on confirm, or None on
    top-level ESC.

    `sections` is a list of role-section dicts:
        [
          {"title": "Backend",
           "fields": [
             {"label": "language", "value": "Python",
              "alternatives": ["TypeScript", "Go"],
              "optional": False,
              "recommendation": "Python",            # optional — preferred pick
              "recommendation_label": "lead's pick",  # optional override
              "alternative_label": "switch to this",  # optional info on each alt
              "skip_label": "skip this rule",         # optional override
              "custom_label": "write your own",       # optional override
              "optional_tag": "",                     # "" suppresses the
                                                      # default "(optional)"
                                                      # tag in the list view
              ...},
             ...
           ]},
          ...
        ]

    `recommendation_label` overrides the info text on the
    `recommendation` option (only shown when `recommendation` is
    set); defaults to "recommended". `skip_label` overrides the
    info text on the auto-added "none" option (only shown when
    `optional: True`); defaults to "skip this field".
    `custom_label` overrides the info text on the "type custom"
    option; defaults to "type custom". All three are per-field so
    different stages can pick wording that matches their domain
    (rule, field, value, etc.).
    """
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        return sections

    # Flatten into a render list of {kind, ref} so navigation is by
    # row index. "header" rows are visual separators only.
    rows: list[dict[str, Any]] = []
    for section in sections:
        rows.append({"kind": "header", "title": section.get("title", "")})
        for field in section.get("fields", []):
            rows.append({"kind": "field", "field": field})

    first_field_idx = next(
        (i for i, r in enumerate(rows) if r["kind"] == "field"),
        None,
    )
    if first_field_idx is None:
        return sections

    stream = sys.stderr

    # State machine.
    mode = "review"
    cursor = first_field_idx
    pick_field: Optional[dict] = None
    pick_options: list[dict] = []
    pick_cursor = 0
    custom_buffer = ""

    def _move_review(delta: int) -> None:
        nonlocal cursor
        n = len(rows)
        i = cursor
        for _ in range(n):
            i = (i + delta) % n
            if rows[i]["kind"] == "field":
                cursor = i
                return

    def _label(field: dict, key: str, default: str) -> str:
        """Per-field label override that distinguishes "not set" (use
        the default) from "explicitly empty" (render nothing). The
        plain `or` fallback would treat both as missing."""
        val = field.get(key)
        return default if val is None else val

    def _build_pick_options(field: dict) -> list[dict]:
        opts: list[dict] = []
        reco = field.get("recommendation") or ""
        if reco:
            opts.append({
                "name": reco,
                "info": _label(field, "recommendation_label", "recommended"),
            })
        alt_info = _label(field, "alternative_label", "")
        for alt in field.get("alternatives") or []:
            if alt and alt != reco:
                opts.append({"name": alt, "info": alt_info})
        if field.get("optional") and not any(o["name"] == "none" for o in opts):
            opts.append({
                "name": "none",
                "info": _label(field, "skip_label", "skip this field"),
            })
        opts.append({
            "name": "__custom__",
            "info": _label(field, "custom_label", "type custom"),
        })
        return opts

    def _enter_pick() -> None:
        nonlocal mode, pick_field, pick_options, pick_cursor
        pick_field = rows[cursor]["field"]
        pick_options = _build_pick_options(pick_field)
        # Pre-select the field's current value if it appears in opts.
        current = pick_field.get("value") or ""
        pick_cursor = 0
        for i, o in enumerate(pick_options):
            if o["name"] == current:
                pick_cursor = i
                break
        mode = "pick"

    def _commit_pick(name: str) -> None:
        nonlocal mode
        if pick_field is not None:
            pick_field["value"] = name
        mode = "review"

    def _enter_custom() -> None:
        nonlocal mode, custom_buffer
        custom_buffer = ""
        mode = "custom"

    # ---- Painter ------------------------------------------------------------

    def _header_lines() -> list[str]:
        out = [prompt]
        if mode == "review":
            hint = "  (↑/↓ move · space change · enter confirm · esc cancel)"
        elif mode == "pick":
            hint = "  (↑/↓ move · space/enter pick · esc back)"
        else:  # custom
            hint = "  (type a value · enter confirm · esc back)"
        out.append(hint)
        if summary:
            out.append("")
            for line in summary.splitlines():
                out.append(f"  {line}")
        return out

    def _body_lines() -> list[str]:
        out: list[str] = [""]
        if mode == "review":
            for i, r in enumerate(rows):
                if r["kind"] == "header":
                    out.append("")
                    out.append(f"  \033[1m{r['title']}\033[0m")
                    continue
                f = r["field"]
                pointer = "›" if i == cursor else " "
                value = f.get("value") or "(unset)"
                # Default tag for optional fields is "(optional)";
                # caller can override with `optional_tag` (set "" to
                # suppress entirely when the picker's skip_label
                # already conveys it).
                if f.get("optional"):
                    tag_text = f.get("optional_tag", "(optional)")
                    tag = f" {tag_text}" if tag_text else ""
                else:
                    tag = ""
                row = f"  {pointer} {f['label']:<14} {value}{tag}"
                if i == cursor:
                    row = f"\033[7m{row}\033[0m"
                out.append(row)
            return out

        if mode == "pick" and pick_field is not None:
            out.append(f"  \033[1m{pick_field['label']}:\033[0m")
            for i, o in enumerate(pick_options):
                pointer = "›" if i == pick_cursor else " "
                if o["name"] == "__custom__":
                    label = "type custom..."
                else:
                    label = o["name"]
                info = o.get("info", "")
                row = f"  {pointer} {label}"
                if info:
                    row = f"{row}  — {info}"
                if i == pick_cursor:
                    row = f"\033[7m{row}\033[0m"
                out.append(row)
            return out

        # custom
        if pick_field is not None:
            out.append(f"  \033[1m{pick_field['label']}:\033[0m")
        out.append(f"  > {custom_buffer}█")  # block char as caret
        return out

    def _paint() -> None:
        # Home + clear screen — robust to wrapped long lines.
        stream.write("\033[H\033[2J")
        for line in _header_lines() + _body_lines():
            stream.write(f"{line}\n")
        stream.flush()

    # ---- Main loop ----------------------------------------------------------

    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        with alt_screen():
            _paint()
            while True:
                key = read_key(fd)

                if mode == "review":
                    if key == "up":
                        _move_review(-1)
                    elif key == "down":
                        _move_review(1)
                    elif key == "space":
                        _enter_pick()
                    elif key == "enter":
                        return sections
                    elif key in ("esc", "ctrl_c", "eof"):
                        return None

                elif mode == "pick":
                    if key == "up":
                        pick_cursor = (pick_cursor - 1) % len(pick_options)
                    elif key == "down":
                        pick_cursor = (pick_cursor + 1) % len(pick_options)
                    elif key in ("enter", "space"):
                        chosen = pick_options[pick_cursor]
                        if chosen["name"] == "__custom__":
                            _enter_custom()
                        else:
                            _commit_pick(chosen["name"])
                    elif key in ("esc", "ctrl_c", "eof"):
                        mode = "review"

                else:  # custom
                    if key == "enter":
                        text = custom_buffer.strip()
                        if text:
                            _commit_pick(text)
                        else:
                            mode = "pick"
                    elif key in ("esc", "ctrl_c", "eof"):
                        mode = "pick"
                    elif key == "backspace" or key == "\x7f":
                        custom_buffer = custom_buffer[:-1]
                    elif len(key) == 1 and key.isprintable():
                        custom_buffer += key

                _paint()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
