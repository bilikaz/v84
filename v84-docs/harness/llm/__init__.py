"""
llm — LLM client plumbing.

Two concerns live here:

    client.py   LLM call (OpenAI-compat), schema-constrained JSON
                output, think-block stripping.
    config.py   Endpoint resolution from profile.yaml + bootstrap
                cache + interactive prompt. Persists back. No env
                vars (except LLM_API_KEY for secrets).

Most callers import from this package's top level:

    from llm import LLMConfig, call_json, CallSpec, call_many
    from llm import resolve_llm, reset_cache

`call_json(cfg, system, user_msgs, response_schema, ...)` is the
single calling primitive. The provider enforces the JSON Schema at
sampling time (vLLM/xgrammar, OpenAI guided generation), so the
returned value is always a parsed JSON value matching the schema.

Advanced callers needing a submodule directly can use:

    from llm.client import _probe_models   # internal helpers
    from llm.config import CACHE_FILE
"""

from .client import (
    LLMConfig,
    THINK_CLOSE,
    call_json,
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
    "THINK_CLOSE",
    "call_json",
    "call_many",
    "resolve_llm",
    "reset_cache",
]
