"""
roles.py — Stage 1 of init: propose roles + user selects + copy templates.

Three phases:

    1. AI propose — cheap LLM call using the propose-roles instruction.
       Produces a starting-point list of active role tags. No tool
       calls, no survey.

    2. User selects — harness-driven multi-select UI. User toggles the
       proposed list, commits when happy. Zero AI. Fast.

    3. Templates copied — for each active role_tag, copy
       <v84-docs>/init/roles/<tag>.yaml into
       <project>/v84/structure/roles/<tag>.yaml so the project owns
       an editable copy. profile.yaml is written with the final list.

Reviewer customisation (editing which reviewers each role uses) is
deferred — see DEFERRED.md. Users can edit structure/roles/<name>.yaml
manually between runs.
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from core.stage import Stage
from ui import Spinner, checklist
from core.util import (
    default_log_dir,
    instruction_path,
    project_v84_dir,
    v84_docs_root,
)
from llm import LLMConfig, call


# No tools exposed — the UI step handles all the user interaction.
# Every decision the LLM might have asked about happens in the
# multi-select UI afterwards.
SUPPORTED_TOOLS: tuple[str, ...] = ()


def select_roles(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Run the three-phase role selection for this project.

    Returns the path to the written profile.yaml.
    """
    brief = brief.strip()
    if not brief:
        raise ValueError("brief is empty")

    # ---- Phase 1: AI proposes ------------------------------------------------
    if cfg is None:
        raise ValueError("LLMConfig required — call via v84.py or pass cfg=")

    preselected, summary = _propose_roles(brief, cfg)

    # ---- Phase 2: User selects ----------------------------------------------
    # Show the AI's summary before the picker so the user has context.
    if summary:
        print("", file=sys.stderr)
        print("AI suggestion:", file=sys.stderr)
        for line in summary.splitlines():
            print(f"  {line}", file=sys.stderr)

    options = _build_role_options()
    active = checklist(
        options,
        prompt="Which roles should be active for this project?",
        preselected=set(preselected),
    )

    if not active:
        raise RuntimeError(
            "no roles selected — a project needs at least one role. "
            "Re-run and pick at least one."
        )

    # ---- Phase 3: Copy templates + write profile.yaml -----------------------
    _copy_role_templates(project_dir, active)

    v84 = project_v84_dir(project_dir)
    out_file = v84 / "profile.yaml"
    out_file.write_text(
        _build_profile_yaml(active, cfg),
        encoding="utf-8",
    )

    print(f"✓ wrote {out_file}", file=sys.stderr)
    print(f"  active roles ({len(active)}): {', '.join(active)}", file=sys.stderr)

    return out_file


# -----------------------------------------------------------------------------
# Phase 1 — AI call
# -----------------------------------------------------------------------------

def _propose_roles(
    brief: str,
    cfg: LLMConfig,
) -> tuple[list[str], str]:
    """Ask the LLM which roles are likely relevant.

    Returns:
        proposed   ordered list of role tags the AI thinks apply
        summary    AI's summary of the project shape + proposal reasoning
                   (empty string when the instruction doesn't request one)
    """
    skill_file = instruction_path("init", "suggest-roles.md")
    if not skill_file.exists():
        raise FileNotFoundError(f"Instruction not found: {skill_file}")
    system = skill_file.read_text(encoding="utf-8")

    # Compact menu — title + role_tag + when_activate text per role.
    # Reviewer definitions, responsibilities, and writer charters are
    # stripped out — they don't affect the pick and would bloat the
    # prompt.
    role_menu = build_role_menu()

    user_msgs = [
        f"## Project brief\n\n{brief}",
        f"## Role menu\n\n{role_menu}",
        "Propose which roles apply. Follow your output format exactly.",
    ]

    with Spinner(f"calling {cfg.model} @ {cfg.url}"):
        response = call(
            cfg,
            system=system,
            user_msgs=user_msgs,
            log_name="init-propose-roles",
            log_dir=default_log_dir(),
            # max_tokens=4096
        )

    return _parse_proposal(response)


def _parse_proposal(yaml_text: str) -> tuple[list[str], str]:
    """Parse the LLM's proposed roles YAML into (role tags, summary).

    Expected shape (from instructions/init/suggest-roles.md):
        roles:
          - backend
          - frontend

    Hallucinated role tags (anything not matching a file in
    init/roles/) are filtered out. `summary` is optional — older
    instructions emitted one; current instruction does not. Returns
    empty string when absent.
    """
    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as exc:
        raise RuntimeError(f"LLM output was not valid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError("LLM output did not parse as a YAML mapping")

    # Accept either `roles:` (current) or `proposed_active:` (legacy)
    # as the list key — one-way-door deprecation, models occasionally
    # fall back to wording from their training data.
    raw_list = data.get("roles") or data.get("proposed_active") or []

    proposed: list[str] = []
    for entry in raw_list:
        # Accept bare strings (current shape) OR dicts with a `name:`
        # key (defensive against model drift).
        if isinstance(entry, str):
            name = entry
        elif isinstance(entry, dict):
            name = entry.get("name")
        else:
            continue
        if isinstance(name, str) and name not in proposed:
            proposed.append(name)

    # Filter hallucinated names against the actual template files.
    valid = set(list_role_names())
    proposed = [n for n in proposed if n in valid]

    # Summary is optional. Kept for backward compat + for later
    # instructions that may bring it back as an explicit field.
    summary = (data.get("summary") or "").strip()

    return proposed, summary


# -----------------------------------------------------------------------------
# Phase 2 — UI helpers
# -----------------------------------------------------------------------------

def _build_role_options() -> list[dict]:
    """Build the checklist options list for the roles picker.

    Each option has:
        name   role_tag (returned as the selection result)
        label  human-readable title shown in the picker
        info   one-line description from `responsibilities:`
    """
    options = []
    for name in list_role_names():
        role = _load_role(name)
        title = role.get("title", name)
        options.append({
            "name": name,
            "label": title,
            "info": role_short_info(name),
        })
    return options


# -----------------------------------------------------------------------------
# Phase 3 — copy templates + write profile.yaml
# -----------------------------------------------------------------------------

def _copy_role_templates(project_dir: Path, active: list[str]) -> None:
    """Copy init/roles/<name>.yaml → structure/roles/<name>.yaml for each.

    Also removes any stale templates in structure/roles/ for roles
    that are no longer active — keeps the folder in sync with the
    selection.
    """
    src_dir = v84_docs_root() / "init" / "roles"
    dst_dir = project_dir / "v84" / "structure" / "roles"
    dst_dir.mkdir(parents=True, exist_ok=True)

    # Remove stale files for roles no longer active
    for existing in dst_dir.glob("*.yaml"):
        if existing.stem not in active:
            existing.unlink()
            print(f"  removed stale {existing}", file=sys.stderr)

    # Copy (or re-copy) active roles
    for name in active:
        src = src_dir / f"{name}.yaml"
        if not src.exists():
            raise FileNotFoundError(f"Role template missing: {src}")
        dst = dst_dir / f"{name}.yaml"
        if not dst.exists():
            shutil.copy(src, dst)
            print(f"  copied {name} template → {dst}", file=sys.stderr)


def _build_profile_yaml(active: list[str], cfg: LLMConfig) -> str:
    """Render the final profile.yaml text.

    Contains v84 defaults (execution_mode, model_tiers, loop), the
    resolved LLM endpoint, and the user-confirmed roles list. Stack
    picks land in this same file under a `stack:` block once the
    stack stage runs.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [
        "# profile.yaml — v84 project profile",
        "#",
        "# Active roles, model tiers, loop parameters, and LLM endpoints",
        "# for this project. The llm: block has two tiers:",
        "#   single — used for stage calls (one agent at a time)",
        "#   multi  — used when 2+ agents run concurrently (optional;",
        "#            falls back to single when absent)",
        "# max_concurrency caps in-flight calls per tier — single defaults",
        "# to 1, multi defaults to 4. Raise on multi to fan out wider.",
        "# Edit the file or run `python3 v84.py --llm-set [URL]` /",
        "# `--llm-set-multi [URL]`.",
        "",
        "project:",
        f"  created: {today}",
        "",
        "llm:",
        "  single:",
        f"    url: {cfg.url}",
        f"    model: {cfg.model}",
        f"    max_concurrency: {cfg.max_concurrency}",
        "",
        "execution_mode: interactive    # interactive | auto",
        "",
        "model_tiers:",
        "  writers:    auto",
        "  reviewers:  auto",
        "  architect:  auto",
        "",
        "loop:",
        "  min_rounds: 1",
        "  max_rounds: 10",
        "  approval_mode: architect",
        "",
        "# --- role selection ---",
        "",
        "roles:",
    ]
    for name in active:
        lines.append(f"  - {name}")

    return "\n".join(lines) + "\n"


# -----------------------------------------------------------------------------
# Role template discovery & access
# -----------------------------------------------------------------------------

def list_role_names() -> list[str]:
    """All role tags available, read from v84-docs/init/roles/*.yaml.

    Each .yaml file's stem is the role_tag. The filesystem is the
    source of truth — adding a role is a matter of dropping a new
    .yaml file in init/roles/. Nothing else needs editing.

    (Function is called `list_role_names` for historical reasons;
    callers treat the strings as role tags everywhere user-visible.)
    """
    roles_dir = v84_docs_root() / "init" / "roles"
    return sorted(f.stem for f in roles_dir.glob("*.yaml"))


def _load_role(name: str) -> dict[str, Any]:
    """Load one role YAML by name. Returns {} if missing or invalid."""
    role_file = v84_docs_root() / "init" / "roles" / f"{name}.yaml"
    if not role_file.exists():
        return {}
    with role_file.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def role_short_info(name: str) -> str:
    """One-line short description for a role, for the UI picker blurb.

    Pulled from the first line of `responsibilities:` — typically a
    concise "this role does X" sentence. Truncated to ~90 chars so
    the picker table stays readable.
    """
    role = _load_role(name)
    text = (role.get("responsibilities") or "").strip()
    if not text:
        return ""
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    if len(first) > 90:
        first = first[:87].rstrip() + "..."
    return first


def build_role_menu() -> str:
    """Compact role menu for the LLM call.

    Extracts name + title + when_activate from each role template.
    Reviewer definitions, responsibilities, and writer charters are
    NOT included — they're irrelevant to the activation decision and
    would bloat the prompt. ~2.7KB total across 8 roles.

    Each entry starts with `### role: <name>` as the boundary marker.
    `###` is visually unambiguous (no prose line starts with `###`),
    and the `role:` prefix labels what the section is about so even
    weak models cannot confuse the identifier with something else.
    """
    summaries = []
    for name in list_role_names():
        role = _load_role(name)
        n = role.get("name", name)
        title = role.get("title", "")
        when = (role.get("when_activate") or "").strip()
        summaries.append(f"### {title}\n\nrole_tag: {n}\n\n{when}")
    return "\n\n".join(summaries)


# -----------------------------------------------------------------------------
# Stage registration
# -----------------------------------------------------------------------------

def _roles_is_done(project_dir: Path) -> bool:
    """Roles is done when profile.yaml has a non-empty `roles:` list.

    Default file-existence check is wrong here because `--llm-set`
    creates profile.yaml with just the llm block, before roles ever
    runs — that would make state detection skip roles and crash the
    stack stage (which needs active_roles).
    """
    profile = project_dir / "v84" / "profile.yaml"
    if not profile.exists():
        return False
    try:
        data = yaml.safe_load(profile.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return False
    block = data.get("roles") or data.get("active_roles")
    return isinstance(block, list) and len(block) > 0


STAGE = Stage(
    name="roles",
    title="Select roles",
    priority=1,
    produces="profile.yaml#roles",
    requires=(),
    needs_brief=True,
    is_done=_roles_is_done,
    call=select_roles,
)
