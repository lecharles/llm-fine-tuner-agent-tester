"""S62 (Model serving 1): Ollama Modelfile generation for fused models.

The serving design comes from docs/RESEARCH_MLX.md §5: ship one self-
contained GGUF per fused model and import it with

    ollama create <tag> -f Modelfile

The GGUF carries its own chat template and tokenizer metadata (llama.cpp's
convert_hf_to_gguf writes them in), so the Modelffile we generate stays
minimal: FROM [+ QUANTIZE] [+ NOTES]. No TEMPLATE/SYSTEM directives —
repeating what the GGUF already declares is how drift bugs are born.

Kept pure-stdlib on purpose: this module is imported by the backend router,
by the pytest suite, and by `llmtuner serve` in the CLI. No torch, no mlx.
"""

import re
import unicodedata
from pathlib import Path

OLLAMA_TAG_PREFIX = "ft-"

# Directives we accept when validating a generated Modelfile. The set mirrors
# ollama's own parser (Modelfile grammar, upper-case keywords); a file with
# anything else fails at `ollama create` time, so we fail it first — with a
# better message.
KNOWN_DIRECTIVES = {
    "FROM", "TEMPLATE", "SYSTEM", "LICENSE", "ADAPTER", "PARAMETER",
    "QUANTIZE", "NOTES",
}

# llama.cpp quantization types ollama's QUANTIZE accepts (upper-case form).
KNOWN_QUANTIZATIONS = {
    "Q2_K", "Q3_K_S", "Q3_K_M", "Q3_K_L", "Q4_K_S", "Q4_K_M",
    "Q5_K_S", "Q5_K_M", "Q6_K", "Q8_0", "F16",
}

# What RESEARCH_MLX §4/§5 prescribes when a fused dir has no GGUF yet: the
# export step today writes MLX safetensors (see training/export.py), so the
# conversion is a manual/spike step until it lands in the job runner.
NO_GGUF_HINT = (
    "Ollama imports GGUF, and this model's fused dir holds MLX safetensors "
    "today (see training/export.py). Convert once — "
    "`python convert_hf_to_gguf.py <fused-dir> --outfile model-f16.gguf "
    "--outtype f16` per docs/RESEARCH_MLX.md §4 — drop the .gguf into the "
    "fused dir (or pass --path) and re-run."
)


def ollama_tag(name: str) -> str:
    """Slugify a display name into a valid Ollama model tag.

    Ollama tags are lowercase and may contain letters, digits, '.' and '-'.
    Accented names are transliterated first (NFKD, combining marks dropped)
    so "Café 3B" becomes the useful "cafe-3b", not the lossy "caf-3b".
    We prefix 'ft-' so imported fine-tunes are never confusable with a base
    model pulled from the registry, and never double-prefix an id that
    already starts with the marker (runner names rows '<base>-ft-<id>').
    """
    decomposed = unicodedata.normalize("NFKD", name or "")
    ascii_name = decomposed.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9.]+", "-", ascii_name.lower()).strip("-.")
    if not slug:
        slug = "model"
    if slug == OLLAMA_TAG_PREFIX.rstrip("-") or slug.startswith(OLLAMA_TAG_PREFIX):
        return slug
    return OLLAMA_TAG_PREFIX + slug


def find_gguf(path: str | Path) -> Path | None:
    """Resolve a model path to the GGUF file Ollama should import.

    Accepts either the .gguf file itself or a directory (a fused dir); in the
    directory case we pick a .gguf from it, preferring an f16 variant because
    that is what §4's prescribed conversion produces (quantizing later, at
    import time, is cheaper than re-converting). Returns None when no GGUF is
    reachable — the caller then explains the conversion step instead of
    writing a Modelfile whose FROM would fail.
    """
    p = Path(path)
    if p.is_file() and p.suffix.lower() == ".gguf":
        return p
    if p.is_dir():
        candidates = sorted(p.glob("*.gguf"))
        if not candidates:
            return None
        f16 = [c for c in candidates if "f16" in c.name.lower()]
        return (f16 or candidates)[0]
    return None


def build_modelfile(
    gguf_path: str | Path,
    quantize: str | None = None,
    notes: str | None = None,
) -> str:
    """Render Modelfile content. FROM first (ollama requires it before the
    model can be created), then an optional QUANTIZE (import-time shrink:
    q4_K_M takes a 1B f16 well under 1 GB, RESEARCH_MLX §5), then one
    single-line NOTES for provenance. Trailing newline mirrors write_jsonl."""
    lines = [f"FROM {Path(gguf_path)}"]
    if quantize:
        lines.append(f"QUANTIZE {quantize.strip().upper()}")
    if notes:
        # single-line NOTES: no triple-quote blocks, nothing to escape wrong
        lines.append(f"NOTES {' '.join(str(notes).split())}")
    return "\n".join(lines) + "\n"


def validate_modelfile(text: str, base_dir: str | Path | None = None) -> list[str]:
    """Offline import smoke — mirror the checks `ollama create` performs,
    so the CLI and tests can prove the file is importable without running
    Ollama (the VPS has none; the Mac run is the real one, S70).

    Returns a list of human-readable problems; empty means good. When
    base_dir is given, a relative FROM is resolved against it and must
    exist (this is exactly the failure mode of a stale fused dir).
    """
    errors: list[str] = []
    seen_from = False
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        head, _, rest = line.partition(" ")
        command = head.upper()
        value = rest.strip()
        if command not in KNOWN_DIRECTIVES:
            errors.append(
                f"line {number}: unknown directive {command!r} "
                "(ollama will reject this Modelfile)"
            )
            continue
        if command == "FROM":
            if seen_from:
                errors.append(f"line {number}: second FROM directive")
            seen_from = True
            if not value:
                errors.append(f"line {number}: FROM with no path")
            elif base_dir is not None:
                candidate = Path(value)
                if not candidate.is_absolute():
                    candidate = Path(base_dir) / candidate
                if not candidate.exists():
                    errors.append(
                        f"line {number}: FROM path does not exist: {value}"
                    )
        elif command == "QUANTIZE":
            if value.upper() not in KNOWN_QUANTIZATIONS:
                errors.append(
                    f"line {number}: QUANTIZE {value!r} is not a known "
                    f"type (try {'/'.join(sorted(KNOWN_QUANTIZATIONS))})"
                )
    if not seen_from:
        errors.append("Modelfile has no FROM directive")
    return errors
