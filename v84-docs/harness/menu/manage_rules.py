"""
menu.manage_rules — Manage promoted rules.

UI is a single_select list rebuilt each loop iteration. Rows are:

    1. Every existing rule, prefixed with its scope —
       "[global] ..."  / "[<role>] ..."
    2. "+ Add new rule"  (visible affordance)
    3. "Done"            (return to main menu)

Selecting an existing rule opens a Keep / Rewrite / Drop / Cancel
sub-prompt. Selecting "+ Add new" opens a scope picker, then
text_input for the rule body. Every action saves immediately —
no "confirm all" step. ESC at any layer cancels that layer and
returns to the previous screen.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

from core import proposals
from core.context import active_roles
from ui import single_select, text_input


# Public action wired into menu/main.py
def manage_rules(project_dir: Path, cfg: Any, args: Any) -> int:
    return _manage(project_dir)


# -----------------------------------------------------------------------------
# Top-level loop
# -----------------------------------------------------------------------------

def _manage(project_dir: Path) -> int:
    profile = project_dir / "v84" / "profile.yaml"
    if not profile.exists():
        print(
            "\n  ⚠ no profile.yaml — run init first to define active roles.",
            file=sys.stderr,
        )
        input("  press Enter to return to the menu...")
        return 0
    roles = active_roles(profile)

    while True:
        rows = _build_list(project_dir, roles)
        pick = single_select(
            rows,
            prompt="Manage project rules:",
            preselected="__done__",
            allow_custom=False,
        )
        if pick is None or pick == "__done__":
            return 0
        if pick == "__add__":
            _add_new(project_dir, roles)
            continue
        if pick.startswith("edit:"):
            _, scope, rid = pick.split(":", 2)
            _edit_or_drop(project_dir, scope, rid)
            continue


def _build_list(
    project_dir: Path, roles: list[str],
) -> list[dict]:
    """One header per scope, then its rules underneath. Rule rows
    carry no trailing info — the rule text is the value, and crowding
    it with `— <id>` pushed wide rules to wrap. The id is shown in
    the sub-screen when the row is picked.

    Add-new and Done sit under their own visual section at the bottom."""
    rows: list[dict] = []

    for scope in ["global"] + list(roles):
        records = _read_root(project_dir, scope=scope)
        if not records:
            continue
        rows.append({"kind": "header", "title": scope.capitalize()})
        for r in records:
            rid = r.get("id") or "?"
            text = (r.get("text") or "").strip()
            preview = text.replace("\n", " ")
            if len(preview) > 130:
                preview = preview[:127] + "..."
            rows.append({
                "name": f"edit:{scope}:{rid}",
                "label": preview,
            })

    rows.append({"kind": "header", "title": "Actions"})
    rows.append({
        "name": "__add__",
        "label": "+ Add new rule",
        "info": "type a new rule for any scope",
    })
    rows.append({
        "name": "__done__",
        "label": "Done",
        "info": "return to main menu",
    })
    return rows


# -----------------------------------------------------------------------------
# Per-rule actions (Keep / Rewrite / Drop)
# -----------------------------------------------------------------------------

def _edit_or_drop(
    project_dir: Path, scope: str, rid: str,
) -> None:
    records = _read_root(project_dir, scope=scope)
    target = next((r for r in records if r.get("id") == rid), None)
    if target is None:
        print(f"  ⚠ {rid} no longer exists in v84/{_filename(scope)}",
              file=sys.stderr)
        return
    text = (target.get("text") or "").strip()

    options = [
        {"name": "keep",    "label": "Keep",    "info": "no change"},
        {"name": "rewrite", "label": "Rewrite", "info": "type new rule text"},
        {"name": "drop",    "label": "Drop",    "info": "delete this rule"},
    ]
    action = single_select(
        options,
        prompt=f"{rid} — what to do?",
        summary=f"Scope: {scope}\n\n{text}",
        preselected="keep",
        allow_custom=False,
    )
    if action is None or action == "keep":
        return

    if action == "drop":
        new_records = [r for r in records if r.get("id") != rid]
        _write_root(project_dir, scope=scope, records=new_records)
        print(f"  ✓ dropped {rid}", file=sys.stderr)
        return

    if action == "rewrite":
        new_text = text_input(
            prompt=f"New text for {rid}:",
            summary=f"Scope: {scope}\nCurrent:\n{text}",
        )
        if new_text is None:
            return
        new_text = new_text.strip()
        if not new_text or new_text == text:
            return
        for r in records:
            if r.get("id") == rid:
                r["text"] = new_text
                break
        _write_root(project_dir, scope=scope, records=records)
        print(f"  ✓ rewrote {rid}", file=sys.stderr)


# -----------------------------------------------------------------------------
# Add-new
# -----------------------------------------------------------------------------

def _add_new(
    project_dir: Path, roles: list[str],
) -> None:
    scope_options: list[dict] = [
        {"name": "global", "label": "Global", "info": "applies to every role"},
    ]
    for role in roles:
        scope_options.append({
            "name": role,
            "label": role.capitalize(),
            "info": f"applies only to {role}",
        })

    scope = single_select(
        scope_options,
        prompt="New rule — pick the scope:",
        preselected="global",
        allow_custom=False,
    )
    if scope is None:
        return

    text = text_input(
        prompt="Type the rule's text (one short prose line):",
        summary=f"Scope: {scope}",
    )
    if text is None:
        return
    text = text.strip()
    if not text:
        return

    existing = _read_root(project_dir, scope=scope)
    prefix = f"v84-user.{scope}.rule"
    next_n = proposals.next_index_for_prefix(existing, prefix)
    record = {"id": f"{prefix}.{next_n}", "text": text}
    existing.append(record)
    _write_root(project_dir, scope=scope, records=existing)
    print(
        f"  ✓ added {record['id']} → v84/{_filename(scope)}",
        file=sys.stderr,
    )


# -----------------------------------------------------------------------------
# IO helpers
# -----------------------------------------------------------------------------

def _filename(scope: str) -> str:
    return f"{scope}.rules.yaml"


def _path(project_dir: Path, scope: str) -> Path:
    return project_dir / "v84" / _filename(scope)


def _read_root(project_dir: Path, *, scope: str) -> list[dict]:
    p = _path(project_dir, scope)
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        return []
    return [r for r in data if isinstance(r, dict)]


def _write_root(
    project_dir: Path, *, scope: str, records: list[dict],
) -> None:
    p = _path(project_dir, scope)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        if p.exists():
            p.unlink()
        return
    p.write_text(
        yaml.safe_dump(records, default_flow_style=False, sort_keys=False,
                       allow_unicode=True, width=10000),
        encoding="utf-8",
    )
