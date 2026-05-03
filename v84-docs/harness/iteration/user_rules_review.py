"""
user_rules_review.py — Pre-pass user gate.

Fires after rules_consolidate. Same review_list shape as the
iter-close user_review, but ticked rules promote to project-root
files BEFORE the iteration's actions are drafted, so writers
read the user-finalised rule set on first draft.

Two terminal actions:

    [c] continue   — promote ticked rules to project root, then
                     initialise the cycle pipeline (next_step=cycle
                     with every active role parked at draft) so
                     the iteration's actions get drafted next.

    [r] regenerate — promote ticked rules to project root, then
                     clear pre-pass artifacts (per-role rules
                     files + iteration-level global.rules.yaml +
                     classifications cache) and reset next_step
                     to rules_lead so the pre-pass re-runs against
                     the now-richer root rule set.

Mid-iteration rule raises by writers / reviewers / architect during
the cycle still flow through the existing iter-close user_review;
this stage handles only the pre-pass output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core import coreyaml, iter_status, proposals
from core.context import active_roles
from core.stage import Stage
from llm import LLMConfig
from ui import review_list, spinner

# Reuse the user_review helpers — the rule-promotion mechanics are
# identical at both the pre-pass gate and the iter-close gate.
from iteration.user_review import (
    _apply_classifications,
    _build_summary,
    _collect_accepted,
    _load_or_classify_rules,
    _promote_all,
    _status_line,
    _writeback_declines,
    _writeback_edits,
)


def user_rules_review(
    project_dir: Path,
    brief: str,
    *,
    cfg: Optional[LLMConfig] = None,
) -> Path:
    """Show pre-pass accepted rules to the user; on commit, promote
    + either continue (start cycle) or regenerate (restart pre-pass)."""
    data = coreyaml.read(project_dir)
    parent_id = data.get("current_iteration")
    if not parent_id:
        raise RuntimeError(
            "no current_iteration set in core.yaml — user_rules_review "
            "needs an in-flight iteration"
        )
    iteration_n = _iteration_number(parent_id)
    parent = coreyaml.find_by_id(data, parent_id)

    profile = project_dir / "v84" / "profile.yaml"
    roles = active_roles(profile)
    if not roles:
        raise RuntimeError("no active roles in profile.yaml")

    bundle = _collect_accepted(project_dir, iteration_n, roles)
    total = sum(len(s.get("rows") or []) for s in bundle["sections"])
    if total == 0:
        # Nothing accepted from the pre-pass — just enter the cycle.
        spinner.log(
            "  (pre-pass produced no accepted rules — entering cycle)"
        )
        _enter_cycle(project_dir, iteration_n, profile)
        return project_dir / "v84" / "core.yaml"

    classifications = _load_or_classify_rules(
        project_dir=project_dir,
        parent=parent,
        iteration_n=iteration_n,
        bundle=bundle,
        cfg=cfg,
    )
    _apply_classifications(bundle, classifications)

    summary = _build_pre_pass_summary(iteration_n, total)
    result = review_list(
        bundle["sections"],
        summary=summary,
        enable_tick=True,
        enable_pick=True,
        enable_edit=True,
        actions=[
            {
                "name":  "continue",
                "key":   "c",
                "label": "promote & continue",
                "kind":  "commit",
                "confirm": {
                    "title": "Promote and start drafting",
                    "bullets": [
                        "Promote ticked rules to project root",
                        "Initialise the cycle pipeline (round 1, draft)",
                    ],
                    "body": "Writers will draft actions against the "
                            "user-finalised rule set.",
                },
            },
            {
                "name":  "regenerate",
                "key":   "r",
                "label": "promote & regenerate pre-pass",
                "kind":  "commit",
                "confirm": {
                    "title": "Promote and re-run pre-pass",
                    "bullets": [
                        "Promote ticked rules to project root",
                        "Clear iteration rules + globals + classifications",
                        "Reset to rules_lead so pre-pass re-runs",
                    ],
                    "body": "The next pre-pass round reads the freshly "
                            "promoted root rules as binding context.",
                },
            },
        ],
        status_fn=_status_line,
    )
    if result is None:
        raise RuntimeError(
            "user_rules_review cancelled — re-run when ready to settle "
            "the pre-pass output"
        )

    promote: list[dict] = []
    declined: list[dict] = []
    for section in result["sections"]:
        meta = section["_meta"]
        for row in section.get("rows") or []:
            record = row.get("_record")
            if record is None:
                continue
            if row.get("ticked"):
                promote.append({
                    **meta,
                    "record": record,
                    "final_text": (row.get("text") or "").strip(),
                })
            else:
                declined.append({**meta, "record": record})

    _promote_all(project_dir, promote)
    _writeback_edits(project_dir, iteration_n, promote)
    _writeback_declines(project_dir, iteration_n, declined)

    if result["action"] == "continue":
        _enter_cycle(project_dir, iteration_n, profile)
        kept = len(promote)
        msg = f"{kept} rule(s) promoted to project root"
        if declined:
            msg += f"; {len(declined)} kept iteration-only"
        spinner.log(
            f"  ✓ pre-pass settled — entering cycle. {msg}"
        )
    else:   # regenerate
        _restart_pre_pass(project_dir, iteration_n, profile)
        spinner.log(
            f"  ✓ {len(promote)} rule(s) promoted "
            f"({len(declined)} declined). Restarting pre-pass against "
            f"the new root rule set."
        )
    return project_dir / "v84" / "core.yaml"


# -----------------------------------------------------------------------------
# Branch handlers
# -----------------------------------------------------------------------------

def _enter_cycle(project_dir: Path, iteration_n: int, profile: Path) -> None:
    """Initialise the per-role cycle pipeline so cycle picks up next."""
    iter_status.init_pipeline(
        project_dir, iteration_n,
        round=1,
        roles=active_roles(profile),
        starting_step=iter_status.STEP_DRAFT,
    )


def _restart_pre_pass(
    project_dir: Path, iteration_n: int, profile: Path,
) -> None:
    """Clear pre-pass artifacts and reset next_step to rules_lead.

    Kept on disk:
        - status.yaml (rewritten to next_step=rules_lead)
        - plan.yaml (iteration's sub-task plan)

    Cleared:
        - iterations/<n>/global.rules.yaml (architect's pending/accepted/
          rejected globals — promoted ones now live in
          <project>/v84/global.rules.yaml)
        - iterations/<n>/<role>.rules.yaml (lead packs — promoted ones
          now live in <project>/v84/<role>.rules.yaml)
        - iterations/<n>/rule_classifications.yaml (stale bucket cache)
        - iterations/<n>/cache/*.md (rendered context blocks reflecting
          the old rule set)
    """
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    roles = active_roles(profile)

    plain_unlink: list[Path] = [
        iter_dir / "global.rules.yaml",
        iter_dir / "rule_classifications.yaml",
    ]
    for role in roles:
        plain_unlink.append(iter_dir / f"{role}.rules.yaml")
    for p in plain_unlink:
        if p.exists():
            p.unlink()

    cache_dir = iter_dir / "cache"
    if cache_dir.exists():
        for f in cache_dir.glob("*.md"):
            f.unlink()

    iter_status.write(
        project_dir, iteration_n,
        round=1,
        next_step=iter_status.STEP_RULES_LEAD,
        roles=None,
    )


# -----------------------------------------------------------------------------
# UI summary
# -----------------------------------------------------------------------------

def _build_pre_pass_summary(iteration_n: int, total: int) -> str:
    return (
        f"Iteration {iteration_n} pre-pass produced {total} "
        f"accepted rule(s).\n"
        f"Tick the rules to PROMOTE to project root (binding for "
        f"future iterations).\n"
        f"Untick to keep iteration-only. Continue starts drafting; "
        f"regenerate re-runs the\n"
        f"pre-pass against the just-promoted root rules."
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
        return False
    iteration_n = _iteration_number(parent_id)
    return iter_status.stage_is_done(
        project_dir, iteration_n, "user_rules_review",
    )


STAGE = Stage(
    name="user_rules_review",
    title="Pre-pass user gate (promote ticked rules → cycle or regenerate)",
    priority=1050,
    produces="<project>/v84/{global,<role>}.rules.yaml",
    requires=("rules_consolidate",),
    needs_brief=False,
    is_done=_is_done,
    call=user_rules_review,
)
