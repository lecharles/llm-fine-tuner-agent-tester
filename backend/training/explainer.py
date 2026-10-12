"""Training error explainer (S29, issue #33).

Runs persist raw failure text (#42/#46): exception + traceback + train.log /
fuse.log tails. That is honest but unreadable for a non-engineer. This module
maps the *common* MLX / Ollama / QLoRA failure strings we have actually seen
(plus their well-known variants) to a human cause and a concrete fix, so the
API and the Train page can show "what this probably means" under a failed run.

Deterministic on purpose: substring/keyword rules, no LLM call, no network.
Rules are matched case-insensitively against the whole error blob; the first
match wins per rule and rules are evaluated in priority order (most specific
first). When nothing matches, one generic fallback entry is returned so the
UI always has something to say.
"""

from __future__ import annotations


class ErrorExplanation:
    """One human-readable reading of a failure: title + cause + fix."""

    def __init__(self, title: str, cause: str, fix: str) -> None:
        self.title = title
        self.cause = cause
        self.fix = fix

    def as_dict(self) -> dict[str, str]:
        return {"title": self.title, "cause": self.cause, "fix": self.fix}


# (patterns, title, cause, fix) — patterns are substrings matched against the
# lowercased error blob. Ordered: specific -> broad.
_RULES: list[tuple[tuple, str, str, str]] = [
    (
        ("training runs on the mac app only",),
        "Wrong machine: MLX only runs on Apple Silicon",
        "This backend is not a Mac, so the training engine (MLX) is unavailable here — the run was blocked on purpose.",
        "Start training from the desktop app on the Mac (llmtuner up on the Mac, or the LLM Tuner bundle), or wait for the Phase 6 local companion.",
    ),
    (
        ("the mlx-lm package is not installed", "mlx_lm not found", "no module named 'mlx", "mlx_lm.lora: command not found", "mlx_lm.fuse: command not found"),
        "MLX is missing from this environment",
        "The backend's Python environment has no mlx-lm, so train/fuse commands die immediately.",
        "In the Mac app venv run: pip install mlx-lm  — then retry. (The new install/macos.sh does this for you.)",
    ),
    (
        ("out of memory", "bad_alloc", "cannot allocate", "insufficient memory", "memory capacity", "kmetalcommandbuffer", "exit code 137", "killed"),
        "Not enough memory (OOM)",
        "The model + batch did not fit in Apple Silicon unified memory (or the OS killed the worker at 137).",
        "Pick a smaller 4-bit base model (start with the 1B), close browser tabs / memory-heavy apps, and retry. Do not raise batch size on smaller Macs.",
    ),
    (
        ("no space left on device", "disk full"),
        "Disk is full",
        "Training needs room for the downloaded base weights, the adapter, and the fused model.",
        "Free space on the Mac (the fused bf16 export is the big one — a 1B model needs roughly 2-3 GB around the run), then retry.",
    ),
    (
        ("repository not found", "entrynotfound", "entry not found", "gated repo", "401 client error", "403 client error", "hf auth", "restricted by their authors"),
        "Base model id is wrong or gated on Hugging Face",
        "The base_model string could not be downloaded: either the repo id is misspelled or the model is gated and needs access.",
        "Use a public mlx-community 4-bit id (e.g. mlx-community/Llama-3.2-1B-Instruct-4bit). For gated models accept the license on huggingface.co and run: hf auth login",
    ),
    (
        ("max retries exceeded", "temporary failure in name resolution", "could not connect to host", "ssl error", "network is unreachable"),
        "Network hiccup while fetching the base model",
        "Weights could not be downloaded (offline, DNS, proxy, or TLS). Partial downloads are retried automatically by HF on the next run.",
        "Check the Mac's internet connection (and VPN/proxy), then just start the run again — cached shards are reused.",
    ),
    (
        ("failed to load the configuration", "couldn't connect to hub", "can't load the model"),
        "Base model download/corrupt cache",
        "Hugging Face could not load the base model's files — usually a corrupted download cache.",
        "Re-run once; if it repeats, clear the partial cache: huggingface-cli delete-cache — then retry.",
    ),
    (
        ("11434", "connection refused", "couldn't connect to ollama server", "failed to connect to ollama", "try pulling first"),
        "Ollama is not up or lacks the model",
        "A step needed the local Ollama server (port 11434) but could not reach it, or asked for a model that was never pulled.",
        "Start Ollama (the Mac app, or `ollama serve`) and pull the model it asks for, e.g.: ollama pull llama3.2:1b",
    ),
    (
        ("zero division", "train.jsonl", "no training data", "dataset has no qa pairs"),
        "Dataset had nothing to train on",
        "The converted training files were empty (the dataset lost its QA pairs between start and build).",
        "Add QA pairs to the dataset (or import a CSV/JSONL) and start a fresh run.",
    ),
    (
        ("mlx_lm.fuse exited with code", "no fused model weights"),
        "Training worked; the fuse/export step failed",
        "The LoRA adapter finished but mlx_lm.fuse could not merge it into the base (see the fuse.log tail above for the exact reason).",
        "Most often memory or disk during export: close apps, keep a smaller 4-bit base, and re-run. If train.log showed clean losses but fuse keeps failing, capture both logs (scripts/collect-run-logs.sh) for #46.",
    ),
    (
        ("mlx_lm.lora exited with code",),
        "The trainer crashed partway",
        "mlx_lm.lora died with a non-zero exit before finishing; the train.log tail above is the last thing it said.",
        "Read the log tail for the first real error line, fix it (memory/model/data), and start a fresh run — adapters are per-run, nothing to clean up.",
    ),
]

_GENERIC = ErrorExplanation(
    "Unclassified failure",
    "We do not have a ready-made explanation for this error string yet.",
    "Open the raw text above and find the first 'Error'/'Traceback' line — that is usually the real cause. Copy it to issue #33 and the lane will teach the explainer this case.",
)


def explain_error(text: str) -> list[ErrorExplanation]:
    """Return every rule that matches `text` (priority order), or the generic
    fallback when nothing matches. Never raises on odd input."""
    if not text or not text.strip():
        return []
    blob = text.lower()
    matches: list[ErrorExplanation] = []
    for patterns, title, cause, fix in _RULES:
        for pat in patterns:
            if pat in blob:
                matches.append(ErrorExplanation(title, cause, fix))
                break  # one hit per rule is enough
    return matches if matches else [_GENERIC]
