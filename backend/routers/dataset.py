from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.dataset import Dataset
from models.qa_pair import QAPair
from models.user import User
from schemas.dataset import (
    DatasetCreate,
    DatasetUpdate,
    DatasetOut,
    DedupeRequest,
    DedupeResult,
    DedupeGroup,
    MergeRequest,
    MergeResult,
)
from core.security import get_current_user, is_service_lane
from generation.prompt_suggest import suggest_use_case_prompt

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

# S56: bounded preview for dedupe groups (the counts are always complete).
PREVIEW_GROUPS = 50

# SQLite caps bind variables (default 999); batch IN() writes under that.
_SQLITE_CHUNK = 500


def _pair_key(question: str, answer: str) -> tuple[str, str]:
    """S56: normalized exact-match key for a Q&A pair.

    Whitespace is collapsed and case folded, so "What is X?" and
    "  what is   x? " are the same training example. Content is otherwise
    compared exactly — deliberately NOT fuzzy: merging near-misses with
    different answers would silently pick a winner the user never chose.
    """
    q = " ".join((question or "").split()).casefold()
    a = " ".join((answer or "").split()).casefold()
    return (q, a)


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
    # S31: owner-or-public read. Private datasets stay invisible to everyone
    # else (404, not 403, so existence is not leaked).
    dataset = (
        db.query(Dataset)
        .filter(
            Dataset.id == dataset_id,
            (Dataset.user_id == current_user.id) | (Dataset.visibility == "public"),
        )
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return dataset


@router.post("/{dataset_id}/use-case-suggestion")
def suggest_use_case(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """S27: template a starter use-case prompt from the dataset's saved
    name/description. Zero-LLM and idempotent — it never writes; the UI fills
    the editable box and the user saves."""
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return {"suggestion": suggest_use_case_prompt(dataset.name, dataset.description)}


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
    # S8 (#11): service lanes get read/create/queue permissions only.
    if is_service_lane(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service lanes cannot delete datasets",
        )
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


def _owned_dataset(dataset_id: int, db: Session, current_user: User) -> Dataset:
    """S56: owner-only fetch shared by the destructive pair ops. Kept local
    (not routers.qa_pair.get_owned_dataset) so dataset mutations never answer
    a public-dataset read path by accident: dedupe/merge are writes."""
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
        .first()
    )
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return dataset


def _pairs_of(db: Session, dataset_id: int) -> list[QAPair]:
    # Ordered by id: the lowest id is the oldest row, and dedupe keeps it.
    return (
        db.query(QAPair)
        .filter(QAPair.dataset_id == dataset_id)
        .order_by(QAPair.id.asc())
        .all()
    )


# S56: fixed suffix paths, declared after the /{dataset_id} routes (no id can
# collide with a two-segment path).
@router.post("/{dataset_id}/dedupe", response_model=DedupeResult)
def dedupe_dataset(
    dataset_id: int,
    body: DedupeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """S56: drop exact-duplicate Q&A pairs inside one dataset, keeping the
    oldest row of each group (lowest id). dry_run previews without writing.
    Comparison key is whitespace- and case-normalized (see _pair_key)."""
    if is_service_lane(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service lanes cannot dedupe datasets",
        )
    _owned_dataset(dataset_id, db, current_user)

    groups: dict[tuple[str, str], list[QAPair]] = {}
    for pair in _pairs_of(db, dataset_id):
        groups.setdefault(_pair_key(pair.question, pair.answer), []).append(pair)

    dup_groups = [(key, rows) for key, rows in groups.items() if len(rows) > 1]
    removed_ids = [row.id for _, rows in dup_groups for row in rows[1:]]

    preview = [
        DedupeGroup(
            question=rows[0].question,
            answer=rows[0].answer,
            kept_id=rows[0].id,
            removed_ids=[row.id for row in rows[1:]],
        )
        for _, rows in dup_groups[:PREVIEW_GROUPS]
    ]

    if removed_ids and not body.dry_run:
        for start in range(0, len(removed_ids), _SQLITE_CHUNK):
            chunk = removed_ids[start : start + _SQLITE_CHUNK]
            db.query(QAPair).filter(QAPair.id.in_(chunk)).delete(synchronize_session=False)
        db.commit()

    total = sum(len(rows) for rows in groups.values())
    return DedupeResult(
        dry_run=body.dry_run,
        total_pairs=total,
        unique_pairs=len(groups),
        removed=len(removed_ids),
        duplicate_groups=len(dup_groups),
        groups_preview=preview,
        preview_truncated=len(dup_groups) > PREVIEW_GROUPS,
    )


@router.post("/{dataset_id}/merge", response_model=MergeResult)
def merge_dataset(
    dataset_id: int,
    body: MergeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """S56: move Q&A pairs from the user's source dataset into this target.
    Pairs whose normalized (question, answer) key already exists in the
    target - or was already moved earlier in this merge (source-internal
    dupes) - are skipped and stay in the source; nothing in the source is
    ever deleted here. dry_run computes the same numbers without writing.
    Both datasets must belong to the caller: the source 404s for anyone
    else's dataset, public included (S31 rule: writes are owner-only)."""
    if is_service_lane(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service lanes cannot merge datasets",
        )
    target = _owned_dataset(dataset_id, db, current_user)
    if body.source_dataset_id == target.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot merge a dataset into itself",
        )
    source = _owned_dataset(body.source_dataset_id, db, current_user)

    seen = {_pair_key(p.question, p.answer) for p in _pairs_of(db, target.id)}
    moved_ids: list[int] = []
    skipped = 0
    source_pairs = _pairs_of(db, source.id)
    for pair in source_pairs:
        key = _pair_key(pair.question, pair.answer)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        moved_ids.append(pair.id)

    if moved_ids and not body.dry_run:
        for start in range(0, len(moved_ids), _SQLITE_CHUNK):
            chunk = moved_ids[start : start + _SQLITE_CHUNK]
            db.query(QAPair).filter(QAPair.id.in_(chunk)).update(
                {QAPair.dataset_id: target.id}, synchronize_session=False
            )
        db.commit()

    return MergeResult(
        dry_run=body.dry_run,
        target_dataset_id=target.id,
        source_dataset_id=source.id,
        moved=len(moved_ids),
        skipped_duplicates=skipped,
        source_remaining=len(source_pairs) - len(moved_ids),
    )