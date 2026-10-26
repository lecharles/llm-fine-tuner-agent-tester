"""S33 (#35) regressions: advanced hyperparameters on the training config.

Covers the three backend touchpoints: the mlx_lm.lora command actually carries
--lora-rank/--lora-alpha, the create schema bounds-checks them (plus the
newly guarded iters/learning_rate), and the run row persists them with the
mlx defaults (8/16) when a caller never touched the panel.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from training.runner import build_lora_command
from schemas.training_run import TrainingRunCreate


def _flags(cmd: list[str], flag: str) -> str:
    return cmd[cmd.index(flag) + 1]


def test_command_carries_rank_and_alpha():
    cmd = build_lora_command(
        "some/base", Path("/tmp/data"), Path("/tmp/adapter"),
        iters=50, learning_rate=0.0001, lora_rank=4, lora_alpha=32,
    )
    assert _flags(cmd, "--lora-rank") == "4"
    assert _flags(cmd, "--lora-alpha") == "32"
    assert _flags(cmd, "--learning-rate") == "0.0001"


def test_command_defaults_match_mlx():
    cmd = build_lora_command(
        "some/base", Path("/tmp/data"), Path("/tmp/adapter"),
        iters=300, learning_rate=None,
    )
    assert _flags(cmd, "--lora-rank") == "8"
    assert _flags(cmd, "--lora-alpha") == "16"
    assert "--learning-rate" not in cmd


@pytest.mark.parametrize(
    "field,value",
    [
        ("lora_rank", 0),
        ("lora_rank", 129),
        ("lora_alpha", 0),
        ("lora_alpha", 257),
        ("iters", 0),
        ("iters", 5001),
        ("learning_rate", 0),
        ("learning_rate", -1),
        ("learning_rate", 2),
    ],
)
def test_out_of_range_values_rejected(field, value):
    with pytest.raises(ValidationError):
        TrainingRunCreate(dataset_id=1, **{field: value})


def test_sane_values_accepted():
    run_in = TrainingRunCreate(dataset_id=1, lora_rank=64, lora_alpha=128,
                               iters=400, learning_rate=0.00002)
    assert (run_in.lora_rank, run_in.lora_alpha) == (64, 128)


def test_run_row_persists_with_defaults(in_memory_db):
    from models.training_run import TrainingRun

    run = TrainingRun(user_id=1, dataset_id=1, base_model="Llama-3.2-1B",
                      method="qlora", iters=20, status="queued")
    in_memory_db.add(run)
    in_memory_db.commit()
    in_memory_db.refresh(run)
    assert run.lora_rank == 8
    assert run.lora_alpha == 16
