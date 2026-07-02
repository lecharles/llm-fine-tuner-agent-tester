"""Run a QLoRA fine-tune as a background job and track it on the training_runs row.

The heavy lifting is done by mlx-lm's `mlx_lm.lora` command, invoked as a
subprocess so a crash or out-of-memory takes down a child process, not the API
worker. The job walks training_runs.status through queued -> running ->
completed or failed, and writes the adapter plus a log into a per-run workspace.

Flag reference: mlx-lm LoRA docs (see docs/RESEARCH_MLX.md).
"""

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from database import SessionLocal
from models.qa_pair import QAPair
from models.training_run import TrainingRun
from training.data import build_training_files

BATCH_SIZE = 4
TRAINING_ROOT = Path(__file__).resolve().parent.parent / "_training_runs"


def run_dir_for(run_id: int) -> Path:
    """Per-run workspace: data/, adapters/, and the training log all live here."""
    return TRAINING_ROOT / str(run_id)


def build_lora_command(
    base_model: str,
    data_dir: Path,
    adapter_dir: Path,
    iters: int,
    learning_rate,
) -> list[str]:
    """Assemble the mlx_lm.lora argument list. A 4-bit base_model makes this QLoRA
    automatically; --mask-prompt trains on the answer, not the question."""
    command = [
        "mlx_lm.lora",
        "--model", base_model,
        "--train",
        "--data", str(data_dir),
        "--adapter-path", str(adapter_dir),
        "--iters", str(iters),
        "--batch-size", str(BATCH_SIZE),
        "--mask-prompt",
    ]
    if learning_rate is not None:
        command += ["--learning-rate", str(learning_rate)]
    return command


def run_training(run_id: int) -> None:
    """Background entry point. Opens its own DB session (the request's session is
    already closed by the time this runs), converts the dataset to JSONL, runs the
    training subprocess, and records the outcome on the run."""
    db = SessionLocal()
    try:
        run = db.query(TrainingRun).filter(TrainingRun.id == run_id).first()
        if run is None:
            return

        run.status = "running"
        db.commit()

        workspace = run_dir_for(run_id)
        data_dir = workspace / "data"
        adapter_dir = workspace / "adapters"
        adapter_dir.mkdir(parents=True, exist_ok=True)

        pairs = db.query(QAPair).filter(QAPair.dataset_id == run.dataset_id).all()
        build_training_files(pairs, data_dir)

        command = build_lora_command(
            run.base_model, data_dir, adapter_dir, run.iters, run.learning_rate
        )

        result = subprocess.run(command, capture_output=True, text=True)
        (workspace / "train.log").write_text(
            result.stdout + "\n" + result.stderr, encoding="utf-8"
        )
        if result.returncode != 0:
            raise RuntimeError(f"mlx_lm.lora exited with code {result.returncode}")

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        run = db.query(TrainingRun).filter(TrainingRun.id == run_id).first()
        if run is not None:
            run.status = "failed"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()