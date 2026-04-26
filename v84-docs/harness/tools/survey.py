"""
survey — tool: ask the human multiple questions in one round, with
optional multi-choice pickers per question.

Designed for when the LLM has several things to clarify at once.
Batching is faster for the user than a sequence of single `ask_user`
calls — they see all questions upfront and answer in one sitting.

Each question can optionally offer choices (a/b/c...). The user can
pick a letter or type a free-text answer. Return format is structured
so the LLM can parse answers back reliably.

Use ask_user for a single question. Use survey when you have 2+
clarifications or when offering discrete options saves back-and-forth.
"""

from __future__ import annotations

import string
import sys


def call(questions: list[dict]) -> str:
    """Ask a batch of questions, return structured answers.

    Parameters
    ----------
    questions : list[dict]
        Each dict has:
            question  str  required — the question text
            context   str  optional — why you're asking / default if skipped
            choices   list[str]  optional — 2-8 discrete options.
                      If present, user picks a letter (a, b, ...) or
                      types a custom answer.

    Returns a YAML-formatted summary of Q/A pairs that the LLM can
    parse. Empty/missing answers come back as "(user skipped)" so
    the LLM still has a non-empty response to work with.
    """
    # Defensive: schema guarantees a list but models sometimes send
    # a single dict or a string. Normalise.
    if isinstance(questions, dict):
        questions = [questions]
    if not isinstance(questions, list) or not questions:
        return "Error: 'questions' must be a non-empty list of question objects"

    n = len(questions)
    suffix = f" ({n} questions)" if n > 1 else ""

    _banner(f"AGENT SURVEY{suffix}")

    answers: list[dict] = []
    for i, q in enumerate(questions, 1):
        if not isinstance(q, dict):
            answers.append({
                "question": str(q),
                "answer": "(malformed — expected object)",
            })
            continue

        question = str(q.get("question", "")).strip()
        context = str(q.get("context", "")).strip()
        choices = q.get("choices") or []
        if not isinstance(choices, list):
            choices = []

        if not question:
            answers.append({"question": "", "answer": "(skipped — empty question)"})
            continue

        print("", file=sys.stderr)
        print(f"Q{i}: {question}", file=sys.stderr)
        if context:
            print(f"    (context: {context})", file=sys.stderr)

        # Render lettered choices
        if choices:
            for j, choice in enumerate(choices):
                # Only generate a-z; if someone passes >26 choices,
                # remaining entries fall back to numeric indices.
                letter = (
                    string.ascii_lowercase[j]
                    if j < len(string.ascii_lowercase)
                    else str(j + 1)
                )
                print(f"    {letter}) {choice}", file=sys.stderr)
            print(f"    (pick a letter or type a custom answer)", file=sys.stderr)

        # Prompt
        try:
            raw = input(f"Q{i}> ").strip()
        except EOFError:
            print("", file=sys.stderr)
            answers.append({"question": question, "answer": "(user skipped)"})
            continue

        answers.append(_resolve_answer(question, raw, choices))

    _banner_close()
    return _format_answers(answers)


SCHEMA = {
    "type": "function",
    "function": {
        "name": "survey",
        "description": (
            "Ask the human operator a batch of clarifying questions in one "
            "round. Use when you have 2+ questions, or when offering "
            "discrete choices makes the answer easier than free-text. "
            "For a single free-form question use ask_user instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "description": "One or more questions to ask in a batch.",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": (
                                    "Specific, concrete question. Short is "
                                    "better — one sentence is ideal."
                                ),
                            },
                            "context": {
                                "type": "string",
                                "description": (
                                    "Optional one-sentence explanation of "
                                    "why you're asking and what default "
                                    "you'd pick if the user skips."
                                ),
                            },
                            "choices": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Optional 2-8 discrete options to offer. "
                                    "User picks a letter (a, b, c, ...) or "
                                    "types a custom answer. Include choices "
                                    "when the answer space is bounded — "
                                    "makes responding fast."
                                ),
                            },
                        },
                        "required": ["question"],
                    },
                },
            },
            "required": ["questions"],
        },
    },
}


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _resolve_answer(question: str, raw: str, choices: list[str]) -> dict:
    """Turn raw input into a structured answer.

    If the user typed exactly one letter matching a choice index,
    we record both the chose letter and the resolved choice text.
    Otherwise it's a custom answer (free text).
    """
    if not raw:
        return {"question": question, "answer": "(user left blank)"}

    # Single-letter pick against the choices list
    if choices and len(raw) == 1 and raw.isalpha():
        idx = ord(raw.lower()) - ord("a")
        if 0 <= idx < len(choices):
            return {
                "question": question,
                "answer": choices[idx],
                "chose": raw.lower(),
            }

    # Free-text answer (or letter outside range)
    return {
        "question": question,
        "answer": raw,
        "chose": "custom" if choices else None,
    }


def _format_answers(answers: list[dict]) -> str:
    """Return a YAML-ish block the LLM can parse reliably."""
    lines = []
    for i, a in enumerate(answers, 1):
        lines.append(f"Q{i}: {a['question']}")
        lines.append(f"A{i}: {a['answer']}")
        if a.get("chose") and a["chose"] != "custom":
            lines.append(f"    (picked option {a['chose']})")
    return "\n".join(lines)


def _banner(title: str) -> None:
    print("", file=sys.stderr)
    print("━" * 59, file=sys.stderr)
    print(title, file=sys.stderr)
    print("━" * 59, file=sys.stderr)


def _banner_close() -> None:
    print("━" * 59, file=sys.stderr)
    print("", file=sys.stderr)
