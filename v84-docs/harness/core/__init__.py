"""
core — cross-cutting harness infrastructure.

Modules that aren't domain-specific (LLM, stages, init/cycle flow)
but are used across the harness.

Layout:
    stage.py         Stage dataclass shared by every stage registry
    state.py         project-state detection used by v84.py
    util.py          path/dir helpers (v84_docs_root, project_root)
    context.py       prompt-context builders (roles_block, stack_block)

Sibling top-level packages: `ui/` (terminal UI primitives), `init/`
(init-flow stages), `llm/` (LLM client), `tools/` (LLM tools).
"""
