"""
patch.py — Per-role round-2+ writer (applies corrections).

Replaces draft as the round opener in round 2 and beyond. The cycle
orchestrator calls this once per role with pending corrections. The
writer reads its existing draft + the corrections that landed on its
punch list and emits a patched actions list. After persisting the
new draft, applied corrections move to
`<role>.corrections-applied.yaml` so the next round's reviewers can
verify what was honored.

On success the role's pipeline step advances from `patch` → `review`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core import iter_status, proposals
from core.context import build_user_msgs
from core.util import default_log_dir, load_instruction
from core.versioning import versioned_write
from llm import CallSpec, LLMConfig, call_many, resolve_llm
from ui import spinner

# Reuse draft's parser + renderer — patch emits the same actions /
# rules shape, harness handles ids the same way.
from .draft import _parse, _render_role_output


def patch_role(
    project_dir: Path,
    parent: dict,
    iteration_n: int,
    role: str,
    *,
    cfg: LLMConfig,
) -> None:
    """Patch a single role's draft against pending corrections.

    Persists the patched `<role>.yaml`, archives applied corrections
    to `<role>.corrections-applied.yaml`, clears `<role>.corrections.yaml`,
    and advances the role's pipeline step to `review`. Raises on failure
    so the cycle orchestrator can leave the role at `patch` for a retry.
    """
    iter_dir = project_dir / "v84" / "iterations" / str(iteration_n)
    iter_dir.mkdir(parents=True, exist_ok=True)

    fan_cfg = _fan_out_cfg(project_dir, fallback=cfg)

    system, schema = load_instruction("iteration", "patch")
    round_n = iter_status.read(project_dir, iteration_n).get("round", "?")
    spec = CallSpec(
        system=system,
        user_msgs=build_user_msgs(
            project_dir, parent, iteration_n,
            {
                "plan":                          True,
                "active_roles":                  None,
                "stack":                         [role],
                "layout":                        [role],
                "role_definition":               [role],
                "history":                       [role],
                "actions":                       [role],
                "corrections":                   [role],
                "corrections_pending":           None,
                "corrections_rejected":          None,
                "corrections_applied":           None,
                "corrections_rejected_history":  None,
                "rules":                         [role],
                "rules_pending":                 None,
                "rules_rejected":                None,
                "trailing": (
                    "Apply every correction to your existing draft and "
                    "emit the patched actions list."
                ),
            },
            role=role,
        ),
        response_schema=schema,
        log_name=f"iter-{iteration_n}-r{round_n}-patch-{role}",
    )

    results = call_many(fan_cfg, [spec], log_dir=default_log_dir())
    result = results[0]
    if result.error is not None:
        raise RuntimeError(f"patch failed for {role}: {result.error!r}")

    parsed = _parse(result.response or {})
    out_file = iter_dir / f"{role}.yaml"
    versioned_write(
        out_file, _render_role_output(parsed),
        project_dir=project_dir,
    )
    spinner.log(f"  ✓ {out_file} (patched)")

    # Move applied corrections to the audit file so the next round's
    # reviewers can verify what was honored.
    applied = proposals.read_corrections(project_dir, iteration_n, role)
    existing_archive = _read_corrections_applied(project_dir, iteration_n, role)
    _write_corrections_applied(
        project_dir, iteration_n, role,
        existing_archive + applied,
    )
    proposals.write_corrections(project_dir, iteration_n, role, [])
    spinner.log(
        f"  ✓ {role}.corrections-applied.yaml +{len(applied)} "
        f"(corrections.yaml cleared)"
    )

    # Round-2+ patch may still surface fresh rule proposals.
    rule_prefix = f"v84-{iteration_n}.{role}.rule"
    existing_rules = proposals.read_rules(project_dir, iteration_n, role)
    new_rules = proposals.to_pending_rule_records(
        parsed.get("rules"),
        id_prefix=rule_prefix,
        start_n=proposals.next_index_for_prefix(existing_rules, rule_prefix),
    )
    if new_rules:
        proposals.write_rules(
            project_dir, iteration_n, role,
            proposals.append_pending(existing_rules, new_rules),
        )

    iter_status.set_role_step(
        project_dir, iteration_n, role, iter_status.STEP_REVIEW,
    )


# -----------------------------------------------------------------------------
# corrections-applied audit file
# -----------------------------------------------------------------------------

def _dump(data: Any) -> str:
    return yaml.safe_dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10000,
    )


def _corrections_applied_path(project_dir: Path, n: int, role: str) -> Path:
    return (
        project_dir / "v84" / "iterations" / str(n)
        / f"{role}.corrections-applied.yaml"
    )


def _read_corrections_applied(
    project_dir: Path, n: int, role: str,
) -> list[dict]:
    p = _corrections_applied_path(project_dir, n, role)
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    return [r for r in data if isinstance(r, dict)]


def _write_corrections_applied(
    project_dir: Path, n: int, role: str, records: list[dict],
) -> Path:
    p = _corrections_applied_path(project_dir, n, role)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_dump(records), encoding="utf-8")
    return p


# -----------------------------------------------------------------------------
# Fan-out tier resolution
# -----------------------------------------------------------------------------

def _fan_out_cfg(project_dir: Path, *, fallback: LLMConfig) -> LLMConfig:
    try:
        return resolve_llm(
            project_dir=project_dir, tier="multi",
            interactive=False,
        )
    except RuntimeError:
        return fallback
