"""
cache.py — Per-iteration disk cache for rendered context blocks.

Many stages (draft, review, lead, patch) call the same context
builders — `roles_block(frontend)`, `conventions_block(frontend)`,
`role_history_block(frontend)`, etc. — over and over within one
iteration. Each call reads the same source YAML and produces the
same markdown.

The cache stores each rendered block as one file under
`iterations/<n>/cache/<func_name>.<params>.md`. On read:

    - If the cache file exists AND every source file is at least
      as old as the cache file → return the cached text.
    - Otherwise → re-render, overwrite the cache file, return.

Why per-iteration: each iteration is a self-contained cycle.
Cache lives the iteration's lifespan, then dies with it
(iterations/<n>/cache/ folder is removed when the iteration is
cleaned up — restart_cycle / archive). Cross-iteration cache
state stays out of the picture.

Why filename = func+params (no hash): inspection. You can
`cat iterations/1/cache/roles_block.frontend.md` to see exactly
what every stage sent the LLM for that block. Stale renders are
overwritten cleanly; no `.<hash>.md` clutter.

Sources that don't exist (e.g. role_history_block reading a
documentation file that doesn't yet exist on iteration 1) are
skipped — they don't invalidate the cache. The render function
handles "no file" by returning empty string; the cache stores the
empty result and reuses it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable


def cached(
    name: str,
    sources: list[Path],
    render: Callable[[], str],
    iter_dir: Path,
) -> str:
    """Return rendered text from cache or compute fresh.

    `name`     human-readable cache key (e.g. "roles_block.frontend").
               Becomes the cache filename: `<iter_dir>/cache/<name>.md`.
    `sources`  list of paths the render reads. Cache invalidates when
               any source's mtime is newer than the cached file's mtime.
               Non-existent sources are skipped (don't invalidate).
    `render`   nullary callable that produces the markdown when called.
    `iter_dir` `iterations/<n>/` — cache lives under `cache/` here.
    """
    cache_file = iter_dir / "cache" / f"{name}.md"
    if cache_file.exists():
        cache_mtime = cache_file.stat().st_mtime
        if all(
            (not p.exists()) or p.stat().st_mtime <= cache_mtime
            for p in sources
        ):
            return cache_file.read_text(encoding="utf-8")
    rendered = render()
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(rendered, encoding="utf-8")
    return rendered
