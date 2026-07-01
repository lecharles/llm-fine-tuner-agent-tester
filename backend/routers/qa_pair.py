from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.dataset import Dataset
from models.qa_pair import QAPair
from models.user import User
from schemas.qa_pair import QAPairCreate, QAPairUpdate, QAPairOut
from core.security import get_current_user

router = APIRouter(prefix="/api/datasets/{dataset_id}/qa-pairs", tags=["qa-pairs"])


def get_owned_dataset(dataset_id: int, db: Session, current_user: User) -> Dataset:
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return dataset


@router.post("", response_model=QAPairOut, status_code=status.HTTP_201_CREATED)
def create_qa_pair(
    dataset_id: int,
    qa_pair_in: QAPairCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_dataset(dataset_id, db, current_user)
    qa_pair = QAPair(
        dataset_id=dataset_id,
        question=qa_pair_in.question,
        answer=qa_pair_in.answer,
    )
    db.add(qa_pair)
    db.commit()
    db.refresh(qa_pair)
    return qa_pair


@router.get("", response_model=list[QAPairOut])
def list_qa_pairs(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_dataset(dataset_id, db, current_user)
    qa_pairs = db.query(QAPair).filter(QAPair.dataset_id == dataset_id).all()
    return qa_pairs


@router.get("/{qa_pair_id}", response_model=QAPairOut)
def read_qa_pair(
    dataset_id: int,
    qa_pair_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_dataset(dataset_id, db, current_user)
    qa_pair = (
        db.query(QAPair)
        .filter(QAPair.id == qa_pair_id, QAPair.dataset_id == dataset_id)
        .first()
    )
    if qa_pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA pair not found")
    return qa_pair


@router.put("/{qa_pair_id}", response_model=QAPairOut)
def update_qa_pair(
    dataset_id: int,
    qa_pair_id: int,
    qa_pair_in: QAPairUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_dataset(dataset_id, db, current_user)
    qa_pair = (
        db.query(QAPair)
        .filter(QAPair.id == qa_pair_id, QAPair.dataset_id == dataset_id)
        .first()
    )
    if qa_pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA pair not found")

    update_data = qa_pair_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(qa_pair, field, value)

    db.commit()
    db.refresh(qa_pair)
    return qa_pair


@router.delete("/{qa_pair_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_qa_pair(
    dataset_id: int,
    qa_pair_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_dataset(dataset_id, db, current_user)
    qa_pair = (
        db.query(QAPair)
        .filter(QAPair.id == qa_pair_id, QAPair.dataset_id == dataset_id)
        .first()
    )
    if qa_pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA pair not found")

    db.delete(qa_pair)
    db.commit()
    return None