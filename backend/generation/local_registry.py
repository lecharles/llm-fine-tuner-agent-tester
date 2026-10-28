"""Local (Ollama) model-family registry: known recipes + ladder preference.

The last tier of the generation fallback ladder walks whatever Ollama has
installed. This registry names the families we support locally — Llama 3.2,
Phi-4, Gemma 3 — with the pull recipe and approximate size for each, and
gives the ladder a deterministic preference order among installed models:

    llama3.2:1b  ->  phi4-mini  ->  gemma3:4b  ->  (anything else, installed order)

Unknown models are never dropped; they keep their `/api/tags` order after the
known ones (that is issue #3's real complaint). An explicit
GENERATION_LOCAL_MODELS setting still wins over everything (S9 behaviour).

Model IDs and prompting strategy for the hosted tiers: docs/RESEARCH_DATASETS.md.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LocalModelRecipe:
    tag: str          # ollama tag; `ollama pull <tag>` gets it
    family: str       # human label
    approx_gb: float  # download size of the default quantisation, approximate
    note: str         # why it is in the ladder / where it shines


# Preference order == the order the fallback ladder tries these models.
LOCAL_MODEL_REGISTRY: tuple[LocalModelRecipe, ...] = (
    LocalModelRecipe(
        tag="llama3.2:1b",
        family="Meta Llama 3.2 (1B)",
        approx_gb=1.3,
        note="VPS default since S3; smallest + fastest, good JSON-schema adherence for its size.",
    ),
    LocalModelRecipe(
        tag="phi4-mini",
        family="Microsoft Phi-4 mini (3.8B)",
        approx_gb=2.5,
        note="Stronger reasoning than the 1B Llama at still-modest size; `ollama pull phi4-mini`.",
    ),
    LocalModelRecipe(
        tag="gemma3:4b",
        family="Google Gemma 3 (4B)",
        approx_gb=3.3,
        note="Best structured-output quality of the three when the machine can spare the RAM.",
    ),
)


def ordered_tags() -> list[str]:
    """Registry tags in ladder-preference order."""
    return [recipe.tag for recipe in LOCAL_MODEL_REGISTRY]


def _norm(tag: str) -> str:
    """Lower-case, trimmed, org prefix dropped: "microsoft/phi4-mini" -> "phi4-mini"."""
    return tag.strip().lower().split("/", 1)[-1]


def _candidate_keys(tag: str) -> set[str]:
    """Keys an installed model name can match a registry tag by.

    For "phi4-mini:latest" -> {"phi4-mini:latest", "phi4-mini"};
    for "llama3.2:1b:latest" -> {"llama3.2:1b:latest", "llama3.2:1b", "llama3.2"}.
    Registry tags are matched exactly (after _norm), so size-qualified tags
    like llama3.2:1b never collide with llama3.2:3b.
    """
    name = _norm(tag)
    keys = {name, name.split(":", 1)[0]}
    if name.endswith(":latest"):
        keys.add(name[: -len(":latest")])
    return keys


def recipe_for(tag: str) -> LocalModelRecipe | None:
    """Registry entry matching a (possibly qualified) model tag, else None."""
    keys = _candidate_keys(tag)
    for recipe in LOCAL_MODEL_REGISTRY:
        if _norm(recipe.tag) in keys:
            return recipe
    return None


def prefer_order(installed: list[str]) -> list[str]:
    """Stable-sort installed model tags so registry families come first.

    Registry models are ordered by the registry's preference order; every
    unknown model keeps its relative position after them. Tags that match a
    family but carry a different qualifier (e.g. "phi4-mini:latest") are
    matched by repo key but returned unchanged, so callers talk to Ollama in
    exactly the names Ollama knows.
    """
    exact = {_norm(recipe.tag): i for i, recipe in enumerate(LOCAL_MODEL_REGISTRY)}
    unranked = len(exact)

    def rank(tag: str) -> int:
        keys = _candidate_keys(tag)
        for key, i in exact.items():
            if key in keys:
                return i
        return unranked

    return sorted(installed, key=rank)
