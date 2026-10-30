"""api-agents: the agent-testing half of this repo as a first-party package.

Extracted per docs/ADR-002-api-agents-extraction.md (boundary map + import
cuts, S40; this package is S41). The stable API is exactly ``__all__`` below;
everything else inside the package is an implementation detail.

Import contract (ADR-002 rule 2, guarded by
tests/test_api_agents_boundary_s41.py):

- may import stdlib, the provider SDKs (openai, anthropic), and ``config``
  (read-only env);
- must **never** import ``models.*``, ``schemas.*``, ``database``, or
  ``core.security`` — no SQL, no auth, no ambient DB session crosses this
  boundary. Callers inject credentials/limits as arguments; routers persist
  what the package returns, one direction only.

Keeping the package import-light is the point: the S24 Mac companion can
import ``api_agents`` against the on-device Ollama/fine-tuned server without
dragging FastAPI and SQLAlchemy along.
"""

from api_agents.chat.client import chat_completion
from api_agents.chat.compare import (
    fan_out,
    hosted_backends,
    installed_ollama_models,
    local_backends,
    ollama_backend,
)
from api_agents.generation.client import call_json_tool
from api_agents.generation.local_registry import prefer_order
from api_agents.generation.status import generation_status as local_model_status

__all__ = [
    "call_json_tool",
    "chat_completion",
    "hosted_backends",
    "local_backends",
    "ollama_backend",
    "fan_out",
    "installed_ollama_models",
    "local_model_status",
    "prefer_order",
]
