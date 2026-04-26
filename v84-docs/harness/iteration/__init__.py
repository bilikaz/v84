"""
iteration — per-iteration stages (plan, cycle, close) and registry.

Mirrors `init/__init__.py` shape: each stage module exports STAGE +
its public function; this file collects them in priority order.

Currently shipping:
    plan        decompose a top-level task into sub-tasks for the
                cycle. Two-shape agent (TASKS / QUESTIONS), Q&A
                round via field_editor.

Future (DEFERRED.md):
    cycle       writers → reviewers → architect rounds
    close       merge delta into documentation/, advance core.yaml
"""

from __future__ import annotations

from core.stage import Stage

from .architect    import STAGE as _architect_stage,    architect
from .draft        import STAGE as _draft_stage,        draft
from .finish       import STAGE as _finish_stage,       finish
from .lead         import STAGE as _lead_stage,         lead
from .patch        import STAGE as _patch_stage,        patch
from .plan         import STAGE as _plan_stage,         plan
from .review       import STAGE as _review_stage,       review
from .user_review  import STAGE as _user_review_stage,  user_review
from .validate     import STAGE as _validate_stage,     validate


STAGES: tuple[Stage, ...] = tuple(sorted(
    (
        _plan_stage,
        _draft_stage,
        _review_stage,
        _lead_stage,
        _architect_stage,
        _validate_stage,
        _patch_stage,
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
    "draft",
    "finish",
    "lead",
    "patch",
    "plan",
    "review",
    "user_review",
    "validate",
]
