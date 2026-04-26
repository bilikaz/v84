"""
llm — LLM client plumbing.

Two concerns live here:

    client.py   LLM call (OpenAI-compat), marker-with-retry parsing,
                tool-call loop, think-block stripping.
    config.py   Endpoint resolution from profile.yaml + bootstrap
                cache + interactive prompt. Persists back. No env
                vars (except LLM_API_KEY for secrets).

Most callers import from this package's top level:

    from llm import LLMConfig, call
    from llm import resolve_llm, reset_cache

`call(cfg, system, user_msgs, *, marker=True, ...)` handles both
marker-validated stage calls (default) and raw prompt/response
exchanges (`marker=False`).

Advanced callers needing a submodule directly can use:

    from llm.client import _probe_models   # internal helpers
    from llm.config import CACHE_FILE
"""

from .client import (
    LLMConfig,
    MARKER,
    THINK_CLOSE,
    call,
)
from .concurrent import (
    CallResult,
    CallSpec,
    call_many,
)
from .config import (
    resolve_llm,
    reset_cache,
)

__all__ = [
    "CallResult",
    "CallSpec",
    "LLMConfig",
    "MARKER",
    "THINK_CLOSE",
    "call",
    "call_many",
    "resolve_llm",
    "reset_cache",
]
