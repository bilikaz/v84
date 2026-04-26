"""
ask_user — tool: surface a clarifying question to the human operator.

Used mid-stage when the brief is genuinely ambiguous and picking
wrongly would mislead the whole project. The LLM invokes this tool,
the harness prompts the operator, the operator's answer is fed back
into the conversation as a tool result, and the LLM continues.

The `SCHEMA` below is what the LLM sees. The `call` function below
is what actually executes.
"""

from __future__ import annotations

import sys


def call(question: str, context: str = "") -> str:
    """Prompt the human operator and return their answer.

    Parameters
    ----------
    question
        The clarifying question, short and concrete.
    context
        Optional: one-sentence explanation of why the agent is
        asking and what it would assume if the user skips.

    Returns the answer verbatim (whitespace-stripped). If the user
    hits Ctrl+D without typing, returns "(user skipped)" so the LLM
    gets a non-empty string and knows to fall back to its default.
    """
    # Blank line + banner makes the prompt visible even after spinner
    # output has been printed to the same stream.
    print("", file=sys.stderr)
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
          file=sys.stderr)
    print(f"AGENT ASKS: {question}", file=sys.stderr)
    if context:
        print("", file=sys.stderr)
        print(f"(context: {context})", file=sys.stderr)
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
          file=sys.stderr)
    try:
        answer = input("> ").strip()
    except EOFError:
        print("", file=sys.stderr)
        return "(user skipped)"
    return answer or "(user left blank)"


SCHEMA = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": (
            "Ask the human operator a clarifying question. Use this ONLY "
            "when the brief is genuinely ambiguous and the wrong guess "
            "would mislead the whole project. Prefer to make a best-guess "
            "with a noted assumption in your output rather than asking — "
            "reserve ask_user for cases where the wrong guess is harmful."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": (
                        "A specific, concrete question. Short is better."
                    ),
                },
                "context": {
                    "type": "string",
                    "description": (
                        "Optional one-sentence explanation of why you're "
                        "asking and what you'd assume if not told."
                    ),
                },
            },
            "required": ["question"],
        },
    },
}
