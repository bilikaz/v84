"""
menu — Top-level interactive menu.

Default landing screen for an interactive `python3 v84.py` run.
Lets the operator choose between starting the pipeline, tuning
LLM endpoints, and managing the project's promoted rules,
without forcing them through the stage loop on every invocation.

Power-user flags (--call, --force, --auto, --status, --llm-set,
--reset-llm) bypass the menu entirely; they wire into the same
dispatch helpers the menu uses.
"""

from .main import run_main_menu

__all__ = ["run_main_menu"]
