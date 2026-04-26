#!/usr/bin/env python3
"""
config.py — LLM endpoint config: discover, prompt, persist.

Two named tiers live under `llm:` in profile.yaml:

    single   default endpoint, used for one-at-a-time stage calls
             (roles, stack, decompose).
    multi    optional endpoint used when 2+ agents run concurrently
             (writer/reviewer cascade in the iteration loop). Falls
             back to `single` when not set, so projects can ignore
             the multi tier until they need it.

Resolution order for a tier's URL + model, first-wins:
    1. Project profile.yaml        (<project>/v84/profile.yaml — `llm:` block)
    2. User cache                  (~/.config/v84/config.yaml — bootstrap)
    3. Interactive prompt          (if a TTY is attached) — single tier only
    4. Raise — no way to resolve

`LLM_API_KEY` (only) is read from the environment because secrets
shouldn't live in checked-in YAML. URL and model live in profile.yaml
so the project owns its LLM choice; edit the file or run
`v84.py --llm-set [URL]` / `--llm-set-multi [URL]`.

Once resolved, the URL+model are persisted to whichever sink already
owns them: profile.yaml when the project has one, otherwise the user
cache (bootstrap before the first project init).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Optional

import yaml

from .client import LLMConfig, _probe_models


CACHE_DIR = Path.home() / ".config" / "v84"
CACHE_FILE = CACHE_DIR / "config.yaml"

TIERS = ("single", "multi")
DEFAULT_TIER = "single"


# -----------------------------------------------------------------------------
# Public entry point
# -----------------------------------------------------------------------------

def resolve_llm(
    *,
    project_dir: Optional[Path] = None,
    tier: str = DEFAULT_TIER,
    interactive: bool = True,
    force_url: Optional[str] = None,
    force_rescan: bool = False,
) -> LLMConfig:
    """Return a working LLMConfig for the given tier or raise RuntimeError.

    project_dir   project root (used to find profile.yaml).
    tier          "single" (default) or "multi". When tier="multi" is
                  not configured, falls back to "single".
    interactive   if False, never prompt — used in scripted contexts.
    force_url     use this URL and re-probe the model. Always written
                  to the requested tier.
    force_rescan  re-probe the model from the resolved URL.
    """
    if tier not in TIERS:
        raise ValueError(f"unknown tier {tier!r}; must be one of {TIERS}")

    profile_path = (
        project_dir / "v84" / "profile.yaml" if project_dir else None
    )
    profile_all = (
        _read_profile_llm(profile_path) if profile_path and profile_path.exists()
        else {}
    )
    cached = _read_cache()

    api_key = os.getenv("LLM_API_KEY")

    profile_tier = profile_all.get(tier) or {}
    cached_tier = cached.get(tier) or {}

    # Multi falls back to single when not yet configured — projects don't
    # need to set up parallel infra until they actually parallelise.
    if tier == "multi" and not (force_url or profile_tier or cached_tier):
        return resolve_llm(
            project_dir=project_dir,
            tier="single",
            interactive=interactive,
            force_url=force_url,
            force_rescan=force_rescan,
        )

    # URL: passed-in > profile.yaml > user cache > prompt.
    url = force_url or profile_tier.get("url") or cached_tier.get("url")
    if not url:
        if not interactive:
            raise RuntimeError(
                f"No LLM URL configured for tier {tier!r}. "
                f"Set one in profile.yaml or run interactively."
            )
        url = _prompt_for_url(tier)

    # Model: profile / cache value, unless force_url or force_rescan
    # invalidate it — then re-probe.
    if force_url or force_rescan:
        model = None
    else:
        model = profile_tier.get("model") or cached_tier.get("model")

    if not model:
        probed = _probe_models(url, api_key)
        if not probed:
            raise RuntimeError(
                f"LLM endpoint unreachable or not OpenAI-compatible: {url}\n"
                f"Check with: curl {url.rstrip('/')}/models"
            )
        model = probed

    # max_concurrency: profile-set wins; default 1 for single, 4 for multi
    # (sensible for fan-out without overwhelming a small local server).
    raw_mc = profile_tier.get("max_concurrency")
    if raw_mc is None:
        max_concurrency = 1 if tier == "single" else 4
    else:
        try:
            max_concurrency = max(1, int(raw_mc))
        except (TypeError, ValueError):
            max_concurrency = 1 if tier == "single" else 4

    # Persist the resolved tier back to its owning sink.
    payload = {"url": url, "model": model, "max_concurrency": max_concurrency}
    if profile_path and profile_path.exists():
        _write_profile_llm_tier(profile_path, tier, payload)
    else:
        _write_cache_tier(tier, payload)

    return LLMConfig(
        url=url, model=model, api_key=api_key,
        max_concurrency=max_concurrency,
    )


def reset_cache() -> None:
    """Delete the user-level cache file. Profile.yaml is left alone —
    delete it manually if you want to re-init a project's LLM.
    """
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()


# -----------------------------------------------------------------------------
# profile.yaml `llm:` block — read + in-place write (preserves comments)
# -----------------------------------------------------------------------------

# Matches a top-level `llm:` block: the header line plus any subsequent
# indented lines, ending at the next non-indented non-blank line or EOF.
_LLM_BLOCK_RE = re.compile(
    r"(?m)^llm:[ \t]*\n(?:[ \t]+\S.*\n)*",
)


def _read_profile_llm(profile_path: Path) -> dict:
    """Return the `llm:` mapping (with tier sub-mappings) from
    profile.yaml, or {} if missing.
    """
    try:
        data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    llm = data.get("llm")
    return llm if isinstance(llm, dict) else {}


def _write_profile_llm_tier(profile_path: Path, tier: str, cfg: dict) -> None:
    """Update profile.yaml's `llm:` block in place — sets/overwrites
    one tier, leaves the other tier(s) intact.
    """
    current = _read_profile_llm(profile_path)
    # Merge: keep other tiers, replace the one we're writing.
    merged: dict[str, dict] = {}
    for t in TIERS:
        if t == tier:
            merged[t] = cfg
        elif isinstance(current.get(t), dict) and current[t]:
            merged[t] = current[t]

    block = render_llm_block(merged)
    text = profile_path.read_text(encoding="utf-8")
    if _LLM_BLOCK_RE.search(text):
        text = _LLM_BLOCK_RE.sub(block + "\n", text, count=1)
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += "\n" + block + "\n"
    profile_path.write_text(text, encoding="utf-8")


def render_llm_block(llm: dict) -> str:
    """Render a fresh `llm:` block with tier sub-blocks. Used by
    roles.py for first-time profile.yaml creation and by the
    in-place writer above.
    """
    lines = ["llm:"]
    for tier in TIERS:
        cfg = llm.get(tier)
        if not isinstance(cfg, dict) or not cfg:
            continue
        lines.append(f"  {tier}:")
        lines.append(f"    url: {cfg['url']}")
        lines.append(f"    model: {cfg['model']}")
        mc = cfg.get("max_concurrency")
        if mc is not None:
            lines.append(f"    max_concurrency: {mc}")
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Interactive prompt
# -----------------------------------------------------------------------------

def _prompt_for_url(tier: str) -> str:
    """Ask the user for an LLM API URL. Returns a validated-looking URL."""
    print(f"LLM endpoint not configured for tier {tier!r}.", file=sys.stderr)
    print(
        "Examples:\n"
        "  http://localhost:8000/v1    (vLLM on this machine)\n"
        "  http://localhost:11434/v1   (Ollama)\n"
        "  https://api.openai.com/v1   (OpenAI — also set LLM_API_KEY)",
        file=sys.stderr,
    )
    while True:
        try:
            url = input(f"URL ({tier}): ").strip()
        except EOFError:
            raise RuntimeError("no URL provided")
        if not url:
            continue
        if not (url.startswith("http://") or url.startswith("https://")):
            print("URL must start with http:// or https://", file=sys.stderr)
            continue
        return url.rstrip("/")


# -----------------------------------------------------------------------------
# User cache I/O — bootstrap-only fallback before profile.yaml exists.
# Cache mirrors profile.yaml's tiered shape under a top-level `llm:`.
# -----------------------------------------------------------------------------

def _read_cache() -> dict:
    """Return cached config as a {tier: {url, model}} mapping. Empty
    dict if missing or malformed.
    """
    if not CACHE_FILE.exists():
        return {}
    try:
        data = yaml.safe_load(CACHE_FILE.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(data, dict):
        return {}
    llm = data.get("llm")
    return llm if isinstance(llm, dict) else {}


def _write_cache_tier(tier: str, cfg: dict) -> None:
    """Set/overwrite one tier in the user cache. Other tiers preserved."""
    current = _read_cache()
    current[tier] = cfg
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# v84 LLM bootstrap cache — used until a project profile.yaml exists",
        "llm:",
    ]
    for t in TIERS:
        c = current.get(t)
        if not isinstance(c, dict) or not c:
            continue
        lines.append(f"  {t}:")
        lines.append(f"    url: {c['url']}")
        lines.append(f"    model: {c['model']}")
    CACHE_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
