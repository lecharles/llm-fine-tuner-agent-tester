from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.fine_tuned_model import FineTunedModel
from models.user import User
from schemas.fine_tuned_model import FineTunedModelOut
from core.security import get_current_user

router = APIRouter(prefix="/api/fine-tuned-models", tags=["fine-tuned-models"])


@router.get("", response_model=list[FineTunedModelOut])
def list_fine_tuned_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(FineTunedModel)
        .filter(FineTunedModel.user_id == current_user.id)
        .all()
    )


@router.get("/{model_id}", response_model=FineTunedModelOut)
def read_fine_tuned_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = (
        db.query(FineTunedModel)
        .filter(FineTunedModel.id == model_id, FineTunedModel.user_id == current_user.id)
        .first()
    )
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fine-tuned model not found"
        )
    return model