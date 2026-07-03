"""Fuse a trained adapter into its base model and export a GGUF for Ollama.

The adapter is trained against a 4-bit (QLoRA) base, but GGUF export is clean only
from a full-precision base, so we fuse onto the bf16 twin of the training model.
This is the workaround the spike settled on (see docs/RESEARCH_MLX.md); it sidesteps
the tensor-dtype errors that hit when exporting GGUF straight from a quantized base.
"""

import subprocess
from pathlib import Path

FUSE_BASE = {
    "mlx-community/Llama-3.2-1B-Instruct-4bit": "mlx-community/Llama-3.2-1B-Instruct-bf16",
    "mlx-community/Llama-3.2-3B-Instruct-4bit": "mlx-community/Llama-3.2-3B-Instruct-bf16",
}


def fuse_base_for(base_model: str) -> str:
    """Map the 4-bit training model to its bf16 twin for fusing. Falls back to the
    given model if it is already full precision or not in the map."""
    return FUSE_BASE.get(base_model, base_model)


def build_fuse_command(fuse_base: str, adapter_dir: Path, fused_dir: Path) -> list[str]:
    """mlx_lm.fuse merges the adapter into the base and writes a fused model (safetensors)
    to the save path. We deliberately skip --export-gguf: that flag hits an mlx-lm
    serialization bug (see docs/RESEARCH_MLX.md), and GGUF conversion moves to Phase 4."""
    return [
        "mlx_lm.fuse",
        "--model", fuse_base,
        "--adapter-path", str(adapter_dir),
        "--save-path", str(fused_dir),
    ]


def export_gguf(base_model: str, adapter_dir: Path, fused_dir: Path) -> dict:
    """Fuse the adapter onto the full-precision base into a fused model directory. Returns
    its path and size in MB for the fine_tuned_models row (stored in gguf_path for now; real
    GGUF conversion is Phase 4). Raises on failure so the caller marks the run failed."""
    fused_dir = Path(fused_dir)
    fused_dir.mkdir(parents=True, exist_ok=True)

    command = build_fuse_command(fuse_base_for(base_model), adapter_dir, fused_dir)
    result = subprocess.run(command, capture_output=True, text=True)
    (fused_dir / "fuse.log").write_text(
        result.stdout + "\n" + result.stderr, encoding="utf-8"
    )
    if result.returncode != 0:
        raise RuntimeError(f"mlx_lm.fuse exited with code {result.returncode}")

    weights = sorted(fused_dir.glob("*.safetensors"))
    if not weights:
        raise RuntimeError(f"No fused model weights in {fused_dir}")

    size_mb = int(sum(w.stat().st_size for w in weights) / (1024 * 1024))
    return {"gguf_path": str(fused_dir), "size_mb": size_mb}