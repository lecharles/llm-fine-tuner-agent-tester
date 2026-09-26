"""Parse per-iteration loss out of a run's train.log (S11, issue #4).

The Train page shows a live loss curve by polling
GET /api/training-runs/{id}/losses, which runs `read_losses` over the per-run
workspace log. mlx-lm prints progress lines such as

    Iter 20: Train loss 1.94872, Validation loss 0.00000, Learn rate 0.002, ...

but the exact wording has drifted across mlx-lm versions, so the parser is
deliberately forgiving: an "Iter N + train loss" match wins, standalone
validation-only lines are skipped, and any remaining bare "loss <number>"
line is kept as an ordinal step. Duplicates (tqdm rewrites the same iteration
with \\r, which splitlines treats as new lines) collapse to the last value
seen for each step.
"""

import re
from pathlib import Path

from training.runner import run_dir_for

# "Iter 20: ... Train loss 1.94872" — the number may be int, float, or exp.
_NUM = r"(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
_ITER_TRAIN = re.compile(
    rf"iter(?:ation)?\D{{0,3}}(\d+).*?\btrain(?:ing)?\s*loss[^0-9-]*{_NUM}",
    re.IGNORECASE,
)
# A line that is *only* reporting validation loss must not join the curve.
_VAL_ONLY = re.compile(r"^\s*(?:iter\D{0,3}\d+\s*[:|-]?\s*)?val(?:idation)?\s+loss", re.IGNORECASE)
# Fallback: any "... loss 1.234" / "loss=1.234" mention (e.g. tqdm postfixes).
_BARE_LOSS = re.compile(rf"\bloss[^0-9-]*{_NUM}", re.IGNORECASE)


def parse_loss_lines(text: str) -> list[dict]:
    """Return [{"step": int, "loss": float}, ...] in step order.

    Never raises: unparseable text simply yields fewer (or zero) points.
    """
    by_step: dict[int, float] = {}
    for line in text.splitlines():
        match = _ITER_TRAIN.search(line)
        if match:
            by_step[int(match.group(1))] = float(match.group(2))
            continue
        if _VAL_ONLY.match(line):
            continue
        match = _BARE_LOSS.search(line)
        if match:
            # No iteration marker to trust: number the point by arrival order.
            by_step[len(by_step) + 1] = float(match.group(1))
    return [{"step": step, "loss": loss} for step, loss in sorted(by_step.items())]


def read_losses(run_id: int) -> list[dict]:
    """Parse the run's train.log. Missing/unreadable log -> empty curve."""
    log_path = run_dir_for(run_id) / "train.log"
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return parse_loss_lines(text)
