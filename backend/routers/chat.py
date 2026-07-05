from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.chat_session import ChatSession
from models.chat_message import ChatMessage
from models.fine_tuned_model import FineTunedModel
from models.user import User
from schemas.chat import (
    ChatSessionCreate,
    ChatSessionOut,
    ChatMessageCreate,
    ChatMessageOut,
)
from core.security import get_current_user
from chat.compare import hosted_backends, local_backends, fan_out

router = APIRouter(prefix="/api/chat-sessions", tags=["chat"])


@router.post("", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
def create_chat_session(
    session_in: ChatSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # The pinned fine-tuned model must be one the caller owns. A 404 (not 403)
    # keeps other users' models invisible.
    model = (
        db.query(FineTunedModel)
        .filter(
            FineTunedModel.id == session_in.fine_tuned_model_id,
            FineTunedModel.user_id == current_user.id,
        )
        .first()
    )
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fine-tuned model not found"
        )

    session = ChatSession(
        user_id=current_user.id,
        fine_tuned_model_id=session_in.fine_tuned_model_id,
        title=session_in.title,
        compare_model_a=session_in.compare_model_a,
        compare_model_b=session_in.compare_model_b,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("", response_model=list[ChatSessionOut])
def list_chat_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(ChatSession).filter(ChatSession.user_id == current_user.id).all()


@router.get("/{session_id}", response_model=ChatSessionOut)
def read_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found"
        )
    return session


@router.post(
    "/{session_id}/messages",
    response_model=list[ChatMessageOut],
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    session_id: int,
    body: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found"
        )

    ft = session.fine_tuned_model  # the pinned model, via the relationship

    # Four columns: the two local Llamas derived from the pinned model (its fused
    # model served on 8081, its untuned base on 8082), plus the two hosted models
    # chosen on the session.
    backends = local_backends(
        f"_training_runs/{ft.training_run_id}/fused_model", ft.base_model
    ) + hosted_backends(session.compare_model_a, session.compare_model_b)

    # Single turn for now: the prompt is sent to every column on its own, with no
    # prior history. Multi-turn (threading history per column) is a roadmap item.
    messages = [{"role": "user", "content": body.content}]
    replies = fan_out(backends, messages)

    # Persist the user turn, then each column's reply. fan_out isolates failures,
    # so a column that errored has no content and is skipped here while the others
    # still land.
    created = [ChatMessage(chat_session_id=session.id, role="user", content=body.content)]
    for reply in replies:
        if reply.content is not None:
            created.append(
                ChatMessage(
                    chat_session_id=session.id,
                    role="assistant",
                    model_label=reply.label,
                    content=reply.content,
                )
            )

    db.add_all(created)
    db.commit()
    for obj in created:
        db.refresh(obj)
    return created


@router.get("/{session_id}/messages", response_model=list[ChatMessageOut])
def list_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found"
        )

    return (
        db.query(ChatMessage)
        .filter(ChatMessage.chat_session_id == session.id)
        .order_by(ChatMessage.id)
        .all()
    )