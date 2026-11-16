from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.dataset import Dataset
from models.qa_pair import QAPair
from models.training_run import TrainingRun
from models.user import User
from schemas.training_run import (
    ErrorExplanationOut,
    LossPoint,
    TrainingRunCreate,
    TrainingRunHistoryOut,
    TrainingRunOut,
)
from core.security import get_current_user
from training.explainer import explain_error
from training.losses import read_losses
from training.preflight import mlx_training_available
from training.runner import run_training

router = APIRouter(prefix="/api/training-runs", tags=["training-runs"])

# S59: the train queue serializes per user. A run is "active" while it is
# queued or running; a second start for the same user answers 409 instead of
# launching a concurrent mlx_lm.lora that would fight the first for the GPU.
ACTIVE_STATUSES = ("queued", "running")


def _blocking_run(db: Session, user_id: int) -> TrainingRun | None:
    """The user's oldest active run, if any — the one a new POST collides with."""
    return (
        db.query(TrainingRun)
        .filter(TrainingRun.user_id == user_id, TrainingRun.status.in_(ACTIVE_STATUSES))
        .order_by(TrainingRun.created_at, TrainingRun.id)
        .first()
    )


def _queue_positions(db: Session) -> dict[int, int]:
    """run id -> 1-based FIFO position over ALL active runs (queued or running),
    ordered by creation. Computed per request from the active set, which is a
    handful of rows at this scale — no column, no migration."""
    rows = (
        db.query(TrainingRun.id)
        .filter(TrainingRun.status.in_(ACTIVE_STATUSES))
        .order_by(TrainingRun.created_at, TrainingRun.id)
        .all()
    )
    return {row[0]: i + 1 for i, row in enumerate(rows)}


def _run_out(run: TrainingRun, positions: dict[int, int]) -> TrainingRunOut:
    out = TrainingRunOut.model_validate(run)
    # Only a waiting run has a queue position; running/terminal rows report
    # None so clients never render a stale spot in line.
    if run.status == "queued":
        out.queue_position = positions.get(run.id)
    return out


@router.post("", response_model=TrainingRunOut, status_code=status.HTTP_201_CREATED)
def start_training_run(
    run_in: TrainingRunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == run_in.dataset_id, Dataset.user_id == current_user.id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    pair_count = db.query(QAPair).filter(QAPair.dataset_id == dataset.id).count()
    if pair_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dataset has no QA pairs to train on",
        )

    # 425 preflight (#42): on a non-Mac backend training can never succeed, so
    # answer plainly instead of queueing a doomed run.
    ok, reason = mlx_training_available()
    if not ok:
        raise HTTPException(status_code=425, detail=reason)

    # S59: one active run per user — serialize instead of oversubscribing
    # the single MLX engine. The client can poll that run for status.
    blocker = _blocking_run(db, current_user.id)
    if blocker is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A training run is already in progress (run {blocker.id}, "
                f"status {blocker.status}). Runs are serialized per user — "
                "wait for it to finish, then start another."
            ),
        )

    run = TrainingRun(
        user_id=current_user.id,
        dataset_id=run_in.dataset_id,
        base_model=run_in.base_model,
        method=run_in.method,
        iters=run_in.iters,
        learning_rate=run_in.learning_rate,
        lora_rank=run_in.lora_rank,
        lora_alpha=run_in.lora_alpha,
        status="queued",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(run_training, run.id)
    return _run_out(run, _queue_positions(db))


@router.get("", response_model=list[TrainingRunOut])
def list_training_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    runs = (
        db.query(TrainingRun)
        .filter(TrainingRun.user_id == current_user.id)
        .order_by(TrainingRun.created_at.desc())
        .all()
    )
    # S59: one position pass over the active set, then stamp each row.
    positions = _queue_positions(db)
    return [_run_out(run, positions) for run in runs]


@router.get("/history", response_model=list[TrainingRunHistoryOut])
def list_run_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # S35 (#36): run history 1. Declared BEFORE /{run_id} so "history" is not
    # swallowed by the int path param (which would 422 instead of matching).
    # One row per run, newest first, owner-scoped — the history page's data.
    rows = (
        db.query(TrainingRun, Dataset.name)
        .outerjoin(Dataset, Dataset.id == TrainingRun.dataset_id)
        .filter(TrainingRun.user_id == current_user.id)
        .order_by(TrainingRun.created_at.desc(), TrainingRun.id.desc())
        .all()
    )
    history = []
    for run, dataset_name in rows:
        # Final loss = last parsed point of the run's train.log (S11 parser).
        # Queued/running runs with no log yet report None, not 0.
        points = read_losses(run.id)
        history.append(
            TrainingRunHistoryOut(
                id=run.id,
                dataset_id=run.dataset_id,
                dataset_name=dataset_name or "(deleted dataset)",
                base_model=run.base_model,
                method=run.method,
                iters=run.iters,
                status=run.status,
                final_loss=points[-1]["loss"] if points else None,
                created_at=run.created_at,
                completed_at=run.completed_at,
            )
        )
    return history


@router.get("/{run_id}", response_model=TrainingRunOut)
def read_training_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = (
        db.query(TrainingRun)
        .filter(TrainingRun.id == run_id, TrainingRun.user_id == current_user.id)
        .first()
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training run not found")
    return _run_out(run, _queue_positions(db))


@router.get("/{run_id}/losses", response_model=list[LossPoint])
def read_run_losses(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # S11 (issue #4): live loss curve. The Train page polls this every few
    # seconds; train.log is streamed by the runner, so points appear while
    # the run is still going. No log yet (queued/older runs) -> empty list.
    run = (
        db.query(TrainingRun)
        .filter(TrainingRun.id == run_id, TrainingRun.user_id == current_user.id)
        .first()
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training run not found")
    return read_losses(run.id)


@router.get("/{run_id}/explain", response_model=list[ErrorExplanationOut])
def read_run_explain(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # S29 (issue #33): map the failed run's persisted error text (#42/#46) to
    # human cause + fix entries. Empty list while a run never failed; generic
    # fallback for unrecognized strings — the UI always gets something back.
    run = (
        db.query(TrainingRun)
        .filter(TrainingRun.id == run_id, TrainingRun.user_id == current_user.id)
        .first()
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training run not found")
    return [e.as_dict() for e in explain_error(run.error_message or "")]