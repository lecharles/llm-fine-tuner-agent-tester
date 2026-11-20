from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models.fine_tuned_model import FineTunedModel
from models.user import User
from schemas.fine_tuned_model import (
    FineTunedModelOut,
    ModelVisibilityUpdate,
    ModelfileOut,
)
from core.security import get_current_user
from training.modelfile import (
    KNOWN_QUANTIZATIONS,
    NO_GGUF_HINT,
    build_modelfile,
    find_gguf,
    ollama_tag,
)

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
    # S31: owner-or-public read; private models 404 for everyone else.
    model = (
        db.query(FineTunedModel)
        .filter(
            FineTunedModel.id == model_id,
            (FineTunedModel.user_id == current_user.id)
            | (FineTunedModel.visibility == "public"),
        )
        .first()
    )
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fine-tuned model not found"
        )
    return model


@router.patch("/{model_id}/visibility", response_model=FineTunedModelOut)
def set_model_visibility(
    model_id: int,
    body: ModelVisibilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """S31: share toggle. Owner-only — a public model still can't be
    re-privated or re-shared by someone else."""
    model = (
        db.query(FineTunedModel)
        .filter(FineTunedModel.id == model_id, FineTunedModel.user_id == current_user.id)
        .first()
    )
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fine-tuned model not found"
        )
    model.visibility = body.visibility
    db.commit()
    db.refresh(model)
    return model


@router.get("/{model_id}/modelfile", response_model=ModelfileOut)
def read_modelfile(
    model_id: int,
    quantize: str | None = Query(
        None, description="import-time quantization type, e.g. q4_K_M"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """S62 (Model serving 1): render the Ollama Modelfile for this row.

    Owner-only, even for public rows: the payload carries the device-local
    path from gguf_path (S26 — those bytes only exist on the Mac that
    trained), so this is not a library read and follows the S31 visibility
    rule: strangers 404 with no leak, owner gets theirs either way. On the
    hosted box the path simply doesn't exist, and the answer is honest:
    has_gguf=false plus the conversion hint — never a Modelfile whose FROM
    would fail on import.
    """
    model = (
        db.query(FineTunedModel)
        .filter(FineTunedModel.id == model_id, FineTunedModel.user_id == current_user.id)
        .first()
    )
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fine-tuned model not found"
        )

    q = (quantize or "").strip().upper() or None
    if q is not None and q not in KNOWN_QUANTIZATIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"unknown quantize {quantize!r}; accepted types: "
                + ", ".join(sorted(KNOWN_QUANTIZATIONS))
            ),
        )

    tag = ollama_tag(model.name)
    # Same fallback the compare-chat uses for a row without a recorded path
    # (routers/chat.py): the fused dir lives at the run's workspace.
    source = model.gguf_path or f"_training_runs/{model.training_run_id}/fused_model"
    gguf = find_gguf(source)
    if gguf is None:
        return ModelfileOut(ollama_tag=tag, has_gguf=False, modelfile=None,
                            source=str(source), hint=NO_GGUF_HINT,
                            create_command=None)
    notes = f"llm-fine-tuner fused model {model.name} (run {model.training_run_id}, id {model.id})"
    return ModelfileOut(
        ollama_tag=tag,
        has_gguf=True,
        modelfile=build_modelfile(gguf, quantize=q, notes=notes),
        source=str(gguf),
        hint=None,
        create_command=f"ollama create {tag} -f Modelfile",
    )