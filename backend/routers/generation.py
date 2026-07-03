from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.dataset import Dataset
from models.qa_pair import QAPair
from models.user import User
from schemas.generation import GenerateRequest
from schemas.qa_pair import QAPairOut
from core.security import get_current_user
from generation.qa_generator import generate_pairs

router = APIRouter(prefix="/api/datasets", tags=["generation"])


@router.post(
    "/{dataset_id}/generate",
    response_model=list[QAPairOut],
    status_code=status.HTTP_201_CREATED,
)
def generate_qa_pairs(
    dataset_id: int,
    body: GenerateRequest,
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

    if not dataset.use_case_prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dataset has no use_case_prompt to generate from",
        )

    try:
        pairs = generate_pairs(dataset.use_case_prompt, body.count)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Generation failed: {exc}",
        )

    if not pairs:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Generation returned no pairs",
        )

    created = [
        QAPair(dataset_id=dataset.id, question=p["question"], answer=p["answer"])
        for p in pairs
    ]
    db.add_all(created)
    db.commit()
    for obj in created:
        db.refresh(obj)
    return created