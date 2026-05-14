#!/usr/bin/env python3
"""
v84.py — CLI entry point.

Run from your project root. The harness treats the current working
directory as the project by default:

    cd /path/to/my-project
    python3 /path/to/v84-docs/harness/v84.py

Or target a different project with --dir:

    python3 v84-docs/harness/v84.py --dir=/path/to/other-project

On every run the harness:
    1. Resolves the LLM endpoint (env → cached config → prompt if needed)
    2. Detects the project's current stage
    3. Drives the right next action — prompting for any input needed

Override flags:
    --dir <path>           Project root (default: current directory).
    --force <stage>        Re-run a specific stage even if its output
                           already exists. Stages: roles, stack,
                           decompose, plan.
    --call <function>      Direct-dispatch a harness function without
                           state detection. Ex: --call init.decompose.
                           Reads any input from stdin.
    --auto                 Skip all user confirmations. Architect/agent
                           decides. Cycle halts only on hard errors.
    --llm-set URL [KEY]    Set the single-tier LLM endpoint (and
                           optionally its Bearer API key). The key is
                           persisted alongside url/model in profile.yaml
                           (or the user cache if no profile yet).
    --llm-set-multi URL [KEY]  Same for the multi tier.
    --reset-llm            Forget cached LLM URL and re-prompt.
    --status               Print project state and exit. No LLM calls.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

import init  # noqa: F401 — kept for --call dispatch
import ui
import menu
from core import registry, runner, state, util
from llm import resolve_llm, reset_cache


# -----------------------------------------------------------------------------
# Entry
# -----------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # Diagnostic / one-shot paths run on the normal terminal — no
    # alt-screen wrap so their output stays on screen for the user.
    if args.reset_llm:
        reset_cache()
        print("✓ LLM cache cleared", file=sys.stderr)

    project_dir = args.dir.resolve()

    if args.status:
        return _print_status(project_dir)

    if args.test_server is not None:
        # Stand up the local playground and block until Ctrl+C. Imports
        # locally so the rest of v84.py never pays the http.server cost.
        import test_server
        return test_server.main([
            "--port", str(args.test_server),
            "--project", str(project_dir),
        ])

    if args.llm_set is not None or args.llm_set_multi is not None:
        # Pick which tier we're operating on. If both flags are given,
        # operate on each in turn so a single command can configure both.
        rc = 0
        if args.llm_set is not None:
            url, key = _split_llm_args(args.llm_set, "--llm-set")
            if url is False:
                return 2
            rc = _set_llm_tier(project_dir, "single", url, key)
            if rc:
                return rc
        if args.llm_set_multi is not None:
            url, key = _split_llm_args(args.llm_set_multi, "--llm-set-multi")
            if url is False:
                return 2
            rc = _set_llm_tier(project_dir, "multi", url, key)
            if rc:
                return rc
        return 0

    # Interactive stage flow. Status output (llm:, project:, spinner,
    # etc.) stays on the normal terminal; only the interactive pickers
    # (checklist, field_editor, single_select) take over the alt-screen
    # buffer for the duration of their input loop, restoring the prior
    # contents on exit so the user keeps the surrounding context.
    return _run_stages(project_dir, args)


def _split_llm_args(values: list[str], flag: str):
    """Validate the [URL [KEY]] shape from `--llm-set` / `--llm-set-multi`.

    Returns (url_or_None, key_or_None) on success, or (False, None) on
    too-many-args (caller exits with rc=2).
    """
    if len(values) > 2:
        print(
            f"ERROR: {flag} takes at most 2 args (URL [KEY]); got {len(values)}",
            file=sys.stderr,
        )
        return False, None
    url = values[0] if len(values) >= 1 and values[0] else None
    key = values[1] if len(values) >= 2 and values[1] else None
    return url, key


def _set_llm_tier(
    project_dir: Path, tier: str, raw_url: Optional[str], raw_key: Optional[str],
) -> int:
    """Re-probe (and optionally swap URL/key) for one tier, persist, log."""
    try:
        cfg = resolve_llm(
            project_dir=project_dir,
            tier=tier,
            interactive=sys.stdin.isatty(),
            force_url=raw_url,
            force_api_key=raw_key,
            force_rescan=True,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    key_note = " (api_key persisted)" if raw_key else ""
    print(f"✓ llm[{tier}]: {cfg.model} @ {cfg.url}{key_note}", file=sys.stderr)
    return 0


def _run_stages(project_dir: Path, args) -> int:
    """Entry point for the interactive flow. Resolves LLM, then either
    runs the menu (interactive default) or dispatches a one-shot
    based on flags (--call, --force, --auto)."""

    # Resolve LLM endpoint before doing anything else. Reads from
    # profile.yaml first if it exists, then user cache, then prompts.
    # Persists back to whichever sink already owns it.
    try:
        cfg = resolve_llm(
            project_dir=project_dir,
            interactive=sys.stdin.isatty(),
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"llm:      {cfg.model} @ {cfg.url}", file=sys.stderr)

    # Attach the dispatcher so menu actions (and runner) can invoke
    # stages without reaching into v84.py.
    args._dispatch_stage = _dispatch_stage

    # --call dispatch skips state detection and the menu entirely.
    if args.call:
        return _dispatch_call(args.call, project_dir, cfg, args)

    # --force / --auto / --start: skip the menu and go straight to
    # the runner. --force runs the named stage; --auto is the
    # autonomous mode (no UI gate); --start is the explicit "skip
    # the menu and just resume the pipeline" flag.
    if args.force or args.auto or args.start:
        return runner.run_pending_stages(
            project_dir, cfg, args,
            force=args.force,
            dispatch=_dispatch_stage,
        )

    # Interactive default: show the main menu.
    return menu.run_main_menu(project_dir, cfg, args)


# -----------------------------------------------------------------------------
# Generic stage dispatch — driven entirely by the init.STAGES registry.
# Adding a new stage requires no changes here; it's picked up automatically.
# -----------------------------------------------------------------------------

def _dispatch_stage(target: str, project_dir: Path, cfg, args) -> int:
    """Look up `target` in the registry, run it, report what's next."""
    stage = registry.ALL_STAGES_BY_NAME.get(target)
    if stage is None:
        print(
            f"ERROR: unknown stage {target!r}. Known stages: "
            f"{', '.join(sorted(registry.ALL_STAGES_BY_NAME))}",
            file=sys.stderr,
        )
        return 1

    if stage.call is None:
        print(
            f"\nStage {stage.name!r} ({stage.title}) is declared but not\n"
            f"yet implemented. Skipping.",
            file=sys.stderr,
        )
        return 2

    # Ensure the brief is available if this stage wants it.
    brief = ""
    if stage.needs_brief:
        maybe_brief = _require_brief(project_dir)
        if maybe_brief is None:
            return 1
        brief = maybe_brief
    else:
        # Load cached brief opportunistically — some stages use it
        # if present but don't require a prompt.
        brief_file = project_dir / "v84" / "brief.md"
        if brief_file.exists():
            brief = brief_file.read_text(encoding="utf-8").strip()

    try:
        stage.call(project_dir, brief, cfg=cfg)
    except Exception as exc:  # noqa: BLE001 — surface any failure uniformly
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # No post-stage confirmation gate — every stage runs its own
    # UI (checklist / field_editor / detail_list) which IS the
    # confirmation. Cancellation (esc/q) inside that UI raises out
    # of stage.call, surfaced as an error here.
    return 0


# -----------------------------------------------------------------------------
# --call direct dispatch (scripting / debug)
# -----------------------------------------------------------------------------

def _dispatch_call(call: str, project_dir: Path, cfg, args) -> int:
    """Direct-call a harness function by name, bypassing state detection.

    Accepted forms:
        init.<stage>           → run that stage's registered function
        <stage>                → same, without the package prefix
    """
    # Strip "init." prefix if present — the registry uses bare names.
    name = call.removeprefix("init.")
    if name not in init.STAGES_BY_NAME:
        print(
            f"ERROR: unknown --call target {call!r}. "
            f"Known stages: {', '.join(sorted(init.STAGES_BY_NAME))}",
            file=sys.stderr,
        )
        return 1
    return _dispatch_stage(name, project_dir, cfg, args)


# -----------------------------------------------------------------------------
# Input helpers
# -----------------------------------------------------------------------------

def _require_brief(project_dir: Path) -> Optional[str]:
    """Return the brief. Reads cached brief if present, else prompts.

    The brief is cached at <project>/v84/brief.md so resuming a session
    doesn't re-prompt. Users can edit that file to tweak the brief.
    """
    brief_file = project_dir / "v84" / "brief.md"
    if brief_file.exists():
        text = brief_file.read_text(encoding="utf-8").strip()
        if text:
            print(f"brief:    loaded from {brief_file}", file=sys.stderr)
            return text

    if not sys.stdin.isatty():
        # Non-interactive: read whole stdin as the brief
        text = sys.stdin.read().strip()
        if not text:
            print("ERROR: no brief on stdin", file=sys.stderr)
            return None
        _save_brief(project_dir, text)
        return text

    # Interactive: prompt. Two equivalent terminators so users don't
    # get stuck:
    #   1. empty line (press Enter on its own)
    #   2. Ctrl+D (EOF)
    # The `> ` per-line prompt makes it obvious input is being read.
    print("", file=sys.stderr)
    print("Describe what you want to build:", file=sys.stderr)
    print("  • Type your brief (multiple lines OK)", file=sys.stderr)
    print("  • Finish with an empty line, or Ctrl+D", file=sys.stderr)
    print("", file=sys.stderr)

    lines: list[str] = []
    try:
        while True:
            # input("> ") prints "> " and waits for a line.
            # Python's readline handles backspace, arrow keys, etc.
            line = input("> ")
            # Empty line after content → done.
            if line.strip() == "" and lines:
                break
            # Skip leading blank lines entirely (user typed Enter too early).
            if line.strip() == "" and not lines:
                continue
            lines.append(line)
    except EOFError:
        # Ctrl+D — print newline so the shell prompt starts clean
        # after the ^D echo.
        print("", file=sys.stderr)

    text = "\n".join(lines).strip()
    if not text:
        print("ERROR: empty brief", file=sys.stderr)
        return None
    _save_brief(project_dir, text)
    return text


def _save_brief(project_dir: Path, text: str) -> None:
    """Persist the brief so subsequent calls don't re-prompt."""
    v84 = project_dir / "v84"
    v84.mkdir(parents=True, exist_ok=True)
    (v84 / "brief.md").write_text(text.strip() + "\n", encoding="utf-8")


# -----------------------------------------------------------------------------
# --status
# -----------------------------------------------------------------------------

def _print_status(project_dir: Path) -> int:
    """No-LLM diagnostic: print detected stage and exit.

    Also prints the full init registry so the operator can see
    which stages exist, their priorities, and what each produces.
    """
    current = state.detect(project_dir)
    print(f"project:  {project_dir}")
    print(f"summary:  {current.summary}")
    print(f"next:     {current.next_action}")
    if current.running_iteration is not None:
        print(f"running:  iteration {current.running_iteration}")

    # Dump the registry so it's easy to see what's available.
    print("")
    print(f"{'priority':>8}  {'name':<12}  {'done?':<6}  produces")
    v84 = project_dir / "v84"
    for s in init.STAGES:
        produced = "yes" if (v84 / s.produces).exists() else "no"
        impl = "" if s.call else "  (not implemented)"
        print(f"{s.priority:>8}  {s.name:<12}  {produced:<6}  {s.produces}{impl}")
    return 0


# -----------------------------------------------------------------------------
# Argument parser
# -----------------------------------------------------------------------------

def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="v84",
        description=(
            "v84 harness — specification-driven development with AI. "
            "Run from a project root; the harness detects state and drives "
            "the right next action. Use --dir to target a different project."
        ),
    )
    p.add_argument(
        "--dir",
        type=Path,
        default=util.project_root(),
        metavar="PATH",
        help="Project root (the folder that contains or will contain v84/). "
             "Defaults to the folder containing v84-docs/ — computed from "
             "the harness script location, not the shell CWD.",
    )
    p.add_argument(
        "--force",
        metavar="STAGE",
        help="Force a specific stage, overriding state detection. "
             "Stage must be a known name in the init registry.",
    )
    p.add_argument(
        "--call",
        metavar="FUNCTION",
        help="Direct-call a harness function (e.g. init.decompose). "
             "Bypasses state detection.",
    )
    p.add_argument(
        "--auto",
        action="store_true",
        help="Skip confirmation prompts. Architect decides autonomously.",
    )
    p.add_argument(
        "--start",
        action="store_true",
        help="Skip the main menu and go straight to the stage runner. "
             "Same as the menu's 'Start / resume' action.",
    )
    p.add_argument(
        "--reset-llm",
        action="store_true",
        help="Delete the user-level LLM bootstrap cache.",
    )
    p.add_argument(
        "--llm-set",
        nargs="*",
        default=None,
        metavar="URL [KEY]",
        help="Re-probe the single-tier LLM model and persist. First arg "
             "is the URL (omit to re-probe the current one); optional "
             "second arg is the Bearer API key. Writes to profile.yaml "
             "when present, else the user cache.",
    )
    p.add_argument(
        "--llm-set-multi",
        nargs="*",
        default=None,
        metavar="URL [KEY]",
        help="Same as --llm-set but for the 'multi' tier (used when "
             "2+ agents run concurrently). Both flags can be combined "
             "in a single invocation.",
    )
    p.add_argument(
        "--status",
        action="store_true",
        help="Print detected project state and exit. No LLM calls.",
    )
    p.add_argument(
        "--test-server",
        nargs="?",
        const=8000,
        default=None,
        type=int,
        metavar="PORT",
        help="Launch the local stage-test web playground and exit. "
             "Default port 8000; pass a port to override. Open "
             "http://localhost:<PORT>/ in a browser to send custom "
             "user_msgs to any stage and inspect the parse + validate "
             "result.",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
