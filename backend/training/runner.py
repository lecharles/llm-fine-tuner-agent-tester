"""Run a QLoRA fine-tune as a background job and track it on the training_runs row.

The heavy lifting is done by mlx-lm's `mlx_lm.lora` command, invoked as a
subprocess so a crash or out-of-memory takes down a child process, not the API
worker. The job walks training_runs.status through queued -> running ->
completed or failed, and writes the adapter plus a log into a per-run workspace.

Flag reference: mlx-lm LoRA docs (see docs/RESEARCH_MLX.md).
"""

import subprocess
import traceback
from datetime import datetime, timezone
from pathlib import Path

from database import SessionLocal
from models.fine_tuned_model import FineTunedModel
from models.qa_pair import QAPair
from models.training_run import TrainingRun
from training.data import build_training_files
from training.export import export_gguf
from training.preflight import mlx_training_available


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


def tail_text(path: Path, limit: int = 1800) -> str:
    """Last `limit` characters of a log file; '' when the file never appeared."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-limit:]
    except OSError:
        return ""


def stream_train_log(command: list[str], log_path: Path) -> int:
    """Run `command`, appending its merged stdout+stderr to `log_path` as
    lines arrive. Returns the exit code. Line-by-line flushing is what makes
    the loss curve live (S11, issue #4): GET /losses parses this file while
    the subprocess is still running.
    """
    with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            log_file.write(line)
            log_file.flush()
        return proc.wait()


def run_training(run_id: int) -> None:
    """Background entry point. Opens its own DB session (the request's session is
    already closed by the time this runs), converts the dataset to JSONL, runs the
    training subprocess, and records the outcome on the run.
    """
    db = SessionLocal()
    try:
        run = db.query(TrainingRun).filter(TrainingRun.id == run_id).first()
        if run is None:
            return

        run.status = "running"
        run.error_message = None  # stale errors from a retried run must not linger
        db.commit()

        # Safety net behind the router's 425 preflight: if the run was created
        # before we shipped the check (or the platform lied), fail with words.
        ok, reason = mlx_training_available()
        if not ok:
            raise RuntimeError(reason)

        workspace = run_dir_for(run_id)
        data_dir = workspace / "data"
        adapter_dir = workspace / "adapters"
        adapter_dir.mkdir(parents=True, exist_ok=True)

        pairs = db.query(QAPair).filter(QAPair.dataset_id == run.dataset_id).all()
        build_training_files(pairs, data_dir)

        command = build_lora_command(
            run.base_model, data_dir, adapter_dir, run.iters, run.learning_rate
        )

        # S11 (issue #4): stream stdout+stderr into train.log line by line
        # instead of capturing and writing at the end, so the losses endpoint
        # can chart the run *live*. The merged stream lands in the same file
        # the failure path already tails, so error reporting is unchanged.
        returncode = stream_train_log(command, workspace / "train.log")
        if returncode != 0:
            raise RuntimeError(f"mlx_lm.lora exited with code {returncode}")
        
        fused_dir = workspace / "fused_model"
        export_result = export_gguf(run.base_model, adapter_dir, fused_dir)

        model = FineTunedModel(
            user_id=run.user_id,
            training_run_id=run.id,
            name=f"{run.base_model.split('/')[-1]}-ft-{run.id}",
            base_model=run.base_model,
            gguf_path=export_result["gguf_path"],
            size_mb=export_result["size_mb"],
            status="ready",
        )
        db.add(model)

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        # #42: this used to be a bare `except Exception:` that swallowed the
        # reason. Persist exception text + traceback + log tail on the run so
        # the API and Train UI can show why it died.
        db.rollback()
        run = db.query(TrainingRun).filter(TrainingRun.id == run_id).first()
        if run is not None:
            tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
            detail = f"{type(exc).__name__}: {exc}"
            if tb:
                detail += "\n" + "".join(tb).strip()[-1500:]
            log_tail = tail_text(run_dir_for(run_id) / "train.log")
            if log_tail.strip():
                detail += "\n--- train.log tail ---\n" + log_tail
            # #46: a fuse-stage failure writes its real reason to fused_model/
            # fuse.log, not train.log. Surface both so the export step self-
            # diagnoses instead of showing only "exited with code 1".
            fuse_tail = tail_text(run_dir_for(run_id) / "fused_model" / "fuse.log")
            if fuse_tail.strip():
                detail += "\n--- fuse.log tail ---\n" + fuse_tail
            run.status = "failed"
            run.error_message = detail[-6000:]
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()