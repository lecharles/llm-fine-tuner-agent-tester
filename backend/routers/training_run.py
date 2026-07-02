from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.dataset import Dataset
from models.qa_pair import QAPair
from models.training_run import TrainingRun
from models.user import User
from schemas.training_run import TrainingRunCreate, TrainingRunOut
from core.security import get_current_user
from training.runner import run_training

router = APIRouter(prefix="/api/training-runs", tags=["training-runs"])


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

    run = TrainingRun(
        user_id=current_user.id,
        dataset_id=run_in.dataset_id,
        base_model=run_in.base_model,
        method=run_in.method,
        iters=run_in.iters,
        learning_rate=run_in.learning_rate,
        status="queued",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(run_training, run.id)
    return run


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
    return runs


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
    return run