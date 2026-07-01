from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.dataset import Dataset
from models.user import User
from schemas.dataset import DatasetCreate, DatasetUpdate, DatasetOut
from core.security import get_current_user

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
def create_dataset(
    dataset_in: DatasetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = Dataset(
        user_id=current_user.id,
        name=dataset_in.name,
        description=dataset_in.description,
        source=dataset_in.source,
        use_case_prompt=dataset_in.use_case_prompt,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


@router.get("", response_model=list[DatasetOut])
def list_datasets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    datasets = db.query(Dataset).filter(Dataset.user_id == current_user.id).all()
    return datasets


@router.get("/{dataset_id}", response_model=DatasetOut)
def read_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return dataset


@router.put("/{dataset_id}", response_model=DatasetOut)
def update_dataset(
    dataset_id: int,
    dataset_in: DatasetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    update_data = dataset_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(dataset, field, value)

    db.commit()
    db.refresh(dataset)
    return dataset


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    db.delete(dataset)
    db.commit()
    return None