"""S31: the shared library — everything public, nothing private.

One endpoint backs the S32 public library page: public datasets and public
fine-tuned models with their owners' display names. It is deliberately
read-only and only ever returns rows whose visibility is "public"; the
viewer's own private rows never appear here (they live in the normal list
endpoints).

S53 (library 2) adds the dataset detail read: GET /api/library/datasets/{id}
is the read-only community view of one public dataset — metadata, a bounded
Q&A preview, and the owner profile line. Even stricter than the S31
owner-or-public read: a private dataset 404s here for its OWN owner, so the
library can never be a side door into private rows.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.dataset import Dataset
from models.fine_tuned_model import FineTunedModel
from models.qa_pair import QAPair
from models.user import User
from core.security import get_current_user

router = APIRouter(prefix="/api/library", tags=["library"])

# S53: the public detail view ships a bounded preview of the dataset's Q&A
# pairs, not the whole table. pair_count carries the true total and the UI
# says when it was trimmed.
PREVIEW_LIMIT = 100


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


@router.get("/datasets/{dataset_id}")
def read_library_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """S53 (Library 2): the read-only public detail view.

    Strictly public: this endpoint serves the community view only, so a
    private row 404s even for its own owner (they use /api/datasets/{id},
    which stays owner-or-public per S31). Nothing here is mutable —
    mutations never route through /api/library at all.

    Returns the dataset's public metadata, a bounded preview of its Q&A
    pairs (PREVIEW_LIMIT, oldest-first), the true pair_count, and the
    owner profile line: display label plus how many public datasets and
    models they have shared. Emails never ride out — _owner_label already
    reduces to the local part and we expose no contact fields.
    """
    row = (
        db.query(Dataset, User)
        .join(User, Dataset.user_id == User.id)
        .filter(Dataset.id == dataset_id, Dataset.visibility == "public")
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    dataset, owner = row

    public_datasets = (
        db.query(Dataset)
        .filter(Dataset.user_id == owner.id, Dataset.visibility == "public")
        .count()
    )
    public_models = (
        db.query(FineTunedModel)
        .filter(FineTunedModel.user_id == owner.id, FineTunedModel.visibility == "public")
        .count()
    )
    pair_count = db.query(QAPair).filter(QAPair.dataset_id == dataset.id).count()
    pairs = (
        db.query(QAPair)
        .filter(QAPair.dataset_id == dataset.id)
        .order_by(QAPair.id.asc())
        .limit(PREVIEW_LIMIT)
        .all()
    )

    return {
        "dataset": {
            "id": dataset.id,
            "name": dataset.name,
            "description": dataset.description,
            "source": dataset.source,
            "use_case_prompt": dataset.use_case_prompt,
            "created_at": dataset.created_at,
        },
        "pairs": [{"id": p.id, "question": p.question, "answer": p.answer} for p in pairs],
        "pair_count": pair_count,
        "truncated": pair_count > len(pairs),
        "owner": {
            "name": _owner_label(owner),
            "public_datasets": public_datasets,
            "public_models": public_models,
            "member_since": owner.created_at,
        },
    }
