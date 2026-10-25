"""S27: deterministic use-case-prompt suggestions.

The "Suggest" button on the dataset page must work even when every generation
tier is unreachable, so this module is zero-LLM: it templates a starter prompt
from the dataset's saved name/description. The result is a starting point the
user can edit before saving.
"""

_MAX_TOPIC = 120

_DESCRIPTION_TEMPLATE = (
    "You are an assistant for {topic}. Answer every question on that subject "
    "with concrete, practical detail."
)
_NAME_TEMPLATE = (
    "You are an assistant that helps with {topic}. Answer clearly and concisely."
)


def _clean(text: str | None) -> str:
    """Collapse whitespace, drop trailing punctuation, bound the length."""
    topic = " ".join((text or "").split()).rstrip(".;:,")
    if len(topic) > _MAX_TOPIC:
        topic = topic[:_MAX_TOPIC].rstrip(",;: ") + "…"
    return topic


def suggest_use_case_prompt(name: str | None, description: str | None = None) -> str:
    """Build a starter use-case prompt from the dataset's name/description.

    The description (when present) carries the topic; the name is the fallback.
    Returns "" when there is nothing to suggest from.
    """
    topic_description = _clean(description)
    topic_name = _clean(name)

    if topic_description:
        return _DESCRIPTION_TEMPLATE.format(topic=topic_description)
    if topic_name:
        return _NAME_TEMPLATE.format(topic=topic_name)
    return ""
