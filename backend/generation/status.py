"""Probe which generation backends are actually usable, without spending tokens.

The ladder in client.py fails through tiers at *request* time, which leaves the
UI showing a bare "Generating..." while a keyless or out-of-credit provider
refuses calls. This module answers the same question up front: what can
generation reach right now, and why not, so the app can warn before a click.
"""

import urllib.error
import urllib.request

from config import settings


def _probe_anthropic() -> dict:
    from generation.client import _get_anthropic_client

    if _get_anthropic_client() is None:
        return {"ready": False, "reason": "no ANTHROPIC_API_KEY configured"}
    return {"ready": True, "reason": "key configured (validated on first call)"}


def _probe_openai() -> dict:
    from generation.client import _get_openai_client

    if _get_openai_client() is None:
        return {"ready": False, "reason": "no OPENAI_API_KEY configured"}
    return {"ready": True, "reason": "key configured (validated on first call)"}


def _probe_ollama() -> dict:
    from generation.client import _ollama_local_models

    url = settings.ollama_base_url.rstrip("/") + "/api/version"
    try:
        with urllib.request.urlopen(url, timeout=3):
            pass
    except (urllib.error.URLError, OSError, ValueError):
        return {"ready": False, "reason": f"not reachable at {settings.ollama_base_url}", "models": []}
    models = _ollama_local_models()
    if not models:
        return {
            "ready": False,
            "reason": "reachable but no models installed (run: ollama pull llama3.1)",
            "models": [],
        }
    return {"ready": True, "reason": f"{len(models)} model(s) installed", "models": models}


def generation_status() -> dict:
    """Report the three generation tiers. Never raises; a broken tier reports why."""
    tiers = {}
    for name, probe in (("anthropic", _probe_anthropic), ("openai", _probe_openai), ("ollama", _probe_ollama)):
        try:
            tiers[name] = probe()
        except Exception as exc:  # a probe must never take down the endpoint
            tiers[name] = {"ready": False, "reason": f"probe failed: {exc}", "models": []}
    ready = [n for n, t in tiers.items() if t["ready"]]
    return {
        "tiers": tiers,
        "ready_count": len(ready),
        "usable": bool(ready),
        "summary": (
            ", ".join(f"{n}: {tiers[n]['reason']}" for n in tiers)
            if ready
            else "No generator backend is reachable. Add an API key to ~/.llmtuner/.env "
                 "or start Ollama and pull a model, then restart `llmtuner up`."
        ),
    }
