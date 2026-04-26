"""
stack.py — Stage 2 of init: suggest a technology stack.

Input:
    <project>/v84/brief.md        the project brief (from user)
    <project>/v84/profile.yaml    roles list (from stage 1)

Calls the suggest-stack instruction. Output is written into
profile.yaml under a `stack:` block (in-place edit, comments
preserved). Done-ness is checked via that block's presence.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
from typing import Optional

import yaml

from core.context import active_roles
from core.stage import Stage
from ui import Spinner, field_editor
from core.util import (
    default_log_dir,
    instruction_path,
    project_v84_dir,
    v84_docs_root,
)
from llm import LLMConfig, call


# No tools exposed — every uncertainty surfaces as `alternatives`
# in the response, which the user picks from in a follow-up UI.


def suggest_stack(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Propose a technology stack based on brief + active roles."""
    brief = brief.strip()
    if not brief:
        raise ValueError("brief is empty")

    # Stage requires profile.yaml to exist — drives which roles we
    # ask the LLM to fill in.
    profile_file = project_dir / "v84" / "profile.yaml"
    if not profile_file.exists():
        raise FileNotFoundError(
            f"profile.yaml not found at {profile_file}. "
            f"Run the 'roles' stage first."
        )
    roles = active_roles(profile_file)
    if not roles:
        raise RuntimeError(
            f"profile.yaml at {profile_file} has no active_roles."
        )

    # Build the per-role stack-field menu from each active role's YAML.
    # Roles whose `stack:` is empty (brand, integrations) drop out —
    # they don't contribute tech picks.
    fields_block, contributing = build_stack_menu(roles)
    if not contributing:
        raise RuntimeError(
            "no active role contributes stack fields — nothing to propose."
        )

    skill_file = instruction_path("init", "suggest-stack.md")
    if not skill_file.exists():
        raise FileNotFoundError(f"Instruction not found: {skill_file}")
    system = skill_file.read_text(encoding="utf-8")

    user_msgs = [
        f"## Project brief\n\n{brief}",
        fields_block,
        "Propose a technology stack. Follow your output format exactly.",
    ]

    if cfg is None:
        raise ValueError("LLMConfig required — call via v84.py or pass cfg=")

    with Spinner(f"calling {cfg.model} @ {cfg.url}"):
        response = call(
            cfg,
            system=system,
            user_msgs=user_msgs,
            log_name="init-suggest-stack",
            log_dir=default_log_dir(),
            # max_tokens=4096,
        )

    parsed = _parse_stack_proposal(response, contributing)

    # Walk the user through each field — accept recommendation, pick an
    # alternative, type custom, or (for optional fields) skip.
    sections = _to_editor_sections(parsed, contributing)
    confirmed = field_editor(
        sections,
        prompt="Stack proposal — review & customise",
        summary=parsed.get("summary", ""),
    )
    if confirmed is None:
        raise RuntimeError("stack review cancelled")

    profile_path = project_v84_dir(project_dir) / "profile.yaml"
    _write_stack_to_profile(profile_path, confirmed)
    _copy_stack_templates(project_dir, contributing)

    print(f"✓ updated {profile_path} (stack:)", file=sys.stderr)
    return profile_path


# -----------------------------------------------------------------------------
# File wrapping + summary helpers (single-caller, so they live here)
# -----------------------------------------------------------------------------

def _parse_stack_proposal(
    yaml_text: str,
    contributing: list[str],
) -> dict:
    """Parse the LLM's stack response.

    Returns:
        {
          "fields":  {role: {field: {value, recommendation,
                                      alternatives, optional}}},
          "summary": str,
        }

    Cross-references each role's source stack template
    (`v84-docs/init/stack/<role>.yaml`) to backfill the `optional`
    flag — the LLM doesn't return it.
    """
    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as exc:
        raise RuntimeError(f"LLM output was not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("LLM output did not parse as a YAML mapping")

    stack_dir = v84_docs_root() / "init" / "stack"
    fields: dict[str, dict] = {}

    for role in contributing:
        section = data.get(role)
        if not isinstance(section, dict):
            continue

        # Source template gives us the `optional` flags (LLM omits them).
        template: dict = {}
        stack_file = stack_dir / f"{role}.yaml"
        if stack_file.exists():
            template = yaml.safe_load(stack_file.read_text(encoding="utf-8")) or {}

        fields[role] = {}
        for field_name, field_data in section.items():
            if not isinstance(field_data, dict):
                continue
            reco = field_data.get("recommendation")
            alts = field_data.get("alternatives") or []
            optional = bool(template.get(field_name, {}).get("optional"))
            fields[role][field_name] = {
                "value": str(reco) if reco is not None else "",
                "recommendation": str(reco) if reco is not None else "",
                "alternatives": [str(a) for a in alts],
                "optional": optional,
            }

    summary = (data.get("summary") or "").strip()
    return {"fields": fields, "summary": summary}


def _to_editor_sections(parsed: dict, contributing: list[str]) -> list[dict]:
    """Convert parsed proposal into the field_editor section list."""
    roles_dir = v84_docs_root() / "init" / "roles"
    sections: list[dict] = []
    for role in contributing:
        if role not in parsed["fields"]:
            continue
        title = role
        role_file = roles_dir / f"{role}.yaml"
        if role_file.exists():
            data = yaml.safe_load(role_file.read_text(encoding="utf-8")) or {}
            title = data.get("title", role)
        fields_list: list[dict] = []
        for field_name, meta in parsed["fields"][role].items():
            fields_list.append({
                "label": field_name,
                "value": meta["value"],
                "recommendation": meta["recommendation"],
                "alternatives": meta["alternatives"],
                "optional": meta["optional"],
                # Carried so we can rebuild the stack: block in role order.
                "_role": role,
                "_field": field_name,
            })
        sections.append({"title": f"{title} ({role})", "fields": fields_list})
    return sections


def _render_stack_block(sections: list[dict]) -> str:
    """Render the `stack:` block (no leading/trailing blanks) for
    profile.yaml from user-confirmed picks.

    Every field declared in the role's stack template appears —
    skipped optional fields render as `none`. Keeping the full
    schema visible to downstream stages prevents them from
    hallucinating values for fields they can't see.
    """
    out: list[str] = ["stack:"]
    for section in sections:
        if not section["fields"]:
            continue
        role = section["fields"][0]["_role"]
        out.append(f"  {role}:")
        for f in section["fields"]:
            value = (f.get("value") or "").strip()
            if not value:
                value = "none"
            out.append(f"    {f['_field']}: {_yaml_scalar(value)}")
    return "\n".join(out) + "\n"


# Matches a top-level `stack:` block: header line + indented children.
_STACK_BLOCK_RE = re.compile(
    r"(?m)^stack:[ \t]*\n(?:[ \t]+\S.*\n)*",
)


def _write_stack_to_profile(profile_path: Path, sections: list[dict]) -> None:
    """Update profile.yaml's `stack:` block in place. Leaves the rest
    of the file (comments, other blocks) intact.
    """
    block = _render_stack_block(sections)
    text = profile_path.read_text(encoding="utf-8")
    if _STACK_BLOCK_RE.search(text):
        text = _STACK_BLOCK_RE.sub(block, text, count=1)
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += "\n" + block
    profile_path.write_text(text, encoding="utf-8")


def _copy_stack_templates(project_dir: Path, contributing: list[str]) -> None:
    """Copy each contributing role's stack template into the project.

    Mirrors `_copy_role_templates` for roles. Pinning the templates
    locally means later updates to v84-docs can't retroactively
    change a project's stack-field schema (descriptions, optionals,
    field set). Stale entries — for roles no longer contributing —
    are removed so the folder tracks the active picks.
    """
    src_dir = v84_docs_root() / "init" / "stack"
    dst_dir = project_dir / "v84" / "structure" / "stack"
    dst_dir.mkdir(parents=True, exist_ok=True)

    for existing in dst_dir.glob("*.yaml"):
        if existing.stem not in contributing:
            existing.unlink()
            print(f"  removed stale {existing}", file=sys.stderr)

    for name in contributing:
        src = src_dir / f"{name}.yaml"
        if not src.exists():
            continue
        dst = dst_dir / f"{name}.yaml"
        if not dst.exists():
            shutil.copy(src, dst)
            print(f"  copied {name} stack template → {dst}",
                  file=sys.stderr)


def _yaml_scalar(value: str) -> str:
    """Quote a string for YAML if it contains characters that would
    break bare-string parsing. Otherwise return as-is.
    """
    if not value:
        return '""'
    needs_quote = any(c in value for c in ":#@&*![]{}|>'\"%`,")
    if needs_quote or value.strip() != value:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


# -----------------------------------------------------------------------------
# Stack-field menu — fed to the LLM so it knows what fields to fill in
# -----------------------------------------------------------------------------

def build_stack_menu(
    active_roles: list[str],
) -> tuple[str, list[str]]:
    """Render the stack-field menu for each active role that has a
    matching stack template. Reads templates from
    `v84-docs/init/stack/<role>.yaml`. Roles without a template
    (brand, integrations) are silently skipped — absence signals
    "no stack contribution".

    Returns (markdown_block, contributing_role_names).
    """
    stack_dir = v84_docs_root() / "init" / "stack"
    roles_dir = v84_docs_root() / "init" / "roles"
    sections: list[str] = ["## Stack field menu by role"]
    contributing: list[str] = []

    for name in active_roles:
        stack_file = stack_dir / f"{name}.yaml"
        if not stack_file.exists():
            continue
        fields = yaml.safe_load(stack_file.read_text(encoding="utf-8")) or {}
        if not isinstance(fields, dict) or not fields:
            continue

        # Title comes from the role YAML for human display.
        role_file = roles_dir / f"{name}.yaml"
        title = name
        if role_file.exists():
            role = yaml.safe_load(role_file.read_text(encoding="utf-8")) or {}
            title = role.get("title", name)

        contributing.append(name)
        sections.append("")
        sections.append(f"### {title}")
        sections.append(f"role_tag: {name}")
        sections.append("")
        sections.append("#### Fields")
        for field, meta in fields.items():
            meta = meta or {}
            required = "no" if meta.get("optional") else "yes"
            desc = (meta.get("description") or "").strip()
            ex = (meta.get("example") or "").strip()
            sections.append("")
            sections.append(f"field-tag: {field}")
            sections.append(f"required: {required}")
            if desc:
                sections.append(f"description: {desc}")
            if ex:
                sections.append(f"example: {ex}")

    return "\n".join(sections), contributing


# Stage metadata. Stack runs after roles is done. Output goes into
# profile.yaml's `stack:` block, so done-ness is a content check.

def _stack_is_done(project_dir: Path) -> bool:
    profile = project_dir / "v84" / "profile.yaml"
    if not profile.exists():
        return False
    try:
        data = yaml.safe_load(profile.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return False
    block = data.get("stack")
    return isinstance(block, dict) and bool(block)


STAGE = Stage(
    name="stack",
    title="Suggest stack",
    priority=101,
    produces="profile.yaml#stack",
    requires=("roles",),
    needs_brief=True,
    is_done=_stack_is_done,
    call=suggest_stack,
)
