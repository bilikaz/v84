"""
review_list — generic sectioned list with tick / alternatives /
edit features and a custom action bar.

Two regions stacked vertically: a list of sections (each with rows)
above, a horizontal action bar below, separated by a divider. `tab`
shifts focus between them. `↑/↓` moves within whatever region has
focus; `←/→` is reserved for the action bar.

Internal modes (all single alt-screen takeover):

    list      main list region focused (cursor moves between rows)
    bar       main action bar focused (←/→ moves between buttons)
    pick      alternatives picker for one row (enable_pick=True)
    pick_bar  alternatives picker, action bar focused
    edit      inline text editor on the row's text (enable_edit=True)

The header keymap line redraws on every mode change so the user
always sees what's currently bound.

Returns either `{"action": <name>, "sections": <mutated>}` for a
commit action, or `None` on cancel (esc, with confirm-on-dirty per
painter UX rule 10).
"""

from __future__ import annotations

import sys
import termios
import tty
from copy import deepcopy
from typing import Any, Callable, Optional

from ._term import alt_screen, read_key
from .confirm_modal import confirm_modal
from .text_input import text_input


_DIVIDER_W = 64
_DIVIDER = "─" * _DIVIDER_W


def review_list(
    sections: list[dict],
    *,
    actions: list[dict],
    summary: str = "",
    enable_tick: bool = True,
    enable_pick: bool = False,
    enable_edit: bool = False,
    status_fn: Optional[Callable[[list[dict]], str]] = None,
) -> Optional[dict]:
    """Sectioned list painter with optional tick / pick / edit per
    row and a custom action bar.

    See readme/screens.md §4 for the full spec including row,
    section, and action shapes.

    Args:
        sections: list of {"title", "_meta", "rows": [...]}.
        actions: list of {"name", "label", "key", "kind", "confirm",
            "handler"} bottom-bar entries.
        summary: optional multi-line context line(s) above the
            keymap.
        enable_tick: when True, `space` toggles each row's `ticked`.
        enable_pick: when True, `enter` opens the alternatives
            picker for the cursor row (row needs `alternatives`).
        enable_edit: when True, `e` opens an inline editor on the
            cursor row's `text`.
        status_fn: optional callable(sections) -> str rendered
            beneath the action bar. Re-evaluated on each repaint
            so it reflects live edits.

    Returns:
        On commit: `{"action": <action.name>, "sections": <mutated>}`.
        On cancel: `None`.
    """
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        return None

    sections = deepcopy(sections)   # never mutate caller's input directly
    initial_snapshot = _snapshot(sections)

    # Map of action.key → action; used for direct hotkey dispatch
    # from the list region.
    actions_by_key: dict[str, dict] = {a["key"]: a for a in actions}

    selectable = _flat_positions(sections)
    if not selectable:
        # Nothing to review — caller shouldn't have invoked us; bail
        # cleanly.
        return None

    # ---- mutable state -----------------------------------------------------
    mode = "list"
    list_cursor = 0           # index into `selectable`
    bar_cursor = 0            # index into `actions`
    pick_cursor = 0           # index into the active picker's options
    pick_row_ref: Optional[tuple[int, int]] = None  # (sec_idx, row_idx) being picked
    pick_options: list[str] = []      # alts for the active pick session
    pick_origin_text = ""              # row's text when picker opened
    edit_buffer = ""
    edit_origin = ""
    edit_came_from = "list"   # "list" or "pick" — where to return on esc

    stream = sys.stderr

    # ---- helpers -----------------------------------------------------------

    def _row_at(sec_idx: int, row_idx: int) -> dict:
        return sections[sec_idx]["rows"][row_idx]

    def _move_list(delta: int) -> None:
        nonlocal list_cursor
        n = len(selectable)
        list_cursor = (list_cursor + delta) % n

    def _move_bar(delta: int) -> None:
        nonlocal bar_cursor
        n = len(actions)
        if n == 0:
            return
        bar_cursor = (bar_cursor + delta) % n

    def _move_pick(delta: int) -> None:
        nonlocal pick_cursor
        n = len(pick_options)
        if n == 0:
            return
        pick_cursor = (pick_cursor + delta) % n

    def _open_pick() -> None:
        """Drill into alternatives picker for the cursor row."""
        nonlocal mode, pick_cursor, pick_options, pick_row_ref, pick_origin_text
        sec_idx, row_idx = selectable[list_cursor]
        row = _row_at(sec_idx, row_idx)
        alts = row.get("alternatives") or []
        # Build the picker option list: row's current text first,
        # then each unique alternative.
        cur = (row.get("text") or "").strip()
        options = [cur] if cur else []
        for a in alts:
            a = (a or "").strip()
            if a and a not in options:
                options.append(a)
        if not options:
            return  # nothing to pick from
        pick_options = options
        pick_row_ref = (sec_idx, row_idx)
        pick_origin_text = cur
        # Place cursor on whichever option matches the current text.
        try:
            pick_cursor = options.index(cur)
        except ValueError:
            pick_cursor = 0
        mode = "pick"

    def _close_pick(*, save: bool) -> None:
        """Exit picker. When save=True, set row.text to the picked
        option."""
        nonlocal mode, pick_options, pick_row_ref
        if save and pick_row_ref is not None and pick_options:
            sec_idx, row_idx = pick_row_ref
            _row_at(sec_idx, row_idx)["text"] = pick_options[pick_cursor]
        pick_options = []
        pick_row_ref = None
        mode = "list"

    def _open_edit_from_list() -> None:
        nonlocal mode, edit_buffer, edit_origin, edit_came_from
        sec_idx, row_idx = selectable[list_cursor]
        row = _row_at(sec_idx, row_idx)
        edit_buffer = row.get("text") or ""
        edit_origin = edit_buffer
        edit_came_from = "list"
        mode = "edit"

    def _open_edit_from_pick() -> None:
        nonlocal mode, edit_buffer, edit_origin, edit_came_from
        if not pick_options:
            return
        edit_buffer = pick_options[pick_cursor]
        edit_origin = edit_buffer
        edit_came_from = "pick"
        mode = "edit"

    def _save_edit_and_return() -> None:
        """Save edit_buffer into the active row's text, return to list."""
        nonlocal mode, pick_options, pick_row_ref
        # Where are we writing?
        if pick_row_ref is not None:
            sec_idx, row_idx = pick_row_ref
        else:
            sec_idx, row_idx = selectable[list_cursor]
        _row_at(sec_idx, row_idx)["text"] = edit_buffer
        # After an edit save we always return to the main list — the
        # picker is just a means of choosing starting text.
        pick_options = []
        pick_row_ref = None
        mode = "list"

    def _toggle_tick() -> None:
        if not enable_tick:
            return
        sec_idx, row_idx = selectable[list_cursor]
        row = _row_at(sec_idx, row_idx)
        row["ticked"] = not row.get("ticked", False)

    def _fire_action(action: dict) -> Optional[dict]:
        """Run an action. Returns a result dict to terminate the
        painter, or None to stay in the painter (mutate / cancelled
        confirm)."""
        nonlocal sections, selectable, list_cursor
        kind = action.get("kind", "commit")
        if kind == "commit":
            confirm_spec = action.get("confirm")
            if confirm_spec:
                ok = confirm_modal(
                    title=confirm_spec.get("title", action.get("label", "")),
                    bullets=confirm_spec.get("bullets") or [],
                    body=confirm_spec.get("body", ""),
                    yes_label=confirm_spec.get("yes_label", "Yes"),
                    no_label=confirm_spec.get("no_label", "No"),
                    default=confirm_spec.get("default", "yes"),
                )
                if not ok:
                    return None
            return {"action": action["name"], "sections": sections}

        if kind == "mutate":
            handler = action.get("handler")
            if handler is None:
                return None
            try:
                new_sections = handler(sections)
            except Exception as err:
                # Don't crash the painter; log and stay.
                print(
                    f"  ✗ mutate action {action['name']!r} failed: {err!r}",
                    file=sys.stderr,
                )
                return None
            if isinstance(new_sections, list):
                sections = new_sections
                selectable = _flat_positions(sections)
                if list_cursor >= len(selectable):
                    list_cursor = max(0, len(selectable) - 1)
            return None

        return None  # unknown kind — ignore

    def _try_cancel() -> Optional[dict]:
        """Esc handler for the main list. Returns a result dict
        (None on confirmed-discard) or 'STAY' to keep the painter
        open. We use a bool wrapper so None means 'discard, exit
        painter'."""
        if not _is_dirty(sections, initial_snapshot):
            return None
        # Build the discard confirm bullets from the diff.
        bullets = _dirty_bullets(sections, initial_snapshot)
        ok = confirm_modal(
            title="Discard your changes?",
            bullets=bullets,
            body="Your ticks, edits, and additions are not saved. "
                 "Closing this screen drops them entirely.",
            yes_label="Discard",
            no_label="Keep working",
            default="no",
        )
        if ok:
            return None
        return {"_stay": True}   # marker — caller stays in painter

    # ---- painter -----------------------------------------------------------

    def _keymap_line() -> str:
        if mode == "list":
            parts = ["↑/↓ move"]
            if enable_tick:
                parts.append("space tick")
            if enable_pick:
                parts.append("enter alternatives")
            if enable_edit:
                parts.append("e edit")
            for a in actions:
                parts.append(f"{a['key']} {a['label'].split()[0] if a.get('label') else a['name']}")
            parts.append("tab actions")
            parts.append("esc cancel")
            return " · ".join(parts)
        if mode == "bar":
            return "←/→ select · enter run · tab back · esc cancel"
        if mode == "pick":
            parts = ["↑/↓ move", "space select"]
            if enable_edit:
                parts.append("e edit")
            parts.append("tab actions")
            parts.append("esc back")
            return " · ".join(parts)
        if mode == "pick_bar":
            return "←/→ select · enter run · tab back · esc back"
        if mode == "edit":
            return "type · enter save · esc cancel"
        return ""

    def _render_list() -> list[str]:
        out: list[str] = []
        if summary:
            for line in summary.splitlines():
                out.append(f"  {line}")
            out.append("")
        out.append(f"  ({_keymap_line()})")
        out.append("")

        for sec_idx, section in enumerate(sections):
            title = section.get("title", "")
            if title:
                out.append(f"  \033[1m{title}\033[0m")
                out.append(f"  {'─' * max(4, len(title))}")
                out.append("")
            rows = section.get("rows") or []
            for row_idx, row in enumerate(rows):
                is_cursor = (
                    mode in ("list", "bar")
                    and (sec_idx, row_idx) == selectable[list_cursor]
                )
                out.extend(_render_row(row, is_cursor=is_cursor))
                out.append("")

        out.append(f"  {_DIVIDER}")
        out.extend(_render_action_bar(focused=(mode == "bar")))
        if status_fn is not None:
            try:
                line = status_fn(sections)
            except Exception:
                line = ""
            if line:
                out.append(f"  {line}")
        return out

    def _render_row(row: dict, *, is_cursor: bool) -> list[str]:
        label = row.get("label", "?")
        tag = row.get("tag", "")
        text = row.get("text") or ""
        ticked = bool(row.get("ticked", False))

        pointer = "›" if is_cursor else " "
        if enable_tick:
            box = "[✓]" if ticked else "[ ]"
            head = f" {pointer} {box} {label}"
        else:
            head = f" {pointer} {label}"

        # Right-align tag on the header line.
        if tag:
            pad = max(2, _DIVIDER_W - len(head) - len(tag))
            head = head + " " * pad + tag

        if is_cursor:
            head = f"\033[7m{head}\033[0m"

        lines = [head]
        for body_line in text.splitlines() or [""]:
            lines.append(f"      {body_line}")
        return lines

    def _render_action_bar(*, focused: bool) -> list[str]:
        if not actions:
            return [f"  [esc] cancel"]
        parts: list[str] = []
        for i, a in enumerate(actions):
            label = a.get("label") or a.get("name", "")
            btn = f"[{a['key']}] {label}"
            if focused and i == bar_cursor:
                btn = f"\033[7m{btn}\033[0m"
            parts.append(btn)
        parts.append("[esc] cancel")
        return [f"  {'   '.join(parts)}"]

    def _render_pick() -> list[str]:
        out: list[str] = []
        if pick_row_ref is not None:
            sec_idx, row_idx = pick_row_ref
            label = _row_at(sec_idx, row_idx).get("label", "")
            out.append(f"  {label} — pick or edit")
            out.append("")
        out.append(f"  ({_keymap_line()})")
        out.append("")

        for i, opt in enumerate(pick_options):
            is_cursor = (mode in ("pick", "pick_bar")) and i == pick_cursor
            ticked = (opt == pick_origin_text)
            box = "[✓]" if ticked else "[ ]"
            pointer = "›" if is_cursor else " "
            head = f" {pointer} {box} {opt}".rstrip()
            if is_cursor:
                head = f"\033[7m{head}\033[0m"
            out.append(head)
            out.append("")

        out.append(f"  {_DIVIDER}")
        # Picker has its own action bar — fixed shape for now.
        if mode == "pick_bar":
            select_btn = "[space] select" if bar_cursor == 0 else "[space] select"
            edit_btn = "[e] edit"
            back_btn = "[esc] back"
            buttons = [select_btn, edit_btn, back_btn]
            buttons[bar_cursor] = f"\033[7m{buttons[bar_cursor]}\033[0m"
            out.append(f"  {'   '.join(buttons)}")
        else:
            out.append(f"  [space] select   [e] edit   [esc] back")
        return out

    def _render_edit() -> list[str]:
        out: list[str] = []
        out.append("  Edit")
        out.append(f"  ({_keymap_line()})")
        out.append("")
        # Show the buffer with a block-character caret at the end.
        for line in (edit_buffer or "").splitlines() or [""]:
            out.append(f"  > {line}")
        # Add the caret on the last line.
        if out[-1].endswith(" >") or out[-1].endswith(">"):
            out[-1] = out[-1] + "█"
        else:
            out[-1] = out[-1] + "█"
        return out

    def _paint() -> None:
        if mode in ("pick", "pick_bar"):
            lines = _render_pick()
        elif mode == "edit":
            lines = _render_edit()
        else:
            lines = _render_list()

        stream.write("\033[H\033[2J")
        for line in lines:
            stream.write(f"{line}\n")
        stream.flush()

    # ---- main loop ---------------------------------------------------------

    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        with alt_screen():
            _paint()
            while True:
                key = read_key(fd)

                # ---- LIST ----
                if mode == "list":
                    if key in ("up", "k"):
                        _move_list(-1)
                    elif key in ("down", "j"):
                        _move_list(1)
                    elif key == "space" and enable_tick:
                        _toggle_tick()
                    elif key == "enter" and enable_pick:
                        _open_pick()
                    elif key == "e" and enable_edit:
                        _open_edit_from_list()
                    elif key == "tab":
                        if actions:
                            mode = "bar"
                    elif key in ("esc", "ctrl_c", "eof"):
                        result = _try_cancel()
                        if result is None:
                            return None
                        # _stay marker — keep painter
                    elif key in actions_by_key:
                        result = _fire_action(actions_by_key[key])
                        if result is not None:
                            return result
                    _paint()
                    continue

                # ---- BAR ----
                if mode == "bar":
                    if key == "left":
                        _move_bar(-1)
                    elif key == "right":
                        _move_bar(1)
                    elif key == "tab":
                        mode = "list"
                    elif key == "enter":
                        if actions:
                            result = _fire_action(actions[bar_cursor])
                            if result is not None:
                                return result
                        # mutate stays in same mode (bar focused)
                    elif key in ("esc", "ctrl_c", "eof"):
                        result = _try_cancel()
                        if result is None:
                            return None
                    _paint()
                    continue

                # ---- PICK ----
                if mode == "pick":
                    if key in ("up", "k"):
                        _move_pick(-1)
                    elif key in ("down", "j"):
                        _move_pick(1)
                    elif key == "space":
                        _close_pick(save=True)
                    elif key == "e" and enable_edit:
                        _open_edit_from_pick()
                    elif key == "tab":
                        mode = "pick_bar"
                    elif key in ("esc", "ctrl_c", "eof"):
                        # Picker is non-destructive; silent back.
                        _close_pick(save=False)
                    _paint()
                    continue

                # ---- PICK_BAR ----
                if mode == "pick_bar":
                    # Three buttons: select / edit / back
                    if key == "left":
                        bar_cursor = (bar_cursor - 1) % 3
                    elif key == "right":
                        bar_cursor = (bar_cursor + 1) % 3
                    elif key == "tab":
                        mode = "pick"
                    elif key == "enter":
                        if bar_cursor == 0:           # select
                            _close_pick(save=True)
                        elif bar_cursor == 1:         # edit
                            if enable_edit:
                                _open_edit_from_pick()
                        else:                          # back
                            _close_pick(save=False)
                    elif key in ("esc", "ctrl_c", "eof"):
                        _close_pick(save=False)
                    _paint()
                    continue

                # ---- EDIT ----
                if mode == "edit":
                    if key == "enter":
                        _save_edit_and_return()
                    elif key in ("esc", "ctrl_c", "eof"):
                        if edit_buffer != edit_origin:
                            ok = confirm_modal(
                                title="Discard edit?",
                                bullets=[],
                                body="The text you typed will be lost.",
                                yes_label="Discard",
                                no_label="Keep editing",
                                default="no",
                            )
                            if not ok:
                                _paint()
                                continue
                        # Return to wherever
                        if edit_came_from == "pick":
                            mode = "pick"
                        else:
                            mode = "list"
                    elif key == "backspace" or key == "\x7f":
                        edit_buffer = edit_buffer[:-1]
                    elif len(key) == 1 and key.isprintable():
                        edit_buffer += key
                    _paint()
                    continue

                # Unknown mode (shouldn't happen) — repaint defensively.
                _paint()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)


# -----------------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------------

def _flat_positions(sections: list[dict]) -> list[tuple[int, int]]:
    """Return [(sec_idx, row_idx), ...] for every selectable row.
    Sections without rows are skipped."""
    out: list[tuple[int, int]] = []
    for si, section in enumerate(sections):
        for ri, row in enumerate(section.get("rows") or []):
            if isinstance(row, dict):
                out.append((si, ri))
    return out


def _snapshot(sections: list[dict]) -> list[tuple]:
    """Take a comparable snapshot of every row's tracked state for
    dirty detection. Tuples per row: (label, text, ticked).
    Section ordering is preserved so order is part of identity."""
    out: list[tuple] = []
    for section in sections:
        for row in section.get("rows") or []:
            if not isinstance(row, dict):
                continue
            out.append((
                row.get("label", ""),
                row.get("text", ""),
                bool(row.get("ticked", False)),
            ))
    return out


def _is_dirty(sections: list[dict], snapshot: list[tuple]) -> bool:
    return _snapshot(sections) != snapshot


def _dirty_bullets(
    sections: list[dict], snapshot: list[tuple],
) -> list[str]:
    """Build human-readable bullets describing what changed since
    the snapshot. Used in the discard-changes confirm modal."""
    current = _snapshot(sections)
    snap_by_label = {row[0]: row for row in snapshot}

    n_added = max(0, len(current) - len(snapshot))
    n_tick_changed = 0
    n_text_edited = 0
    for label, text, ticked in current:
        prev = snap_by_label.get(label)
        if prev is None:
            continue
        if prev[1] != text:
            n_text_edited += 1
        if prev[2] != ticked:
            n_tick_changed += 1

    bullets: list[str] = []
    if n_tick_changed:
        bullets.append(f"{n_tick_changed} row(s) ticked differently")
    if n_text_edited:
        bullets.append(f"{n_text_edited} row(s) edited from original")
    if n_added:
        bullets.append(f"{n_added} row(s) added")
    return bullets or ["unsaved state"]
