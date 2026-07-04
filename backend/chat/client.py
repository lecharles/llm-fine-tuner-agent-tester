"""OpenAI-compatible chat client for the four-way compare.

Every compare backend that speaks the OpenAI /v1/chat/completions shape is
called through this one function: the fine-tuned and vanilla Llama columns
served locally by Ollama, and the hosted OpenAI column. We keep one client
shape and swap the base URL, model name, and API key per backend, the same idea
as coding to one interface with swappable implementations.

How the Anthropic column is called is decided when we wire the compare-chat
orchestration. Serving notes are in docs/RESEARCH_MLX.md.
"""

from openai import OpenAI


def chat_completion(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
) -> str:
    """Send one chat request to an OpenAI-compatible endpoint and return the
    assistant reply text.

    base_url selects the backend: Ollama's local server for the Llama columns,
    the default OpenAI URL for the hosted column. api_key is that backend's
    credential (Ollama accepts any placeholder, OpenAI takes your configured
    key). messages is the standard list of {"role": ..., "content": ...} turns.
    Returns the text of the first choice's message.
    """
    client = OpenAI(base_url=base_url, api_key=api_key)
    response = client.chat.completions.create(model=model, messages=messages)
    return response.choices[0].message.content