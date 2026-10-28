"""S38 — model families 2: local registry tests + generation-ladder fakes.

Registry unit tests pin the S37 recipe data (phi-4 + gemma-3 + llama), the
repo-key tag matching and the stable preference sort. The ladder fakes then
prove `generation.client` walks installed Ollama models in registry order
and that an explicit GENERATION_LOCAL_MODELS setting still overrides it.
No network, no keys — same hermetic rules as the S9 suite.
"""

import json

import pytest

import config
import generation.client as gc
from generation.local_registry import (
    LOCAL_MODEL_REGISTRY,
    LocalModelRecipe,
    ordered_tags,
    prefer_order,
    recipe_for,
)

EXPECTED_TAGS = ["llama3.2:1b", "phi4-mini", "gemma3:4b"]


# --- registry data ---------------------------------------------------------

def test_registry_lists_the_three_families_in_ladder_order():
    assert ordered_tags() == EXPECTED_TAGS


def test_recipes_are_complete_and_pullable():
    for recipe in LOCAL_MODEL_REGISTRY:
        assert isinstance(recipe, LocalModelRecipe)
        assert recipe.tag and recipe.family and recipe.note
        assert recipe.approx_gb > 0
        # recipe.tag is literally the `ollama pull` target
        assert recipe.tag == recipe.tag.strip().lower()
        assert recipe.tag in ("llama3.2:1b", "phi4-mini", "gemma3:4b")


def test_new_families_cover_phi4_and_gemma3():
    phi = recipe_for("phi4-mini")
    gemma = recipe_for("gemma3:4b")
    assert phi is not None and "Phi-4" in phi.family
    assert gemma is not None and "Gemma 3" in gemma.family


# --- tag matching ----------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("phi4-mini", "phi4-mini"),
        ("phi4-mini:latest", "phi4-mini"),
        ("microsoft/phi4-mini:latest", "phi4-mini"),
        ("Gemma3:4b", "gemma3:4b"),          # case-insensitive
        ("  llama3.2:1b:latest  ", "llama3.2:1b"),
    ],
)
def test_recipe_for_matches_by_repo_key(raw, expected):
    recipe = recipe_for(raw)
    assert recipe is not None and recipe.tag == expected


def test_recipe_for_unknown_is_none():
    assert recipe_for("tinyllama:latest") is None
    assert recipe_for("") is None


def test_size_qualifiers_do_not_collide():
    """Regression: llama3.2:1b must not be matched by a llama3.2:3b install.

    The size lives *after* the colon in llama tags, so naive repo-splitting
    would wrongly rank any llama3.2 model as the registry's 1B recipe.
    """
    assert recipe_for("llama3.2:3b") is None
    assert recipe_for("llama3.2:1b:latest").tag == "llama3.2:1b"
    out = prefer_order(["llama3.2:3b", "llama3.2:1b"])
    assert out == ["llama3.2:1b", "llama3.2:3b"]


# --- preference sort -------------------------------------------------------

def test_prefer_order_puts_registry_families_first_in_rank_order():
    installed = ["gemma3:4b", "weird-model", "llama3.2:1b", "phi4-mini:latest"]
    out = prefer_order(installed)
    assert out[:3] == ["llama3.2:1b", "phi4-mini:latest", "gemma3:4b"]
    # unknown models are not dropped; exact installed names are kept so the
    # caller talks to Ollama in the names Ollama knows
    assert "weird-model" in out and "phi4-mini:latest" in out


def test_prefer_order_is_stable_for_unknowns():
    installed = ["z-unknown", "a-unknown", "llama3.2:1b"]
    assert prefer_order(installed) == ["llama3.2:1b", "z-unknown", "a-unknown"]


def test_prefer_order_empty_and_all_unknown():
    assert prefer_order([]) == []
    all_unknown = ["tinyllama", "mistral"]
    assert prefer_order(all_unknown) == all_unknown


# --- ladder integration (faked, hermetic) -----------------------------------

def test_ladder_picks_installed_model_in_registry_order(monkeypatch):
    """Hosted tiers empty; llama3.2:1b fails; ladder must fall to phi4-mini."""
    monkeypatch.setattr(gc, "_get_anthropic_client", lambda: None)
    monkeypatch.setattr(gc, "_get_openai_client", lambda: None)
    monkeypatch.setattr(gc, "_ollama_available", lambda: True)

    # /api/tags lists phi4-mini BEFORE llama3.2:1b on purpose — the registry
    # must still walk llama first.
    asked = []

    def fake_http(path, payload=None, timeout=5.0):
        if path == "/api/tags":
            return {"models": [{"name": "gemma3:4b"}, {"name": "phi4-mini"}, {"name": "llama3.2:1b"}]}
        asked.append(payload["model"])
        if payload["model"] == "llama3.2:1b":
            return {"message": {"content": ""}}  # empty -> counted as failure
        return {"message": {"content": json.dumps({"via": "ollama", "model": payload["model"]})}}

    monkeypatch.setattr(gc, "_ollama_http", fake_http)
    out = gc.call_json_tool("s", "u", "make_json", {"type": "object"})
    assert asked == ["llama3.2:1b", "phi4-mini"]  # registry order, llama first
    assert out == {"via": "ollama", "model": "phi4-mini"}


def test_ladder_no_models_hint_names_registry_families(monkeypatch):
    monkeypatch.setattr(gc, "_get_anthropic_client", lambda: None)
    monkeypatch.setattr(gc, "_get_openai_client", lambda: None)
    monkeypatch.setattr(gc, "_ollama_available", lambda: True)
    monkeypatch.setattr(gc, "_ollama_http", lambda path, payload=None, timeout=5.0: {"models": []})
    with pytest.raises(RuntimeError) as exc:
        gc.call_json_tool("s", "u", "make_json", {})
    msg = str(exc.value)
    for tag in EXPECTED_TAGS:
        assert f"ollama pull {tag}" in msg


def test_no_backend_message_lists_registry_families(monkeypatch):
    monkeypatch.setattr(gc, "_get_anthropic_client", lambda: None)
    monkeypatch.setattr(gc, "_get_openai_client", lambda: None)
    monkeypatch.setattr(gc, "_ollama_available", lambda: False)
    with pytest.raises(RuntimeError) as exc:
        gc.call_json_tool("s", "u", "make_json", {})
    msg = str(exc.value)
    assert "No generator backend available" in msg
    for tag in EXPECTED_TAGS:
        assert f"ollama pull {tag}" in msg


def test_explicit_config_still_overrides_registry(monkeypatch):
    """S9 contract preserved: GENERATION_LOCAL_MODELS wins, unsorted."""
    monkeypatch.setattr(config.settings, "generation_local_models", "gemma3:4b,llama3.2:1b")
    monkeypatch.setattr(gc, "_ollama_http", lambda *a, **k: {"models": []})  # must not be consulted
    assert gc._ollama_local_models() == ["gemma3:4b", "llama3.2:1b"]
