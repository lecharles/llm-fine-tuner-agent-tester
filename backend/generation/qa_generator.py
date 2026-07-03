"""Turn a plain-English use-case description into deduplicated Q/A pairs.

Strategy (see docs/RESEARCH_DATASETS.md): a system prompt owns the rules and the JSON shape, the
model returns pairs through a forced tool (structured output, not parsed from prose), and we dedup
on our side by normalizing the question text. If a call returns fewer unique pairs than asked, we
top up with more calls, up to a cap.
"""

from generation.client import call_json_tool

TOOL_NAME = "emit_qa_pairs"
MAX_ATTEMPTS = 3
MAX_TOKENS = 16384

PAIRS_SCHEMA = {
    "type": "object",
    "properties": {
        "pairs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                },
                "required": ["question", "answer"],
            },
        }
    },
    "required": ["pairs"],
}

SYSTEM_PROMPT = (
    "You generate training data for fine-tuning a small language model. "
    "Given a use case, produce diverse, factual question and answer pairs. "
    "Vary the phrasing and difficulty of the questions. Keep each answer correct, "
    "self-contained, and concise. Do not repeat questions. "
    "Return the pairs only through the emit_qa_pairs tool."
)


def build_user_prompt(description: str, count: int) -> str:
    """The user turn: the use case and how many pairs to make. A short example fixes the tone."""
    return (
        f"Use case: {description}\n\n"
        f"Generate {count} question and answer pairs for this use case. "
        f'For example, a pair might look like: {{"question": "What is ...?", "answer": "..."}}.'
    )


def _normalize(question: str) -> str:
    """Key for dedup: lowercase and collapse whitespace so trivially different phrasings of the
    same question collapse to one."""
    return " ".join(question.lower().split())


def dedupe(pairs: list[dict]) -> list[dict]:
    """Drop pairs whose normalized question was already seen, preserving order."""
    seen = set()
    unique = []
    for pair in pairs:
        key = _normalize(pair["question"])
        if key and key not in seen:
            seen.add(key)
            unique.append(pair)
    return unique


def generate_pairs(description: str, count: int) -> list[dict]:
    """Generate up to `count` unique Q/A pairs for the description. Calls the model, dedupes, and
    tops up with more calls if short, up to MAX_ATTEMPTS. Returns the unique pairs (at most count)."""
    unique: list[dict] = []
    for _ in range(MAX_ATTEMPTS):
        needed = count - len(unique)
        if needed <= 0:
            break
        result = call_json_tool(
            system=SYSTEM_PROMPT,
            user=build_user_prompt(description, needed),
            tool_name=TOOL_NAME,
            input_schema=PAIRS_SCHEMA,
            max_tokens=MAX_TOKENS,
        )
        unique = dedupe(unique + result.get("pairs", []))
    return unique[:count]