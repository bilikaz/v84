"""
iteration — per-iteration stages (plan, pre-pass, cycle, architect,
            validate, user_review, finish) and registry.

Stage flow:
    plan               → decompose iteration into sub-tasks
    rules_lead         → per-role lead proposes role-internal rules
    rules_architect    → architect proposes cross-role globals
    rules_validate     → per-lead vote on architect's pending globals
    rules_consolidate  → architect dedup pass over surviving lead rules
    user_rules_review  → user gate: promote → cycle, or regenerate pre-pass
    cycle              → per-role pipeline (draft|patch → review → lead),
                         parallel across roles, sequential within
    architect          → cross-role synthesis (blocks until cycle's join)
    architect_validate → either bumps round → cycle, or → user_review
    user_review        → user accepts / rejects rules raised mid-cycle
    finish             → close iteration

The per-role workers (draft_role, patch_role, review_role, lead_role)
are no longer Stage objects; cycle.py orchestrates them.
"""

from __future__ import annotations

from core.stage import Stage

from .architect          import STAGE as _architect_stage,          architect
from .architect_validate import STAGE as _architect_validate_stage, architect_validate
from .cycle              import STAGE as _cycle_stage,              cycle
from .finish             import STAGE as _finish_stage,             finish
from .plan               import STAGE as _plan_stage,               plan
from .rules_architect    import STAGE as _rules_architect_stage,    rules_architect
from .rules_consolidate  import STAGE as _rules_consolidate_stage,  rules_consolidate
from .rules_lead         import STAGE as _rules_lead_stage,         rules_lead
from .rules_validate     import STAGE as _rules_validate_stage,     rules_validate
from .user_review        import STAGE as _user_review_stage,        user_review
from .user_rules_review  import STAGE as _user_rules_review_stage,  user_rules_review


STAGES: tuple[Stage, ...] = tuple(sorted(
    (
        _plan_stage,
        _rules_lead_stage,
        _rules_architect_stage,
        _rules_validate_stage,
        _rules_consolidate_stage,
        _user_rules_review_stage,
        _cycle_stage,
        _architect_stage,
        _architect_validate_stage,
        _user_review_stage,
        _finish_stage,
    ),
    key=lambda s: s.priority,
))

STAGES_BY_NAME: dict[str, Stage] = {s.name: s for s in STAGES}


__all__ = [
    "Stage",
    "STAGES",
    "STAGES_BY_NAME",
    "architect",
    "architect_validate",
    "cycle",
    "finish",
    "plan",
    "rules_architect",
    "rules_consolidate",
    "rules_lead",
    "rules_validate",
    "user_review",
    "user_rules_review",
]
