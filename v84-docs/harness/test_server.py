#!/usr/bin/env python3
"""
test_server.py — Local HTTP playground for v84 stages.

Run from the harness/ folder, or via v84.py:

    python3 test_server.py            # listen on 0.0.0.0:8000
    python3 test_server.py --port 8765
    python3 v84.py --test-server      # same, via the main entry point

Then open http://localhost:8000/ in a browser. For each stage you can:

  - Paste the same `build_user_msgs` spec dict the harness would pass
    (e.g. `{"plan": true, "stack": ["frontend"], ...}`) and have the
    playground render the actual user messages from your project's
    state.
  - Override the system message (defaults to the .md instruction).
  - Run N parallel instances at once to check sampling consistency.
  - Tag each run; the tag lands in `.v84-logs/<tag>-<group>-<stem>-...`.

This is a raw call+response viewer — schema goes into the prompt
(via `_response_format_block`) but the playground does NOT validate
the parsed JSON against it. You see whatever the model returned.

Single file, stdlib only. No deps. Same call path, same prompt
augmentation as the real harness; just no validate step.

Endpoints:

    GET  /                          HTML playground
    GET  /api/stages                JSON list of every (group, stem)
    GET  /api/stage/<g>/<s>         JSON: schema + system prompt +
                                    augmented prompt + examples +
                                    a default spec template
    GET  /api/project               project_dir, active_roles,
                                    iteration_n, parent task
    POST /api/render/<g>/<s>        body {spec, role}
                                    → rendered user_msgs list
    POST /api/test/<g>/<s>          body {user_msgs|spec, role,
                                          system_override, max_tokens,
                                          retries, concurrency, tag}
                                    → JSON {runs: [{ok, value, attempts,
                                                     elapsed_s}]}
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback

import yaml
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from core import coreyaml
from core.context import active_roles, build_user_msgs
from core.util import default_log_dir, load_instruction, v84_docs_root
from llm.client import (
    LLMConfig,
    _build_body,
    _post_with_retry,
    _response_format_block,
    _strip_code_fence,
    _strip_thinking,
    _validate_against_schema,
)
from llm.config import resolve_llm
from ui.multi_spinner import MultiSpinner


# ---------------------------------------------------------------------------
# Per-stage spec template — what a typical build_user_msgs spec looks like
# for that stage. Pulled from the real call sites so the playground starts
# users with a realistic shape they can edit.
# ---------------------------------------------------------------------------

SPEC_TEMPLATES: dict[tuple[str, str], dict] = {
    ("iteration", "draft"): {
        "plan": True,
        "active_roles": None,
        "stack": ["{role}"],
        "layout": ["{role}"],
        "role_definition": ["{role}"],
        "history": ["{role}"],
        "rules": ["{role}"],
        "trailing": "Draft the concrete actions for this iteration.",
    },
    ("iteration", "patch"): {
        "plan": True,
        "stack": ["{role}"],
        "layout": ["{role}"],
        "role_definition": ["{role}"],
        "history": ["{role}"],
        "actions": ["{role}"],
        "corrections": ["{role}"],
        "rules": ["{role}"],
        "trailing": "Apply every correction to your existing draft.",
    },
    ("iteration", "review"): {
        "plan": True,
        "stack": ["{role}"],
        "layout": ["{role}"],
        "role_definition": ["{role}"],
        "history": ["{role}"],
        "actions": ["{role}"],
        "corrections_applied": ["{role}"],
        "corrections_rejected_history": ["{role}"],
        "rules": ["{role}"],
        "trailing": "Review the role's draft through your lens.",
    },
    ("iteration", "review_validate"): {
        "plan": True,
        "stack": ["{role}"],
        "layout": ["{role}"],
        "role_definition": ["{role}"],
        "history": ["{role}"],
        "actions": ["{role}"],
        "corrections_pending": ["{role}"],
        "corrections_applied": ["{role}"],
        "corrections_rejected_history": ["{role}"],
        "rules": ["{role}"],
        "rules_pending": ["{role}"],
        "rules_rejected": ["{role}"],
        "trailing": "Vote accept/reject on every pending correction and pending rule proposal.",
    },
    ("iteration", "lead"): {
        "plan": True,
        "stack": ["{role}"],
        "layout": ["{role}"],
        "role_definition": ["{role}"],
        "history": ["{role}"],
        "actions": ["{role}"],
        "corrections_pending": ["{role}"],
        "corrections_applied": ["{role}"],
        "corrections_rejected_history": ["{role}"],
        "rules": ["{role}"],
        "rules_pending": ["{role}"],
        "rules_rejected": ["{role}"],
        "trailing": "Optionally raise corrections or rules the reviewers missed. Most lead calls produce nothing.",
    },
    ("iteration", "architect"): {
        "plan": True,
        "active_roles": True,
        "stack": "all",
        "layout": ["global"],
        "role_definition": "all",
        "actions": "all",
        "corrections": "all",
        "corrections_rejected": "all",
        "rules": ["global"],
        "rules_rejected": ["global"],
        "trailing": "Synthesise across roles.",
    },
    ("iteration", "architect_validate"): {
        "stack": ["{role}"],
        "role_definition": ["{role}"],
        "corrections_pending": ["{role}"],
        "rules": ["{role}"],
        "rules_pending": ["global"],
        "trailing": "Vote accept/reject on every pending item from your role's perspective.",
    },
}


def spec_template_for(group: str, stem: str, role: Optional[str]) -> dict:
    """Realise a stage's spec template, swapping in the chosen role."""
    template = SPEC_TEMPLATES.get((group, stem))
    if template is None:
        return {}
    rendered: dict = {}
    role_value = role or "<role>"
    for key, scope in template.items():
        if isinstance(scope, list):
            rendered[key] = [
                role_value if item == "{role}" else item for item in scope
            ]
        else:
            rendered[key] = scope
    return rendered


# ---------------------------------------------------------------------------
# Stage discovery
# ---------------------------------------------------------------------------

def list_stages() -> list[tuple[str, str]]:
    """Every (group, stem) where the .md and .schema.json both exist."""
    out: list[tuple[str, str]] = []
    root = v84_docs_root() / "instructions"
    if not root.exists():
        return out
    for group_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for schema_file in sorted(group_dir.glob("*.schema.json")):
            stem = schema_file.name[: -len(".schema.json")]
            md_file = group_dir / f"{stem}.md"
            if md_file.exists():
                out.append((group_dir.name, stem))
    return out


def list_instruction_files() -> list[dict]:
    """Every .md and .schema.json under instructions/, with relative
    path + size. Sorted: group → stem → md/schema."""
    out: list[dict] = []
    root = v84_docs_root() / "instructions"
    if not root.exists():
        return out
    for group_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        files = sorted(
            list(group_dir.glob("*.md")) + list(group_dir.glob("*.schema.json"))
        )
        for f in files:
            rel = f.relative_to(v84_docs_root())
            out.append({
                "group": group_dir.name,
                "name": f.name,
                "relpath": str(rel),
                "kind": "schema" if f.name.endswith(".schema.json") else "md",
                "size": f.stat().st_size,
            })
    return out


def read_instruction_file(group: str, name: str) -> str:
    """Read one instruction file by name (must live under
    instructions/<group>/). Path-traversal-safe."""
    root = (v84_docs_root() / "instructions" / group).resolve()
    target = (root / name).resolve()
    if not str(target).startswith(str(root) + "/") and target != root:
        raise PermissionError("path escapes instructions root")
    if not target.exists():
        raise FileNotFoundError(str(target))
    return target.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Project context — pulled lazily so the playground works even when no
# core.yaml exists yet (build_user_msgs paths just fail with a clear error).
# ---------------------------------------------------------------------------

class ProjectCtx:
    project_dir: Path

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir

    def info(self) -> dict:
        info: dict[str, Any] = {
            "project_dir": str(self.project_dir),
            "active_roles": [],
            "iteration_n": None,
            "parent_id": None,
            "parent_task": None,
            "core_yaml_exists": False,
        }
        profile_path = self.project_dir / "v84" / "profile.yaml"
        info["active_roles"] = active_roles(profile_path) if profile_path.exists() else []

        core_path = self.project_dir / "v84" / "core.yaml"
        info["core_yaml_exists"] = core_path.exists()
        if not core_path.exists():
            return info

        data = coreyaml.read(self.project_dir)
        parent_id = data.get("current_iteration")
        if not parent_id:
            return info
        parent = coreyaml.find_by_id(data, parent_id)
        if parent is None:
            return info
        info["iteration_n"] = _iteration_number(parent_id)
        info["parent_id"] = parent_id
        info["parent_task"] = parent.get("task", "")
        return info

    def render_user_msgs(self, spec: dict, role: Optional[str]) -> list[str]:
        """Run build_user_msgs with this project's state."""
        data = coreyaml.read(self.project_dir)
        parent_id = data.get("current_iteration")
        if not parent_id:
            raise RuntimeError(
                "no current_iteration in core.yaml — set it or run plan first"
            )
        parent = coreyaml.find_by_id(data, parent_id)
        if parent is None:
            raise RuntimeError(f"current_iteration {parent_id!r} not found")
        iteration_n = _iteration_number(parent_id)
        return build_user_msgs(
            self.project_dir, parent, iteration_n, spec, role=role,
        )


def _iteration_number(task_id: str) -> int:
    return int(task_id.split(".")[0].split("-")[1])


# ---------------------------------------------------------------------------
# Test-call wrapper — same code path as call_json but exposes per-attempt
# raw content + parse + validate so the UI can show what the model did.
# ---------------------------------------------------------------------------

def run_one(
    cfg: LLMConfig,
    schema: dict,
    augmented_system: str,
    user_msgs: list[str],
    *,
    max_tokens: int,
    retries: int,
    log_name: Optional[str],
    on_stream: Optional[Any] = None,
) -> dict:
    """Run a single instance — schema-augmented system prompt + user msgs.

    Returns: {ok, value, attempts: [{raw, parse_error, schema_errors,
    parsed, log_name, elapsed_s}], elapsed_s}

    `on_stream` is the per-call streaming hook; pass MultiSpinner's
    closure here so live tail snapshots paint on a fixed track instead
    of scrolling stderr.
    """
    base_messages: list[dict[str, Any]] = [
        {"role": "system", "content": augmented_system}
    ]
    for msg in user_msgs:
        base_messages.append({"role": "user", "content": msg})

    attempts: list[dict] = []
    started = time.monotonic()
    for attempt in range(1, retries + 1):
        attempt_log = f"{log_name}-a{attempt}" if log_name else None
        attempt_started = time.monotonic()
        body = _build_body(
            cfg, base_messages,
            response_schema=schema,
            max_tokens=max_tokens,
        )
        try:
            response = _post_with_retry(
                cfg, body,
                attempt_label=attempt_log or "playground",
                log_name=attempt_log,
                log_dir=default_log_dir() if attempt_log else None,
                on_stream=on_stream,
            )
        except RuntimeError as exc:
            attempts.append({
                "raw": "",
                "parse_error": f"transport: {exc}",
                "schema_errors": [],
                "elapsed_s": time.monotonic() - attempt_started,
                "log_name": attempt_log,
            })
            break

        try:
            raw = response["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError):
            attempts.append({
                "raw": "",
                "parse_error": "missing choices/message",
                "schema_errors": [],
                "elapsed_s": time.monotonic() - attempt_started,
                "log_name": attempt_log,
            })
            continue

        text, fence_tag = _strip_code_fence(_strip_thinking(raw))
        try:
            if fence_tag == "yaml":
                value = yaml.safe_load(text)
            else:
                value = json.loads(text)
        except (json.JSONDecodeError, yaml.YAMLError) as exc:
            attempts.append({
                "raw": raw,
                "parse_error": str(exc),
                "schema_errors": [],
                "elapsed_s": time.monotonic() - attempt_started,
                "log_name": attempt_log,
            })
            continue

        errors = _validate_against_schema(value, schema)
        attempts.append({
            "raw": raw,
            "parse_error": None,
            "schema_errors": errors,
            "parsed": value,
            "elapsed_s": time.monotonic() - attempt_started,
            "log_name": attempt_log,
        })
        if not errors:
            return {
                "ok": True,
                "value": value,
                "attempts": attempts,
                "elapsed_s": time.monotonic() - started,
            }

    return {
        "ok": False,
        "value": None,
        "attempts": attempts,
        "elapsed_s": time.monotonic() - started,
    }


def run_one_raw(
    cfg: LLMConfig,
    system: str,
    user_msgs: list[str],
    *,
    max_tokens: int,
    log_name: Optional[str],
    on_stream: Optional[Any] = None,
) -> dict:
    """Single freeform call — no schema, no augmentation, no validation.

    Returns: {raw, parse_error, parsed?, elapsed_s, log_name}
    Note: a single attempt; "retries" at the freeform level mean
    independent re-runs (handled by the caller fanning out copies).

    `on_stream` is the per-call streaming hook; pass MultiSpinner's
    closure to route live tail snapshots onto a fixed track.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system}
    ]
    for msg in user_msgs:
        messages.append({"role": "user", "content": msg})

    started = time.monotonic()
    body = _build_body(cfg, messages, max_tokens=max_tokens)
    try:
        response = _post_with_retry(
            cfg, body,
            attempt_label=log_name or "playground-raw",
            log_name=log_name,
            log_dir=default_log_dir() if log_name else None,
            on_stream=on_stream,
        )
    except RuntimeError as exc:
        return {
            "raw": "",
            "parse_error": f"transport: {exc}",
            "elapsed_s": time.monotonic() - started,
            "log_name": log_name,
        }
    try:
        raw = response["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError, TypeError):
        return {
            "raw": "",
            "parse_error": "missing choices/message",
            "elapsed_s": time.monotonic() - started,
            "log_name": log_name,
        }

    out: dict[str, Any] = {
        "raw": raw,
        "parse_error": None,
        "elapsed_s": time.monotonic() - started,
        "log_name": log_name,
    }
    text, fence_tag = _strip_code_fence(_strip_thinking(raw))
    try:
        if fence_tag == "yaml":
            out["parsed"] = yaml.safe_load(text)
        else:
            out["parsed"] = json.loads(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        out["parse_error"] = str(exc)
    return out


def run_test(
    cfg: LLMConfig,
    project: ProjectCtx,
    group: str,
    stem: str,
    *,
    user_msgs: Optional[list[str]],
    spec: Optional[dict],
    role: Optional[str],
    system_override: Optional[str],
    max_tokens: int,
    retries: int,
    concurrency: int,
    tag: Optional[str],
) -> dict:
    """Set up the call and fan out N copies if concurrency > 1."""
    base_system, schema = load_instruction(group, stem)
    system = system_override if system_override else base_system
    augmented_system = (
        f"{system}\n\n## Response format\n\n{_response_format_block(schema)}"
    )

    # Decide how to build user_msgs.
    if user_msgs is None and spec is not None:
        user_msgs = project.render_user_msgs(spec, role)
    elif user_msgs is None:
        user_msgs = []

    # Build per-instance log_name. The tag is the user's label (lands in
    # .v84-logs/ filenames so the run is searchable).
    safe_tag = (tag or "playground").strip().replace("/", "_") or "playground"
    base_log = f"{safe_tag}-{group}-{stem}"

    labels = [f"{base_log}-i{i + 1}" for i in range(concurrency)]
    runs: list[Optional[dict]] = [None] * concurrency
    with MultiSpinner(labels) as ms:
        def _do(i: int) -> tuple[int, dict]:
            ms.started(i)
            def hook(*, phase, content, reasoning, tail):
                ms.stream_update(
                    i, phase=phase, content=content,
                    reasoning=reasoning, tail=tail,
                )
            try:
                r = run_one(
                    cfg, schema, augmented_system, user_msgs,
                    max_tokens=max_tokens, retries=retries,
                    log_name=labels[i],
                    on_stream=hook,
                )
                ms.done(i, None)
                return i, r
            except BaseException as exc:
                ms.done(i, exc)
                raise

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(_do, i) for i in range(concurrency)]
            for f in futures:
                i, r = f.result()
                runs[i] = r

    return {
        "augmented_system": augmented_system,
        "user_msgs": user_msgs,
        "runs": runs,
    }


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):

    cfg: Optional[LLMConfig] = None
    project: Optional[ProjectCtx] = None

    def log_message(self, format: str, *args) -> None:
        sys.stderr.write(f"{self.address_string()} - {format % args}\n")

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, status: int, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json_body(self) -> Optional[dict]:
        length = int(self.headers.get("Content-Length") or "0")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError as exc:
            self._json(400, {"error": f"invalid JSON body: {exc}"})
            return None

    # ---- GET ---------------------------------------------------------

    def do_GET(self) -> None:
        url = urlparse(self.path)
        path = url.path.rstrip("/") or "/"

        if path == "/":
            self._html(200, render_index())
            return
        if path == "/api/project":
            self._json(200, Handler.project.info())
            return
        if path == "/api/stages":
            self._json(200, [
                {"group": g, "stem": s} for g, s in list_stages()
            ])
            return
        if path == "/api/instructions":
            self._json(200, list_instruction_files())
            return
        if path.startswith("/api/instruction/"):
            parts = path[len("/api/instruction/"):].split("/")
            if len(parts) != 2:
                self._json(400, {"error": "expected /api/instruction/<group>/<name>"})
                return
            group, name = parts
            try:
                content = read_instruction_file(group, name)
            except (FileNotFoundError, PermissionError) as exc:
                self._json(404, {"error": str(exc)})
                return
            self._json(200, {
                "group": group,
                "name": name,
                "relpath": f"instructions/{group}/{name}",
                "content": content,
            })
            return
        if path.startswith("/api/stage/"):
            parts = path[len("/api/stage/"):].split("/")
            if len(parts) != 2:
                self._json(400, {"error": "expected /api/stage/<group>/<stem>"})
                return
            group, stem = parts
            try:
                system, schema = load_instruction(group, stem)
            except FileNotFoundError as exc:
                self._json(404, {"error": str(exc)})
                return
            roles = Handler.project.info()["active_roles"]
            default_role = roles[0] if roles else None
            self._json(200, {
                "group": group,
                "stem": stem,
                "system": system,
                "schema": schema,
                "augmented_system": (
                    f"{system}\n\n## Response format\n\n"
                    f"{_response_format_block(schema)}"
                ),
                "examples": schema.get("examples") or [],
                "spec_template": spec_template_for(group, stem, default_role),
                "default_role": default_role,
            })
            return
        self._json(404, {"error": f"no route for GET {path}"})

    # ---- POST --------------------------------------------------------

    def do_POST(self) -> None:
        url = urlparse(self.path)
        path = url.path.rstrip("/")

        if path == "/api/render":
            self._handle_render_freeform()
            return
        if path == "/api/test_raw":
            self._handle_test_raw()
            return
        if path.startswith("/api/render/"):
            self._handle_render(path)
            return
        if path.startswith("/api/test/"):
            self._handle_test(path)
            return
        self._json(404, {"error": f"no route for POST {path}"})

    def _handle_render_freeform(self) -> None:
        """Stage-agnostic build_user_msgs render. Body: {spec, role}."""
        body = self._read_json_body()
        if body is None:
            return
        spec = body.get("spec")
        role = body.get("role")
        if not isinstance(spec, dict):
            self._json(400, {"error": "spec must be a JSON object"})
            return
        try:
            msgs = Handler.project.render_user_msgs(spec, role)
        except Exception as exc:  # noqa: BLE001
            self._json(400, {
                "error": f"{type(exc).__name__}: {exc}",
                "trace": traceback.format_exc(),
            })
            return
        self._json(200, {"user_msgs": msgs})

    def _handle_test_raw(self) -> None:
        """Freeform call. Body: {system, user_msgs, max_tokens, retries,
        concurrency, tag}. No augmentation, no validation."""
        body = self._read_json_body()
        if body is None:
            return
        system = body.get("system") or ""
        user_msgs = body.get("user_msgs") or []
        if not isinstance(user_msgs, list) or not all(
            isinstance(m, str) for m in user_msgs
        ):
            self._json(400, {"error": "user_msgs must be a list of strings"})
            return
        max_tokens = int(body.get("max_tokens") or 16_000)
        # In freeform mode, "retries" become independent re-runs (no
        # validator to feed back). Tag still drives log naming.
        retries = max(1, int(body.get("retries") or 1))
        concurrency = max(1, int(body.get("concurrency") or 1))
        tag = (body.get("tag") or "blank").strip().replace("/", "_") or "blank"

        instances = concurrency * retries
        base_log = f"{tag}-blank"
        print(
            f"\n[blank] starting {instances} run(s) "
            f"(concurrency={concurrency}, max_tokens={max_tokens}, "
            f"system={len(system):,} chars, "
            f"user_msgs={len(user_msgs)} totaling "
            f"{sum(len(m) for m in user_msgs):,} chars)",
            file=sys.stderr, flush=True,
        )
        wall_started = time.monotonic()
        try:
            labels = [f"{base_log}-i{i + 1}" for i in range(instances)]
            runs: list[Optional[dict]] = [None] * instances
            with MultiSpinner(labels) as ms:
                def _do(i: int) -> tuple[int, dict]:
                    ms.started(i)
                    def hook(*, phase, content, reasoning, tail):
                        ms.stream_update(
                            i, phase=phase, content=content,
                            reasoning=reasoning, tail=tail,
                        )
                    try:
                        r = run_one_raw(
                            Handler.cfg, system, user_msgs,
                            max_tokens=max_tokens,
                            log_name=labels[i],
                            on_stream=hook,
                        )
                        ms.done(i, None)
                        return i, r
                    except BaseException as exc:
                        ms.done(i, exc)
                        raise

                with ThreadPoolExecutor(max_workers=concurrency) as pool:
                    futures = [pool.submit(_do, i) for i in range(instances)]
                    for f in futures:
                        i, r = f.result()
                        runs[i] = r
            wall = time.monotonic() - wall_started
            print(
                f"[blank] all {instances} run(s) done in {wall:.1f}s wall clock",
                file=sys.stderr, flush=True,
            )
            self._json(200, {
                "system": system,
                "user_msgs": user_msgs,
                "runs": runs,
            })
        except Exception as exc:  # noqa: BLE001
            self._json(500, {
                "error": f"{type(exc).__name__}: {exc}",
                "trace": traceback.format_exc(),
            })

    def _handle_render(self, path: str) -> None:
        parts = path[len("/api/render/"):].split("/")
        if len(parts) != 2:
            self._json(400, {"error": "expected /api/render/<group>/<stem>"})
            return
        group, stem = parts
        body = self._read_json_body()
        if body is None:
            return
        spec = body.get("spec")
        role = body.get("role")
        if not isinstance(spec, dict):
            self._json(400, {"error": "spec must be a JSON object"})
            return
        try:
            msgs = Handler.project.render_user_msgs(spec, role)
        except Exception as exc:  # noqa: BLE001
            self._json(400, {
                "error": f"{type(exc).__name__}: {exc}",
                "trace": traceback.format_exc(),
            })
            return
        self._json(200, {"user_msgs": msgs})

    def _handle_test(self, path: str) -> None:
        parts = path[len("/api/test/"):].split("/")
        if len(parts) != 2:
            self._json(400, {"error": "expected /api/test/<group>/<stem>"})
            return
        group, stem = parts
        body = self._read_json_body()
        if body is None:
            return

        spec = body.get("spec")
        user_msgs = body.get("user_msgs")
        if user_msgs is not None:
            if not isinstance(user_msgs, list) or not all(
                isinstance(m, str) for m in user_msgs
            ):
                self._json(400, {"error": "user_msgs must be a list of strings"})
                return
        elif spec is not None and not isinstance(spec, dict):
            self._json(400, {"error": "spec must be a JSON object"})
            return

        role = body.get("role")
        system_override = body.get("system_override") or None
        max_tokens = int(body.get("max_tokens") or 16_000)
        retries = max(1, int(body.get("retries") or 3))
        concurrency = max(1, int(body.get("concurrency") or 1))
        tag = body.get("tag")

        try:
            result = run_test(
                Handler.cfg, Handler.project, group, stem,
                user_msgs=user_msgs, spec=spec, role=role,
                system_override=system_override,
                max_tokens=max_tokens, retries=retries,
                concurrency=concurrency, tag=tag,
            )
            self._json(200, result)
        except FileNotFoundError as exc:
            self._json(404, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._json(500, {
                "error": f"{type(exc).__name__}: {exc}",
                "trace": traceback.format_exc(),
            })


# ---------------------------------------------------------------------------
# Single-file HTML UI
# ---------------------------------------------------------------------------

def render_index() -> str:
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>v84 stage playground</title>
<style>
  body { font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI",
         Roboto, sans-serif; margin: 0; padding: 0;
         background: #0e1116; color: #d8dde3; }
  header { padding: 10px 18px; background: #161b22;
           border-bottom: 1px solid #30363d;
           display: flex; align-items: center; gap: 16px; }
  header h1 { margin: 0; font-size: 16px; font-weight: 600; }
  header .ctx { color: #7d8590; font-size: 12px; flex: 1; }
  header .modes { display: flex; gap: 4px; }
  header .modes button { background: #30363d; padding: 5px 12px; font-size: 12px; }
  header .modes button.active { background: #1f6feb; }
  main { display: grid; grid-template-columns: 260px 1fr;
         min-height: calc(100vh - 41px); }
  nav { background: #0e1116; border-right: 1px solid #30363d; padding: 10px;
        max-height: calc(100vh - 41px); overflow: auto; }
  nav h2 { font-size: 11px; text-transform: uppercase; letter-spacing: .08em;
           color: #7d8590; margin: 12px 0 6px; }
  nav a { display: block; padding: 4px 6px; color: #d8dde3; text-decoration: none;
          border-radius: 4px; font-size: 13px; }
  nav a:hover { background: #21262d; }
  nav a.active { background: #1f6feb; color: #fff; }
  section { padding: 16px 22px; max-width: 1180px; }
  section h2 { font-size: 13px; margin: 22px 0 6px; color: #7d8590;
               text-transform: uppercase; letter-spacing: .06em;
               font-weight: 600; }
  section h2 .sub { color: #4a5258; font-weight: 400; text-transform: none;
                    letter-spacing: 0; font-size: 12px; margin-left: 6px; }
  textarea, pre, input[type=text], select {
    background: #161b22; color: #d8dde3; border: 1px solid #30363d;
    border-radius: 6px; padding: 7px 9px;
    font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    box-sizing: border-box;
  }
  textarea, pre { width: 100%; }
  textarea { min-height: 100px; resize: vertical; }
  pre { white-space: pre-wrap; max-height: 460px; overflow: auto; }
  button { background: #238636; color: #fff; border: 0; padding: 7px 14px;
           border-radius: 6px; cursor: pointer; font-size: 13px;
           font-weight: 600; }
  button.secondary { background: #30363d; }
  button:hover { filter: brightness(1.15); }
  button:disabled { background: #30363d; cursor: progress; opacity: .7; }
  .row { display: flex; gap: 10px; align-items: center; margin: 8px 0;
         flex-wrap: wrap; }
  .row label { font-size: 12px; color: #7d8590; min-width: 80px; }
  .row input[type=number] { width: 90px; background: #161b22; color: #d8dde3;
                            border: 1px solid #30363d; padding: 5px 8px;
                            border-radius: 4px; font: inherit; }
  .row input[type=text] { flex: 1; min-width: 200px; }
  .row select { min-width: 140px; }
  .msg { background: #161b22; padding: 10px 12px; border-radius: 6px;
         border: 1px solid #30363d; margin: 8px 0; }
  .msg .head { font-size: 11px; color: #7d8590; margin-bottom: 6px;
               text-transform: uppercase; letter-spacing: .06em;
               display: flex; gap: 10px; align-items: center; }
  .ok  { border-left: 3px solid #3fb950; }
  .bad { border-left: 3px solid #f85149; }
  .meh { border-left: 3px solid #d29922; }
  details summary { cursor: pointer; padding: 6px 0; color: #7d8590;
                    font-size: 12px; user-select: none; }
  details[open] summary { color: #d8dde3; }
  .empty { color: #7d8590; font-style: italic; padding: 60px 20px;
           text-align: center; }
  .ex-title { font-weight: 600; margin: 12px 0 6px; font-size: 13px; }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 10px;
          font-size: 11px; background: #21262d; color: #d8dde3; }
  .runs { display: grid; gap: 12px; grid-template-columns: 1fr; }
  @media (min-width: 1100px) {
    .runs.multi { grid-template-columns: 1fr 1fr; }
  }
</style>
</head>
<body>
<header>
  <h1>v84 playground</h1>
  <span class="ctx" id="ctx">loading…</span>
  <div class="modes">
    <button id="mode-preview" class="active">Preview Request</button>
    <button id="mode-blank">Blank</button>
  </div>
</header>
<main id="main-preview">
  <nav id="nav"></nav>
  <section id="panel">
    <div class="empty">Pick a stage on the left.</div>
  </section>
</main>
<main id="main-blank" style="display:none; grid-template-columns: 1fr;">
  <section id="blank-panel"></section>
</main>
<script>
const panel = document.getElementById('panel');
const nav = document.getElementById('nav');
const ctxEl = document.getElementById('ctx');
let project = {};
let active = null;
let stage = null;
let userMsgsCache = null;

async function loadProject() {
  const r = await fetch('/api/project');
  project = await r.json();
  ctxEl.textContent = project.iteration_n
    ? `${project.project_dir} • iter ${project.iteration_n} (${project.parent_id}) • roles: ${project.active_roles.join(', ')}`
    : `${project.project_dir} • no iteration set`;
}

async function loadStages() {
  const r = await fetch('/api/stages');
  const stages = await r.json();
  const groups = {};
  for (const s of stages) (groups[s.group] = groups[s.group] || []).push(s);
  nav.innerHTML = '';
  for (const g of Object.keys(groups)) {
    const h = document.createElement('h2'); h.textContent = g; nav.appendChild(h);
    for (const s of groups[g]) {
      const a = document.createElement('a');
      a.href = '#'; a.textContent = s.stem;
      a.addEventListener('click', e => { e.preventDefault(); pick(g, s.stem, a); });
      nav.appendChild(a);
    }
  }
}

function pick(group, stem, el) {
  if (active) active.classList.remove('active');
  active = el; el.classList.add('active');
  loadStage(group, stem);
}

async function loadStage(group, stem) {
  panel.innerHTML = '<div class="empty">Loading…</div>';
  const r = await fetch(`/api/stage/${group}/${stem}`);
  stage = await r.json();
  userMsgsCache = null;
  renderStage();
}

function renderStage() {
  panel.innerHTML = '';

  const head = document.createElement('div');
  head.innerHTML = `<h2 style="margin-top:0">${stage.group} / ${stage.stem}
                      <span class="sub">${stage.augmented_system.length.toLocaleString()} chars in system prompt</span>
                    </h2>`;
  panel.appendChild(head);

  // ---- Schema examples ------------------------------------------------
  if (stage.examples && stage.examples.length) {
    const wrap = document.createElement('div');
    wrap.innerHTML = '<h2>Schema examples</h2>';
    for (const ex of stage.examples) {
      const t = document.createElement('div');
      t.className = 'ex-title';
      t.textContent = ex.title || 'Example';
      wrap.appendChild(t);
      const pre = document.createElement('pre');
      pre.textContent = JSON.stringify(ex.example, null, 2);
      wrap.appendChild(pre);
    }
    panel.appendChild(wrap);
  }

  // ---- Spec mode (build_user_msgs) ------------------------------------
  const specWrap = document.createElement('div');
  specWrap.innerHTML = '<h2>build_user_msgs spec <span class="sub">paste a dict like the harness uses; click "Render preview" to turn it into messages</span></h2>';
  panel.appendChild(specWrap);

  const roleRow = document.createElement('div');
  roleRow.className = 'row';
  roleRow.innerHTML = `<label>role</label>`;
  const roleSel = document.createElement('select');
  roleSel.id = 'role';
  const noneOpt = document.createElement('option');
  noneOpt.value = ''; noneOpt.textContent = '(none — cross-role stage)';
  roleSel.appendChild(noneOpt);
  for (const r of project.active_roles || []) {
    const o = document.createElement('option');
    o.value = r; o.textContent = r;
    if (r === stage.default_role) o.selected = true;
    roleSel.appendChild(o);
  }
  roleRow.appendChild(roleSel);
  panel.appendChild(roleRow);

  const specTa = document.createElement('textarea');
  specTa.id = 'spec';
  specTa.style.minHeight = '180px';
  specTa.value = JSON.stringify(stage.spec_template, null, 2);
  panel.appendChild(specTa);

  const specBtns = document.createElement('div');
  specBtns.className = 'row';
  const renderBtn = document.createElement('button');
  renderBtn.textContent = 'Render preview';
  renderBtn.className = 'secondary';
  specBtns.appendChild(renderBtn);
  const renderStatus = document.createElement('span');
  renderStatus.style.color = '#7d8590'; renderStatus.style.fontSize = '12px';
  specBtns.appendChild(renderStatus);
  panel.appendChild(specBtns);

  const previewWrap = document.createElement('div');
  panel.appendChild(previewWrap);

  renderBtn.addEventListener('click', async () => {
    let parsed;
    try {
      parsed = JSON.parse(specTa.value);
    } catch (e) { renderStatus.textContent = `spec parse: ${e}`; return; }
    renderStatus.textContent = 'rendering…';
    try {
      const r = await fetch(`/api/render/${stage.group}/${stage.stem}`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({spec: parsed, role: roleSel.value || null}),
      });
      const data = await r.json();
      if (data.error) {
        renderStatus.textContent = data.error;
        userMsgsCache = null;
      } else {
        userMsgsCache = data.user_msgs;
        renderStatus.textContent = `rendered ${data.user_msgs.length} message(s)`;
        renderPreview(previewWrap, data.user_msgs);
      }
    } catch (e) { renderStatus.textContent = String(e); }
  });

  // ---- System override -----------------------------------------------
  const sysWrap = document.createElement('details');
  sysWrap.innerHTML = '<summary>System message override (advanced — defaults to .md instruction)</summary>';
  const sysTa = document.createElement('textarea');
  sysTa.id = 'sys-override';
  sysTa.placeholder = '(empty = use .md as-is)';
  sysTa.style.minHeight = '160px';
  sysTa.value = '';
  sysWrap.appendChild(sysTa);
  const fillBtn = document.createElement('button');
  fillBtn.textContent = 'Load default into editor';
  fillBtn.className = 'secondary';
  fillBtn.style.marginTop = '6px';
  fillBtn.addEventListener('click', () => { sysTa.value = stage.system; });
  sysWrap.appendChild(fillBtn);
  panel.appendChild(sysWrap);

  // ---- Augmented prompt (read-only preview) --------------------------
  const augWrap = document.createElement('details');
  augWrap.innerHTML = `<summary>Augmented system prompt (auto-built — what the model actually sees)</summary>`;
  const augPre = document.createElement('pre');
  augPre.textContent = stage.augmented_system;
  augWrap.appendChild(augPre);
  panel.appendChild(augWrap);

  // ---- Knobs ---------------------------------------------------------
  const knobs = document.createElement('div');
  knobs.innerHTML = `
    <h2>Run</h2>
    <div class="row">
      <label>tag</label>
      <input id="tag" type="text" value="playground" placeholder="lands in .v84-logs/<tag>-...">
    </div>
    <div class="row">
      <label>concurrency</label>
      <input id="concurrency" type="number" value="1" min="1" max="20">
      <label style="min-width:auto;margin-left:14px">retries</label>
      <input id="retries" type="number" value="3" min="1" max="10">
      <label style="min-width:auto;margin-left:14px">max_tokens</label>
      <input id="max-tokens" type="number" value="16000" min="100" max="200000">
    </div>
  `;
  panel.appendChild(knobs);

  const sendRow = document.createElement('div');
  sendRow.className = 'row';
  const send = document.createElement('button');
  send.textContent = 'Send to LLM';
  sendRow.appendChild(send);
  const status = document.createElement('span');
  status.style.color = '#7d8590'; status.style.fontSize = '12px';
  sendRow.appendChild(status);
  panel.appendChild(sendRow);

  const out = document.createElement('div');
  panel.appendChild(out);

  send.addEventListener('click', async () => {
    let body;
    try {
      const specParsed = JSON.parse(specTa.value);
      body = {
        spec: specParsed,
        role: roleSel.value || null,
        system_override: sysTa.value || null,
        max_tokens: Number(document.getElementById('max-tokens').value),
        retries: Number(document.getElementById('retries').value),
        concurrency: Number(document.getElementById('concurrency').value),
        tag: document.getElementById('tag').value || 'playground',
      };
    } catch (e) {
      status.textContent = `spec parse: ${e}`; return;
    }

    send.disabled = true;
    status.textContent = 'calling…';
    out.innerHTML = '';
    const t0 = Date.now();
    try {
      const r = await fetch(`/api/test/${stage.group}/${stage.stem}`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body),
      });
      const data = await r.json();
      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      status.textContent = `done in ${elapsed}s wall clock`;
      renderResults(out, data, body.concurrency);
    } catch (e) {
      status.textContent = 'error';
      out.innerHTML = `<pre class="msg bad">${escapeHtml(String(e))}</pre>`;
    } finally {
      send.disabled = false;
    }
  });
}

function renderPreview(parent, msgs) {
  parent.innerHTML = '<h2>Rendered user messages <span class="sub">' + msgs.length + ' message(s)</span></h2>';
  msgs.forEach((m, i) => {
    const det = document.createElement('details');
    const head = document.createElement('summary');
    const first = m.split('\\n')[0].slice(0, 100);
    head.textContent = `[${i + 1}] (${m.length} chars) ${first}${first.length >= 100 ? '…' : ''}`;
    det.appendChild(head);
    const pre = document.createElement('pre');
    pre.textContent = m;
    det.appendChild(pre);
    parent.appendChild(det);
  });
}

function renderResults(out, data, concurrency) {
  if (data.error) {
    const m = document.createElement('div');
    m.className = 'msg bad';
    m.innerHTML = `<div class="head">server error</div>`;
    const p = document.createElement('pre');
    p.textContent = data.error + (data.trace ? '\\n\\n' + data.trace : '');
    m.appendChild(p);
    out.appendChild(m);
    return;
  }

  // Augmented system + rendered user_msgs as context for the run.
  if (data.user_msgs && data.user_msgs.length) {
    const ctx = document.createElement('details');
    ctx.innerHTML = `<summary>Context that was actually sent (${data.user_msgs.length} user msg(s))</summary>`;
    const p = document.createElement('pre');
    p.textContent = data.user_msgs.map((m, i) => `[user ${i+1}]\\n${m}`).join('\\n\\n');
    ctx.appendChild(p);
    out.appendChild(ctx);
  }

  const head = document.createElement('h2');
  const oks = data.runs.filter(r => r.ok).length;
  head.innerHTML = `Results <span class="sub">${oks}/${data.runs.length} succeeded</span>`;
  out.appendChild(head);

  const grid = document.createElement('div');
  grid.className = 'runs' + (data.runs.length > 1 ? ' multi' : '');
  out.appendChild(grid);

  data.runs.forEach((run, i) => {
    const card = document.createElement('div');
    const status = run.ok
      ? `<span class="pill" style="background:#1d3220;color:#3fb950">OK</span>`
      : `<span class="pill" style="background:#321d1d;color:#f85149">FAIL</span>`;
    const elapsed = run.elapsed_s.toFixed(1) + 's';
    card.innerHTML = `<h2>Run ${i + 1} ${status} <span class="sub">${elapsed}, ${run.attempts.length} attempt(s)</span></h2>`;

    if (run.ok) {
      const m = document.createElement('div');
      m.className = 'msg ok';
      m.innerHTML = `<div class="head">parsed value</div>`;
      const p = document.createElement('pre'); p.textContent = JSON.stringify(run.value, null, 2);
      m.appendChild(p); card.appendChild(m);
    }

    run.attempts.forEach((a, ai) => {
      const isLast = ai === run.attempts.length - 1;
      const cls = (isLast && run.ok) ? 'ok'
                : (a.parse_error || (a.schema_errors && a.schema_errors.length)) ? 'bad'
                : 'meh';
      const m = document.createElement('div');
      m.className = 'msg ' + cls;
      m.innerHTML = `<div class="head">attempt ${ai + 1}
        <span style="color:#7d8590">·</span> ${a.elapsed_s.toFixed(1)}s
        ${a.log_name ? `<span style="color:#7d8590">·</span> log: ${a.log_name}` : ''}
      </div>`;
      if (a.parse_error) {
        const e = document.createElement('div');
        e.style.color = '#f85149'; e.textContent = 'parse: ' + a.parse_error;
        m.appendChild(e);
      }
      if (a.schema_errors && a.schema_errors.length) {
        const e = document.createElement('div'); e.style.color = '#d29922';
        e.innerHTML = 'schema:<br>' + a.schema_errors.map(s => '· ' + escapeHtml(s)).join('<br>');
        m.appendChild(e);
      }
      if (a.raw) {
        const det = document.createElement('details');
        det.innerHTML = `<summary>raw content (${a.raw.length} chars)</summary>`;
        const p = document.createElement('pre'); p.textContent = a.raw;
        det.appendChild(p);
        m.appendChild(det);
      }
      card.appendChild(m);
    });

    grid.appendChild(card);
  });
}

function escapeHtml(s) { return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

// ---- Blank mode -----------------------------------------------------
let blankUserMsgs = [''];

function renderBlankMode() {
  const root = document.getElementById('blank-panel');
  root.innerHTML = '';

  const head = document.createElement('div');
  head.innerHTML = `<h2 style="margin-top:0">Blank
                      <span class="sub">freeform system + user msgs, no schema, no validation</span>
                    </h2>`;
  root.appendChild(head);

  // System message
  const sysHead = document.createElement('h2');
  sysHead.innerHTML = 'System message';
  root.appendChild(sysHead);
  const sysTa = document.createElement('textarea');
  sysTa.id = 'blank-system';
  sysTa.placeholder = 'You are a senior engineer. Analyse the documents below...';
  sysTa.style.minHeight = '180px';
  sysTa.value = '';
  root.appendChild(sysTa);

  // Spec render block (populator)
  const specHead = document.createElement('h2');
  specHead.innerHTML = 'build_user_msgs spec <span class="sub">paste a dict like the harness uses; click Render to populate the messages list below (replaces existing messages)</span>';
  root.appendChild(specHead);

  const roleRow = document.createElement('div');
  roleRow.className = 'row';
  roleRow.innerHTML = `<label>role</label>`;
  const roleSel = document.createElement('select');
  roleSel.id = 'blank-role';
  const noneOpt = document.createElement('option');
  noneOpt.value = ''; noneOpt.textContent = '(none — cross-role)';
  roleSel.appendChild(noneOpt);
  for (const r of project.active_roles || []) {
    const o = document.createElement('option');
    o.value = r; o.textContent = r;
    roleSel.appendChild(o);
  }
  roleRow.appendChild(roleSel);
  root.appendChild(roleRow);

  const specTa = document.createElement('textarea');
  specTa.id = 'blank-spec';
  specTa.style.minHeight = '160px';
  // Pre-filled with a starter spec so Render works on first click.
  // Edit freely.
  const starter = {
    plan: true,
    stack: project.active_roles && project.active_roles.length
      ? [project.active_roles[0]]
      : ["frontend"],
    trailing: "your instruction here"
  };
  specTa.value = JSON.stringify(starter, null, 2);
  root.appendChild(specTa);

  const specBtns = document.createElement('div');
  specBtns.className = 'row';
  const renderBtn = document.createElement('button');
  renderBtn.textContent = 'Render preview into messages';
  renderBtn.className = 'secondary';
  specBtns.appendChild(renderBtn);
  const renderStatus = document.createElement('span');
  renderStatus.style.color = '#7d8590'; renderStatus.style.fontSize = '12px';
  specBtns.appendChild(renderStatus);
  root.appendChild(specBtns);

  // Instruction-file picker — append any v84 .md / .schema.json as a
  // user message. Useful for "review this instruction, suggest changes".
  const filesHead = document.createElement('h2');
  filesHead.innerHTML = 'Instruction files <span class="sub">append a v84 .md or .schema.json as a new user message; the file path becomes the message header</span>';
  root.appendChild(filesHead);

  const filesRow = document.createElement('div');
  filesRow.className = 'row';
  const fileSel = document.createElement('select');
  fileSel.id = 'blank-file-sel';
  fileSel.style.flex = '1'; fileSel.style.minWidth = '320px';
  const placeholder = document.createElement('option');
  placeholder.value = ''; placeholder.textContent = 'loading…';
  fileSel.appendChild(placeholder);
  filesRow.appendChild(fileSel);

  const addFileBtn = document.createElement('button');
  addFileBtn.textContent = '+ Add file as message';
  addFileBtn.className = 'secondary';
  filesRow.appendChild(addFileBtn);

  const fileStatus = document.createElement('span');
  fileStatus.style.color = '#7d8590'; fileStatus.style.fontSize = '12px';
  filesRow.appendChild(fileStatus);
  root.appendChild(filesRow);

  // Populate the file select
  fetch('/api/instructions').then(r => r.json()).then(files => {
    fileSel.innerHTML = '';
    let currentGroup = null;
    let currentGrp = null;
    for (const f of files) {
      if (f.group !== currentGroup) {
        currentGrp = document.createElement('optgroup');
        currentGrp.label = f.group;
        fileSel.appendChild(currentGrp);
        currentGroup = f.group;
      }
      const o = document.createElement('option');
      o.value = `${f.group}/${f.name}`;
      o.textContent = `${f.name} (${f.size.toLocaleString()} B)`;
      currentGrp.appendChild(o);
    }
  });

  addFileBtn.addEventListener('click', async () => {
    const v = fileSel.value;
    if (!v) { fileStatus.textContent = 'pick a file first'; return; }
    const [g, n] = v.split('/');
    fileStatus.textContent = 'loading…';
    try {
      const r = await fetch(`/api/instruction/${g}/${n}`);
      const data = await r.json();
      if (data.error) { fileStatus.textContent = data.error; return; }
      const body = `# ${data.relpath}\\n\\n${data.content}`;
      // Drop a single empty leading box if that's all there is.
      if (blankUserMsgs.length === 1 && !blankUserMsgs[0].trim()) {
        blankUserMsgs = [body];
      } else {
        blankUserMsgs.push(body);
      }
      rerenderMsgs();
      fileStatus.textContent = `appended ${data.relpath} (${data.content.length.toLocaleString()} chars)`;
    } catch (e) { fileStatus.textContent = String(e); }
  });

  // Messages list
  const msgsHead = document.createElement('h2');
  msgsHead.innerHTML = 'User messages <span class="sub">add / remove freely. Render above replaces this list; Add file as message appends.</span>';
  root.appendChild(msgsHead);
  const msgList = document.createElement('div');
  msgList.id = 'blank-msglist';
  root.appendChild(msgList);

  function rerenderMsgs() {
    msgList.innerHTML = '';
    blankUserMsgs.forEach((m, i) => {
      const wrap = document.createElement('div');
      wrap.style.marginBottom = '8px';
      const head = document.createElement('div');
      head.style.display = 'flex'; head.style.alignItems = 'center'; head.style.gap = '8px';
      head.innerHTML = `<span style="color:#7d8590;font-size:12px">message ${i + 1} (${m.length} chars)</span>`;
      const rm = document.createElement('button');
      rm.textContent = 'remove'; rm.className = 'secondary';
      rm.style.padding = '2px 8px'; rm.style.fontSize = '11px';
      rm.addEventListener('click', () => {
        blankUserMsgs.splice(i, 1);
        if (!blankUserMsgs.length) blankUserMsgs = [''];
        rerenderMsgs();
      });
      head.appendChild(rm);
      wrap.appendChild(head);
      const ta = document.createElement('textarea');
      ta.value = m;
      ta.addEventListener('input', () => { blankUserMsgs[i] = ta.value; });
      wrap.appendChild(ta);
      msgList.appendChild(wrap);
    });
  }
  rerenderMsgs();

  const addRow = document.createElement('div');
  addRow.className = 'row';
  const addBtn = document.createElement('button');
  addBtn.textContent = '+ message';
  addBtn.className = 'secondary';
  addBtn.addEventListener('click', () => { blankUserMsgs.push(''); rerenderMsgs(); });
  addRow.appendChild(addBtn);
  root.appendChild(addRow);

  renderBtn.addEventListener('click', async () => {
    const txt = specTa.value.trim();
    if (!txt) { renderStatus.textContent = 'spec is empty — paste a JSON object first'; return; }
    let parsed;
    try { parsed = JSON.parse(txt); }
    catch (e) { renderStatus.textContent = `spec parse: ${e}`; return; }
    renderStatus.textContent = 'rendering…';
    try {
      const r = await fetch('/api/render', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({spec: parsed, role: roleSel.value || null}),
      });
      const data = await r.json();
      if (data.error) { renderStatus.textContent = data.error; return; }
      blankUserMsgs = data.user_msgs.length ? data.user_msgs : [''];
      rerenderMsgs();
      renderStatus.textContent = `rendered ${data.user_msgs.length} message(s)`;
    } catch (e) { renderStatus.textContent = String(e); }
  });

  // Knobs
  const knobs = document.createElement('div');
  knobs.innerHTML = `
    <h2>Run</h2>
    <div class="row">
      <label>tag</label>
      <input id="blank-tag" type="text" value="blank" placeholder="lands in .v84-logs/<tag>-blank-...">
    </div>
    <div class="row">
      <label>concurrency</label>
      <input id="blank-concurrency" type="number" value="1" min="1" max="20">
      <label style="min-width:auto;margin-left:14px">retries (re-runs)</label>
      <input id="blank-retries" type="number" value="1" min="1" max="10">
      <label style="min-width:auto;margin-left:14px">max_tokens</label>
      <input id="blank-max-tokens" type="number" value="16000" min="100" max="200000">
    </div>
  `;
  root.appendChild(knobs);

  const sendRow = document.createElement('div');
  sendRow.className = 'row';
  const send = document.createElement('button');
  send.textContent = 'Send to LLM';
  sendRow.appendChild(send);
  const status = document.createElement('span');
  status.style.color = '#7d8590'; status.style.fontSize = '12px';
  sendRow.appendChild(status);
  root.appendChild(sendRow);

  const out = document.createElement('div');
  root.appendChild(out);

  send.addEventListener('click', async () => {
    send.disabled = true;
    out.innerHTML = '';
    const body = {
      system: sysTa.value,
      user_msgs: blankUserMsgs.filter(m => m && m.trim().length > 0),
      max_tokens: Number(document.getElementById('blank-max-tokens').value),
      retries: Number(document.getElementById('blank-retries').value),
      concurrency: Number(document.getElementById('blank-concurrency').value),
      tag: document.getElementById('blank-tag').value || 'blank',
    };
    const expectedRuns = body.concurrency * body.retries;

    // Show pending placeholders for every expected run + a running ticker
    // so the user sees activity even though the response only comes
    // back at the end.
    out.innerHTML = `
      <h2>Results <span class="sub" id="results-sub">${expectedRuns} run(s) in flight…</span></h2>
      <div class="runs ${expectedRuns > 1 ? 'multi' : ''}">
        ${Array.from({length: expectedRuns}, (_, i) =>
          `<div class="msg meh"><div class="head">Run ${i + 1} <span class="pill">pending</span></div></div>`
        ).join('')}
      </div>
    `;
    const sub = document.getElementById('results-sub');
    const t0 = Date.now();
    const ticker = setInterval(() => {
      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      status.textContent = `${elapsed}s elapsed — calling ${expectedRuns} run(s)…`;
      sub.textContent = `${elapsed}s elapsed, still waiting on ${expectedRuns} run(s)…`;
    }, 200);
    console.log(`[blank] sending ${expectedRuns} run(s)`, body);

    try {
      const r = await fetch('/api/test_raw', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body),
      });
      const data = await r.json();
      clearInterval(ticker);
      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      status.textContent = `done in ${elapsed}s wall clock`;
      console.log(`[blank] ${expectedRuns} run(s) done in ${elapsed}s`, data);
      out.innerHTML = '';
      renderRawResults(out, data);
    } catch (e) {
      clearInterval(ticker);
      status.textContent = 'error';
      console.error('[blank] error', e);
      out.innerHTML = `<pre class="msg bad">${escapeHtml(String(e))}</pre>`;
    } finally {
      send.disabled = false;
    }
  });
}

function renderRawResults(out, data) {
  if (data.error) {
    const m = document.createElement('div');
    m.className = 'msg bad';
    m.innerHTML = `<div class="head">server error</div>`;
    const p = document.createElement('pre');
    p.textContent = data.error + (data.trace ? '\\n\\n' + data.trace : '');
    m.appendChild(p);
    out.appendChild(m);
    return;
  }

  const head = document.createElement('h2');
  head.innerHTML = `Results <span class="sub">${data.runs.length} run(s)</span>`;
  out.appendChild(head);

  const grid = document.createElement('div');
  grid.className = 'runs' + (data.runs.length > 1 ? ' multi' : '');
  out.appendChild(grid);

  data.runs.forEach((run, i) => {
    const card = document.createElement('div');
    const hasJson = !run.parse_error && run.parsed !== undefined;
    const cls = hasJson ? 'ok' : (run.parse_error ? 'meh' : 'ok');
    card.innerHTML = `<h2>Run ${i + 1}
        <span class="sub">${run.elapsed_s.toFixed(1)}s
        ${run.log_name ? '· log: ' + run.log_name : ''}</span>
      </h2>`;

    const m = document.createElement('div');
    m.className = 'msg ' + cls;
    m.innerHTML = `<div class="head">raw response (${run.raw.length} chars)</div>`;
    const pre = document.createElement('pre');
    pre.textContent = run.raw;
    m.appendChild(pre);
    card.appendChild(m);

    if (run.parse_error && run.raw) {
      const e = document.createElement('div');
      e.className = 'msg meh';
      e.innerHTML = `<div class="head">not valid JSON</div>`;
      const p = document.createElement('div');
      p.style.color = '#d29922'; p.textContent = run.parse_error;
      e.appendChild(p);
      card.appendChild(e);
    }
    if (hasJson) {
      const j = document.createElement('details');
      j.innerHTML = `<summary>parsed as JSON</summary>`;
      const p = document.createElement('pre'); p.textContent = JSON.stringify(run.parsed, null, 2);
      j.appendChild(p);
      card.appendChild(j);
    }

    grid.appendChild(card);
  });
}

// ---- Mode toggle ----------------------------------------------------
function setMode(mode) {
  const isPreview = mode === 'preview';
  document.getElementById('main-preview').style.display = isPreview ? 'grid' : 'none';
  document.getElementById('main-blank').style.display = isPreview ? 'none' : 'grid';
  document.getElementById('mode-preview').classList.toggle('active', isPreview);
  document.getElementById('mode-blank').classList.toggle('active', !isPreview);
  if (mode === 'blank') renderBlankMode();
}
document.getElementById('mode-preview').addEventListener('click', () => setMode('preview'));
document.getElementById('mode-blank').addEventListener('click', () => setMode('blank'));

(async () => {
  await loadProject();
  await loadStages();
})();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument(
        "--project", type=Path, default=None,
        help="Project directory (the folder containing v84/). Defaults "
             "to the parent of v84-docs/ — same default as v84.py.",
    )
    args = parser.parse_args(argv)

    project_dir = args.project or v84_docs_root().parent
    project_dir = project_dir.resolve()

    try:
        cfg = resolve_llm(project_dir=project_dir, interactive=False)
    except RuntimeError as exc:
        print(f"could not resolve LLM config: {exc}", file=sys.stderr)
        return 1
    Handler.cfg = cfg
    Handler.project = ProjectCtx(project_dir)

    print(
        f"playground using {cfg.model} @ {cfg.url}",
        file=sys.stderr,
    )
    print(f"project: {project_dir}", file=sys.stderr)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        f"listening on http://{args.host}:{args.port} "
        f"(open http://localhost:{args.port}/ in a browser)",
        file=sys.stderr,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
