"""S31: the shared library — everything public, nothing private.

One endpoint backs the S32 public library page: public datasets and public
fine-tuned models with their owners' display names. It is deliberately
read-only and only ever returns rows whose visibility is "public"; the
viewer's own private rows never appear here (they live in the normal list
endpoints).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.dataset import Dataset
from models.fine_tuned_model import FineTunedModel
from models.user import User
from core.security import get_current_user

router = APIRouter(prefix="/api/library", tags=["library"])


def _owner_label(user: User | None) -> str:
    if user is None:
        return "Unknown"
    if user.display_name:
        return user.display_name
    return user.email.split("@")[0] if user.email else "Unknown"


@router.get("")
def read_library(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    datasets = (
        db.query(Dataset, User)
        .join(User, Dataset.user_id == User.id)
        .filter(Dataset.visibility == "public")
        .order_by(Dataset.created_at.desc())
        .all()
    )
    models = (
        db.query(FineTunedModel, User)
        .join(User, FineTunedModel.user_id == User.id)
        .filter(FineTunedModel.visibility == "public")
        .order_by(FineTunedModel.created_at.desc())
        .all()
    )
    return {
        "datasets": [
            {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "source": d.source,
                "owner": _owner_label(u),
                "created_at": d.created_at,
            }
            for d, u in datasets
        ],
        "models": [
            {
                "id": m.id,
                "name": m.name,
                "base_model": m.base_model,
                "status": m.status,
                "size_mb": m.size_mb,
                "owner": _owner_label(u),
                "created_at": m.created_at,
            }
            for m, u in models
        ],
    }
