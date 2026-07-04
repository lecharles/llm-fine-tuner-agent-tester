"""Fan one prompt out to several compare backends and collect labeled replies.

The compare chat shows the same prompt answered by up to four models side by side.
Every backend is an OpenAI-compatible endpoint (the two Llama columns via Ollama,
the OpenAI column, and the Anthropic column via its compat endpoint), so all of
them go through the one chat_completion function, just with a different base URL,
key, and model. Adding a column later means appending one Backend to the list.

One backend failing does not sink the others: each call is isolated, so a failure
is captured as an error on that column and the replies that did come back are still
returned.
"""

from dataclasses import dataclass

from chat.client import chat_completion
from config import settings

# Fixed endpoints for the hosted providers. The Llama columns will add their own
# Ollama base URL here once local serving is wired.
OPENAI_BASE_URL = "https://api.openai.com/v1"
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1/"


@dataclass
class Backend:
    """One compare column: where to send the prompt and how to label the reply."""

    label: str
    base_url: str
    api_key: str
    model: str


@dataclass
class Reply:
    """One column's result. Exactly one of content or error is set."""

    label: str
    model: str
    content: str | None = None
    error: str | None = None


def hosted_backends(openai_model: str, anthropic_model: str) -> list[Backend]:
    """Build the two hosted columns from settings plus the caller's model choices.
    The fine-tuned and vanilla Llama columns get appended to this list once Ollama
    serving is in place."""
    return [
        Backend("openai", OPENAI_BASE_URL, settings.openai_api_key, openai_model),
        Backend("anthropic", ANTHROPIC_BASE_URL, settings.anthropic_api_key, anthropic_model),
    ]


def fan_out(backends: list[Backend], messages: list[dict]) -> list[Reply]:
    """Send the same messages to every backend and collect labeled replies.

    Sequential for now (one call after another). A single backend raising is
    caught and returned as an error on that column instead of aborting the run,
    so the compare always shows whatever did come back. Catching broad Exception
    is deliberate here: any provider or network error should degrade one column,
    not the whole response."""
    replies = []
    for backend in backends:
        try:
            content = chat_completion(
                backend.base_url, backend.api_key, backend.model, messages
            )
            replies.append(Reply(label=backend.label, model=backend.model, content=content))
        except Exception as exc:
            replies.append(Reply(label=backend.label, model=backend.model, error=str(exc)))
    return replies