"""
user_review.py — Iteration close + user-approval gate.

Fires when the cycle has converged (validate saw no pending
corrections). The user's surface here is conv/dec only — actions
are a derived artifact of (rules + plan + role definitions), so
once the user has signed off on the rules and plan, the actions
follow by construction (and have already passed 4 reviewers ×
each round + lead + architect + validate).

Flow:

    1. Read every accepted convention/decision from the iteration:
       per-role files filtered to status: accepted, plus the
       architect's globals from iterations/<n>/global.{conventions,
       decisions}.yaml.
    2. Show them to the user via the same field_editor used by the
       stack stage. Each entry is one field; user can keep the
       lead's chosen rule, pick an alternative, type a custom form,
       or decline (pick "none").
    3. Promote every non-declined entry to project-root files —
       <project>/v84/<role>.{conventions,decisions}.yaml /
       <project>/v84/global.{conventions,decisions}.yaml — using
       the user's finalised wording (lead's rule, picked alt, or
       custom text).
    4. Decide close-vs-restart by whether any KEPT rule's text
       changed:
         - No change (everything kept as-is, even if some declined)
           → close iteration. Existing actions still satisfy any
           rules that survived; declines only relax constraints,
           never add new ones.
         - At least one change (alt or custom) → clear cycle
           artifacts and reset to {round: 1, next_step: draft}.
           The new draft pass reads the updated rule set from
           project root.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from core import coreyaml, iter_status, proposals
from core.context import active_roles
from core.stage import Stage
from iteration.handoff import write_handoff
from llm import LLMConfig
from ui import field_editor


# -----------------------------------------------------------------------------
# Stage entry
# -----------------------------------------------------------------------------

def user_review(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Show accepted conv/dec to user; on full accept, promote + close."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        raise RuntimeError(
            "no current_iteration set in core.yaml — user_review needs "
            "an in-flight iteration"
        )
    iteration_n = _iteration_number(parent_id)

    profile = project_dir / "v84" / "profile.yaml"
    roles = active_roles(profile)
    if not roles:
        raise RuntimeError("no active roles in profile.yaml")

    # Gather every accepted entry from per-role + globals.
    bundle = _collect_accepted(project_dir, iteration_n, roles)
    total = sum(len(s["fields"]) for s in bundle["sections"])
    if total == 0:
        # Nothing to promote — render the handoff (actions still
        # need to ship even when no new rules accumulated) then
        # advance to the finish stage which verifies coverage.
        print(
            "  (no accepted conv/dec from this iteration to review)",
            file=sys.stderr,
        )
        write_handoff(project_dir, iteration_n)
        iter_status.advance_to(project_dir, iteration_n, "finish")
        return project_dir / "v84" / "core.yaml"

    # Show the field_editor.
    summary = _build_summary(iteration_n, total)
    result = field_editor(
        bundle["sections"],
        prompt="Review accepted conventions and decisions:",
        summary=summary,
    )
    if result is None:
        raise RuntimeError(
            "user_review cancelled — re-run when ready to settle "
            "this iteration"
        )

    # Walk results: every non-declined entry promotes with the
    # user's finalised value. Declined entries don't promote.
    #
    # Restart criterion is "did any KEPT rule's text change?", not
    # set-equality. Dropping a rule only REMOVES a constraint —
    # the existing content was drafted under a stricter rule and
    # still satisfies the looser (now non-existent) requirement.
    # CHANGING a rule (picking an alt or writing custom) replaces
    # the constraint with a different one that existing content
    # may now violate — that's where regen is genuinely needed.
    promote: list[dict] = []   # {scope, role|None, kind, record, final_rule}
    declined: list[dict] = []  # {scope, role|None, kind, record}
    any_changed = False        # at least one kept rule's text differs

    for section in result:
        meta = section["_meta"]
        for field in section["fields"]:
            original = field["_original"]
            new_value = (field.get("value") or "").strip()
            if new_value == "none" or not new_value:
                declined.append({**meta, "record": field["_record"]})
                continue
            if new_value != original:
                any_changed = True
            promote.append({
                **meta,
                "record": field["_record"],
                "final_rule": new_value,
            })

    # Promote every non-declined entry (unchanged, picked alt, or
    # custom text). Picked/custom values become the rule.
    _promote_all(project_dir, promote)
    _writeback_edits(project_dir, iteration_n, promote)
    _writeback_declines(project_dir, iteration_n, declined)

    if not any_changed:
        # No kept rule's text changed. Even if some were declined,
        # the existing drafts/corrections still satisfy whatever
        # rules survived (declines only relax constraints, never
        # add new ones). Render the handoff document for the
        # external implementer, then advance to the finish stage —
        # the iteration only TRULY closes once finish verifies
        # every action's files exist and carry the right tag.
        write_handoff(project_dir, iteration_n)
        iter_status.advance_to(project_dir, iteration_n, "finish")
        kept = len(promote)
        msg = f"{kept} rule(s) promoted to project root as-is"
        if declined:
            msg += (
                f"; {len(declined)} declined (existing content still "
                f"valid — declines only remove constraints)"
            )
        print(
            f"  ✓ rules promoted, handoff written — next: run your "
            f"implementer, then re-run v84 for the finish gate. {msg}",
            file=sys.stderr,
        )
    else:
        # At least one kept rule's text changed (alt or custom).
        # Existing actions were drafted under the OLD wording and
        # may violate the new — clean cycle artifacts and restart
        # from draft so writers re-emit against the new rule set.
        _restart_cycle(project_dir, iteration_n, profile)
        changed_count = sum(
            1 for it in promote
            if it["final_rule"] != _original_rule_for(it["record"])
        )
        print(
            f"  ✓ {len(promote)} rule(s) promoted "
            f"({changed_count} changed, {len(declined)} declined). "
            f"At least one rule's text changed — clearing cycle "
            f"artifacts and restarting drafting against the new "
            f"rule set.",
            file=sys.stderr,
        )
    return project_dir / "v84" / "core.yaml"


def _original_rule_for(record: dict) -> str:
    """Re-derive the lead's original rule text for a record."""
    return (record.get("rule") or record.get("proposal") or "").strip()


# -----------------------------------------------------------------------------
# Read accepted entries → field_editor sections
# -----------------------------------------------------------------------------

def _collect_accepted(
    project_dir: Path, iteration_n: int, roles: list[str],
) -> dict:
    """Build the {sections} payload for field_editor + remember per-record
    metadata (scope/role/kind) so we can route promotions later."""
    sections: list[dict] = []

    # Globals first.
    for kind in ("conventions", "decisions"):
        records = _read_global(project_dir, iteration_n, kind, "accepted")
        if records:
            sections.append(_make_section(
                title=f"Global {kind}",
                records=records,
                meta={"scope": "global", "role": None, "kind": kind},
            ))

    # Then per role.
    for role in roles:
        for kind in ("conventions", "decisions"):
            reader = (proposals.accepted_conventions if kind == "conventions"
                      else proposals.accepted_decisions)
            records = reader(project_dir, iteration_n, role)
            if records:
                sections.append(_make_section(
                    title=f"{role.capitalize()} {kind}",
                    records=records,
                    meta={"scope": "role", "role": role, "kind": kind},
                ))

    return {"sections": sections}


def _make_section(*, title: str, records: list[dict], meta: dict) -> dict:
    """Pack records into a field_editor section with embedded metadata.

    `recommendation` = lead's chosen rule (top-of-picker, "lead's
    accepted rule"). `alternatives` = the original `proposal` plus
    the agent's `alternatives` list — i.e. every form that was on
    the table when the lead chose. Field_editor dedupes against
    the recommendation so a rule that matches the proposal or an
    alternative doesn't double-render.
    """
    fields: list[dict] = []
    for r in records:
        rule = (r.get("rule") or r.get("proposal") or "").strip()
        proposal = (r.get("proposal") or "").strip()
        original_alts = [str(a).strip() for a in (r.get("alternatives") or [])
                         if str(a).strip()]
        # Build the full option pool: proposal first (if present),
        # then original alternatives. field_editor will drop any
        # entry equal to `recommendation` so we don't repeat the rule.
        seen: set[str] = set()
        all_options: list[str] = []
        if proposal:
            all_options.append(proposal)
            seen.add(proposal)
        for alt in original_alts:
            if alt not in seen:
                all_options.append(alt)
                seen.add(alt)

        fields.append({
            "label": r.get("id", "?"),
            "value": rule,
            "recommendation": rule,    # top of picker — preselected
            "recommendation_label": "",
            "alternatives": all_options,
            "optional": True,    # so field_editor offers a "none" option = decline
            "optional_tag": "",  # suppress "(optional)" in the list view
            "alternative_label": "",
            "skip_label": "",
            "custom_label": "",
            "_original": rule,
            "_record": r,
        })
    return {"title": title, "fields": fields, "_meta": meta}


def _read_global(
    project_dir: Path, iteration_n: int, kind: str, status: str,
) -> list[dict]:
    """Read iterations/<n>/global.<kind>.yaml filtered to a status."""
    p = (project_dir / "v84" / "iterations" / str(iteration_n)
         / f"global.{kind}.yaml")
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        return []
    return [r for r in data if isinstance(r, dict) and r.get("status") == status]


# -----------------------------------------------------------------------------
# Promotion to project root
# -----------------------------------------------------------------------------

def _promote_all(project_dir: Path, items: list[dict]) -> None:
    """Promote each item to its destination root file using the
    user's `final_rule` text (which may be the lead's original rule,
    a picked alternative, or custom-typed wording). Root records
    carry only id + rule — pending-time fields drop off."""
    by_dest: dict[tuple, list[dict]] = {}
    for it in items:
        key = (it["scope"], it["role"], it["kind"])
        by_dest.setdefault(key, []).append({
            "id": it["record"].get("id"),
            "rule": it["final_rule"],
        })

    for (scope, role, kind), records in by_dest.items():
        if scope == "global" and kind == "conventions":
            proposals.append_project_conventions(project_dir, records)
            label = "global.conventions.yaml"
        elif scope == "global" and kind == "decisions":
            proposals.append_project_decisions(project_dir, records)
            label = "global.decisions.yaml"
        elif scope == "role" and kind == "conventions":
            proposals.append_project_role_conventions(project_dir, role, records)
            label = f"{role}.conventions.yaml"
        else:
            proposals.append_project_role_decisions(project_dir, role, records)
            label = f"{role}.decisions.yaml"
        print(
            f"  ✓ promoted {len(records)} rule(s) → v84/{label}",
            file=sys.stderr,
        )


# -----------------------------------------------------------------------------
# Edits / declines write-back to iteration files
# -----------------------------------------------------------------------------

def _writeback_edits(
    project_dir: Path, iteration_n: int, edits: list[dict],
) -> None:
    """For each edited entry (user picked an alternative or wrote
    custom text), update the rule field in the iteration file and
    flag `edited_by_user: true` so Step 2 (action review) can tell
    which rules diverged from the lead's original wording — those
    are the candidates for action regeneration."""
    for it in edits:
        rid = it["record"].get("id")
        new_rule = it["final_rule"]
        path = _resolve_iteration_path(project_dir, iteration_n, it)
        records = _read_iteration_file(path)
        for r in records:
            if r.get("id") == rid:
                r["rule"] = new_rule
                r["edited_by_user"] = True
                break
        _write_iteration_file(path, records)


def _writeback_declines(
    project_dir: Path, iteration_n: int, declines: list[dict],
) -> None:
    """For each declined entry, mark status: rejected_by_user so the
    record stays for audit but no longer counts as accepted."""
    for it in declines:
        rid = it["record"].get("id")
        path = _resolve_iteration_path(project_dir, iteration_n, it)
        records = _read_iteration_file(path)
        for r in records:
            if r.get("id") == rid:
                r["status"] = "rejected_by_user"
                break
        _write_iteration_file(path, records)


def _resolve_iteration_path(
    project_dir: Path, iteration_n: int, item: dict,
) -> Path:
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    if item["scope"] == "global":
        return iter_dir / f"global.{item['kind']}.yaml"
    return iter_dir / f"{item['role']}.{item['kind']}.yaml"


def _read_iteration_file(p: Path) -> list[dict]:
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def _write_iteration_file(p: Path, records: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(records, default_flow_style=False, sort_keys=False,
                       allow_unicode=True, width=10000),
        encoding="utf-8",
    )


# -----------------------------------------------------------------------------
# Iteration close
# -----------------------------------------------------------------------------

def _restart_cycle(project_dir: Path, iteration_n: int, profile: Path) -> None:
    """Clear the iteration so drafting re-runs from scratch against
    the user's finalised rule set (now sitting in project-root
    conv/dec files).

    Kept on disk:
        - status.yaml (reset to {round: 1, next_step: draft})
        - plan.yaml (iteration's sub-task plan, independent of rules)

    Deleted (everything else regenerates):
        - <role>.yaml (writer drafts)
        - <role>.corrections{,-applied,-rejected}.yaml
        - <role>.conventions.yaml + <role>.decisions.yaml
          (promoted rules now live in <project>/v84/<role>.*.yaml;
          declined entries are dropped entirely)
        - global.conventions.yaml + global.decisions.yaml
          (promoted globals now live in <project>/v84/global.*.yaml)
        - reviews/<role>.<reviewer>.yaml (per-lens suggestions)
    """
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    roles = active_roles(profile)

    cycle_files: list[Path] = [
        iter_dir / "global.conventions.yaml",
        iter_dir / "global.decisions.yaml",
    ]
    for role in roles:
        cycle_files.extend([
            iter_dir / f"{role}.yaml",
            iter_dir / f"{role}.corrections.yaml",
            iter_dir / f"{role}.corrections-applied.yaml",
            iter_dir / f"{role}.corrections-rejected.yaml",
            iter_dir / f"{role}.conventions.yaml",
            iter_dir / f"{role}.decisions.yaml",
        ])
    for p in cycle_files:
        if p.exists():
            p.unlink()

    reviews_dir = iter_dir / "reviews"
    if reviews_dir.exists():
        for f in reviews_dir.glob("*.yaml"):
            f.unlink()

    # Wipe the rendered-context cache too — rules just changed,
    # so cached blocks like conventions_block / decisions_block
    # would still reflect the old rule set if their source mtimes
    # didn't change in a way that invalidates them.
    cache_dir = iter_dir / "cache"
    if cache_dir.exists():
        for f in cache_dir.glob("*.md"):
            f.unlink()

    iter_status.write(project_dir, iteration_n, round=1, next_step="draft")


# -----------------------------------------------------------------------------
# UI summary builder
# -----------------------------------------------------------------------------

def _build_summary(iteration_n: int, total: int) -> str:
    return (
        f"Iteration {iteration_n} produced {total} accepted "
        f"convention(s) and decision(s). The actions you'll see\n"
        f"in the next step were drafted with these rules in scope. "
        f"If you OVERRIDE or DECLINE any rule below, the cycle\n"
        f"will regenerate so the actions reflect your changes. "
        f"Accept the lead's wording as-is to keep the current draft."
    )


# -----------------------------------------------------------------------------
# Stage glue
# -----------------------------------------------------------------------------

def _iteration_number(task_id: str) -> int:
    return int(task_id.split(".")[0].split("-")[1])


def _is_done(project_dir: Path) -> bool:
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        return True   # iteration already closed
    iteration_n = _iteration_number(parent_id)
    return iter_status.stage_is_done(project_dir, iteration_n, "user_review")


STAGE = Stage(
    name="user_review",
    title="User reviews accepted conv/dec; iteration close",
    priority=1404,
    produces="iterations/<n>/status.yaml#next_step=done",
    requires=("validate",),
    needs_brief=False,
    is_done=_is_done,
    call=user_review,
)
