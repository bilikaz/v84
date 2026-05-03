"""
structure.py — Stage 3 of init: pick the project layout.

Single LLM call proposes:
    - layout_type (monorepo / single-app / flat / scripts)
    - per active role: a list of {name, path, notes} sections

User reviews each role SEQUENTIALLY via field_editor (one role at
a time, not all-at-once — keeps the picker scannable when a
project has many roles). User can accept the AI's proposal as-is,
edit a section's path, drop a section, or add new ones for that
role. ESC at the role-loop level skips the remaining roles
(keeping their AI proposals as-written).

Persisted to <project>/v84/profile.yaml under:

    project:
      layout_type: monorepo
    layout:
      <role>:
        - name: app
          path: apps/web
          notes: |
            Next.js app root.
        - name: ...

No template files under v84/structure/layout/ — there's nothing
template-shaped to store; layout is per-project from scratch.
profile.yaml is the single source of truth for chosen values.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from core.context import active_roles, roles_block, stack_block
from core.stage import Stage
from core.util import default_log_dir, load_instruction, project_v84_dir
from llm import LLMConfig, call_json
from ui import field_editor


# -----------------------------------------------------------------------------
# Stage entry
# -----------------------------------------------------------------------------

def suggest_structure(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Propose layout type + per-role sections. User reviews each
    role sequentially; results land in profile.yaml."""
    brief = brief.strip()
    if not brief:
        raise ValueError("brief is empty")

    profile_file = project_v84_dir(project_dir) / "profile.yaml"
    if not profile_file.exists():
        raise FileNotFoundError(
            f"profile.yaml not found at {profile_file}. "
            f"Run the 'roles' and 'stack' stages first."
        )
    roles = active_roles(profile_file)
    if not roles:
        raise RuntimeError(f"profile.yaml has no active_roles.")

    system, schema = load_instruction("init", "suggest-structure")

    user_msgs = [
        f"## Project brief\n\n{brief}",
        f"## Active roles\n\n{roles_block(project_dir, roles)}",
        f"## Stack picks\n\n{stack_block(project_dir, roles=roles)}",
        "Propose layout_type + per-role sections.",
    ]

    if cfg is None:
        raise ValueError("LLMConfig required — call via v84.py or pass cfg=")

    response = call_json(
        cfg,
        system=system,
        user_msgs=user_msgs,
        response_schema=schema,
        log_name="init-suggest-structure",
        log_dir=default_log_dir(),
    )

    parsed = _parse(response, roles)

    # Build the review sequence. Put `global` first when it exists
    # (project-wide root files set the foundation; reviewing it first
    # primes the user for per-role decisions that nest inside it).
    review_order: list[str] = []
    if parsed["layout"].get("global"):
        review_order.append("global")
    review_order.extend(roles)

    # Sequential per-scope review.
    confirmed: dict[str, list[dict]] = {}
    for i, scope in enumerate(review_order, start=1):
        proposed = parsed["layout"].get(scope) or []
        section = _to_editor_section(scope, proposed)
        result = field_editor(
            [section],
            prompt=f"Layout — review {scope} ({i} of {len(review_order)})",
            summary=(
                f"Layout type: {parsed['layout_type']}\n"
                f"\n"
                f"{parsed['summary']}\n"
                f"\n"
                f"Edit any section's path, drop one with `none`, or write "
                f"a custom path. ESC to skip the remaining scopes."
            ),
        )
        if result is None:
            print(
                f"  ⚠ {scope} review skipped — using AI proposal as-is",
                file=sys.stderr,
            )
            confirmed[scope] = proposed
            continue
        confirmed[scope] = _from_editor_section(result[0], proposed)

    _persist(profile_file, parsed["layout_type"], confirmed)
    print(f"✓ updated {profile_file} (layout:)", file=sys.stderr)
    return profile_file


# -----------------------------------------------------------------------------
# LLM response parsing
# -----------------------------------------------------------------------------

def _parse(data: dict, roles: list[str]) -> dict:
    """Reshape the schema-validated response into layout_type, summary,
    and per-role section lists. Defensive: missing role → empty section
    list (user can add via the editor)."""
    if not isinstance(data, dict):
        raise RuntimeError("structure response was not a mapping")

    layout_type = (data.get("layout_type") or "single-app").strip()
    summary = (data.get("summary") or "").strip()

    layout: dict[str, list[dict]] = {}
    # `global` first if present (cross-role / root scope), then each role.
    scopes = (["global"] if isinstance(data.get("global"), list) else []) + list(roles)
    for scope in scopes:
        raw = data.get(scope)
        if not isinstance(raw, list):
            layout[scope] = []
            continue
        cleaned: list[dict] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            name = (entry.get("name") or "").strip()
            path = (entry.get("path") or "").strip()
            if not name or not path:
                continue
            section: dict[str, Any] = {"name": name, "path": path}
            notes = (entry.get("notes") or "").strip()
            if notes:
                section["notes"] = notes
            cleaned.append(section)
        layout[scope] = cleaned

    return {
        "layout_type": layout_type,
        "summary": summary,
        "layout": layout,
    }


# -----------------------------------------------------------------------------
# field_editor adapter — one section per role's review
# -----------------------------------------------------------------------------

def _to_editor_section(role: str, sections: list[dict]) -> dict:
    """Pack a role's proposed sections into one field_editor section.
    Each `field` is a section: label = section name, value = path,
    no alternatives (user picks "none" to drop or types custom)."""
    fields: list[dict] = []
    for s in sections:
        notes = (s.get("notes") or "").strip()
        label = s["name"]
        if notes:
            # Show notes as part of the label so the user has context.
            label = f"{label}  ({notes[:60]}{'…' if len(notes) > 60 else ''})"
        fields.append({
            "label": label,
            "value": s["path"],
            "recommendation": s["path"],
            "recommendation_label": "",
            "alternatives": [],
            "optional": True,    # offers `none` = drop this section
            "optional_tag": "",
            "skip_label": "drop this section",
            "custom_label": "type a custom path",
            "_name": s["name"],
            "_notes": notes,
        })
    return {"title": role.capitalize(), "fields": fields}


def _from_editor_section(
    section: dict, original: list[dict],
) -> list[dict]:
    """Walk the field_editor result for one role and rebuild its
    sections list. `none` drops the section; everything else
    promotes the value as the new path."""
    out: list[dict] = []
    for field in section["fields"]:
        new_value = (field.get("value") or "").strip()
        if new_value == "none" or not new_value:
            continue   # dropped
        entry: dict[str, Any] = {
            "name": field["_name"],
            "path": new_value,
        }
        notes = field.get("_notes")
        if notes:
            entry["notes"] = notes
        out.append(entry)
    return out


# -----------------------------------------------------------------------------
# Persistence — write layout_type + layout block into profile.yaml
# -----------------------------------------------------------------------------

def _persist(
    profile_path: Path,
    layout_type: str,
    layout: dict[str, list[dict]],
) -> None:
    """Read current profile, set project.layout_type and the layout
    block, write back. Preserves every other field."""
    data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        data = {}
    project = data.setdefault("project", {})
    if not isinstance(project, dict):
        project = {}
        data["project"] = project
    project["layout_type"] = layout_type
    data["layout"] = layout
    profile_path.write_text(
        yaml.safe_dump(
            data,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=10000,
        ),
        encoding="utf-8",
    )


# -----------------------------------------------------------------------------
# Stage glue
# -----------------------------------------------------------------------------

def _structure_is_done(project_dir: Path) -> bool:
    """Done when profile.yaml has a non-empty `layout:` block."""
    profile = project_dir / "v84" / "profile.yaml"
    if not profile.exists():
        return False
    try:
        data = yaml.safe_load(profile.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return False
    block = data.get("layout")
    return isinstance(block, dict) and bool(block)


STAGE = Stage(
    name="structure",
    title="Decide repo layout + per-role sections",
    priority=151,
    produces="profile.yaml#layout",
    requires=("stack",),
    needs_brief=True,
    is_done=_structure_is_done,
    call=suggest_structure,
)
