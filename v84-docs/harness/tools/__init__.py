"""
tools — package of LLM-callable tools.

One tool per submodule. Each submodule exposes:
    SCHEMA : dict      the OpenAI function-calling schema sent to the LLM
    call   : Callable  executed when the LLM invokes the tool

The package __init__.py collects them into a TOOLS registry and
provides `tools_for(names)` to pick a subset.

Adding a new tool:
    1. Create tools/<name>.py with:
           def call(<params>) -> str: ...
           SCHEMA = {"type": "function", "function": {...}}
    2. Import the module below and add an entry to TOOLS.

Stages expose only the tools they want — they declare a
SUPPORTED_TOOLS tuple and call `tools_for(SUPPORTED_TOOLS)` to build
a sub-registry for the LLM call:

    from tools import tools_for

    SUPPORTED_TOOLS = ("ask_user",)
    ...
    response = call(
        cfg, system, user_msgs,
        tools=tools_for(SUPPORTED_TOOLS),
        ...
    )
"""

from __future__ import annotations

from typing import Iterable

from . import ask_user
from . import survey


# Registry keyed by tool name. Each value is {"schema": ..., "call": ...}.
TOOLS: dict[str, dict] = {
    "ask_user": {"schema": ask_user.SCHEMA, "call": ask_user.call},
    "survey":   {"schema": survey.SCHEMA,   "call": survey.call},
}


def tools_for(names: Iterable[str]) -> dict[str, dict]:
    """Return a sub-registry containing only the named tools.

    Raises KeyError on an unknown name — surfaces typos and renames
    early instead of silently dropping the tool.
    """
    return {name: TOOLS[name] for name in names}


__all__ = ["TOOLS", "tools_for"]
