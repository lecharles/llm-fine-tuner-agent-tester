"""Preflight checks for training runs (#42).

Training uses MLX (Apple Silicon only). On the VPS team instance the engine is
never available, so instead of letting a run go queued -> running -> failed with
no explanation, the start endpoint answers 425 with a plain-language message and
the background job has the same guard as a safety net.
"""

import importlib.util
import platform


def mlx_training_available() -> tuple[bool, str]:
    """Return (ok, reason). When ok is True, reason is empty."""
    if platform.system() != "Darwin":
        return False, (
            "Training runs on the Mac app only: MLX needs Apple Silicon and this "
            f"backend is on {platform.system()}. Run training from the desktop app "
            "on the Mac."
        )
    if importlib.util.find_spec("mlx_lm") is None:
        return False, (
            "The mlx-lm package is not installed in this backend's environment. "
            "Install it in the Mac app venv (pip install mlx-lm) and retry."
        )
    return True, ""
