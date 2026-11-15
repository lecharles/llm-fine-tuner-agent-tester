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
    ChatTurnOut,
    ColumnScore,
    RatingUpdate,
    SessionScores,
)
from core.security import get_current_user
from api_agents import (
    hosted_backends,
    local_backends,
    ollama_backend,
    fan_out,
    installed_ollama_models,
)
from api_agents.chat.local_server import ensure_local_servers

router = APIRouter(prefix="/api/chat-sessions", tags=["chat"])

# Small companion router so the compare picker list lives on its own prefix
# and never collides with the /{session_id} int paths below.
picker_router = APIRouter(prefix="/api/compare", tags=["compare"])

# Compare fairness: every column answers under a shared length cap so the
# fine-tuned model isn't compared against 500-word hosted essays. Applies to
# all four backends (two local Llamas + two hosted). Tune here, one place.
ANSWER_CAP = (
    "Keep every answer under 150 words. Use short paragraphs with line breaks. "
    "Be direct and skip preamble and filler."
)


@picker_router.get("/ollama-models")
def list_ollama_models(current_user: User = Depends(get_current_user)):
    """Installed Ollama models for the optional compare column (S13, #15).
    Auth'd like every other route; an empty list means Ollama is unreachable
    or has nothing pulled, and the UI simply offers no optional column."""
    return {"models": installed_ollama_models()}


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
        compare_ollama_model=session_in.compare_ollama_model,
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
    response_model=ChatTurnOut,
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

    # The two local columns are separate mlx_lm.server processes. Nothing else
    # in the stack starts them, so bring them up on demand before fanning out:
    # first send pays the model-load cost, later sends reuse the warm servers.
    fused_path = ft.gguf_path or f"_training_runs/{ft.training_run_id}/fused_model"
    startup_errors = ensure_local_servers(fused_path, ft.base_model)

    # Four columns by default: the two local Llamas derived from the pinned
    # model (its fused model served on 8081, its untuned base on 8082), plus
    # the two hosted models chosen on the session. With compare_ollama_model
    # set (S13, #15) a fifth column fans out to that installed Ollama model.
    backends = local_backends(
        fused_path, ft.base_model
    ) + hosted_backends(session.compare_model_a, session.compare_model_b)
    if session.compare_ollama_model:
        backends.append(ollama_backend(session.compare_ollama_model))

    # Multi-turn: rebuild each column's own conversation from the stored messages,
    # then append the new user turn. Each column sees the shared user turns plus
    # only its own prior replies, so the four conversations stay independent.
    prior = (
        db.query(ChatMessage)
        .filter(ChatMessage.chat_session_id == session.id)
        .order_by(ChatMessage.id)
        .all()
    )
    histories = {}
    for backend in backends:
        history = [{"role": "system", "content": ANSWER_CAP}]
        for msg in prior:
            if msg.role == "user":
                history.append({"role": "user", "content": msg.content})
            elif msg.model_label == backend.label and msg.status != "error":
                # S75: persisted error rows show in the transcript but must
                # never replay into the model's own context.
                history.append({"role": "assistant", "content": msg.content})
        history.append({"role": "user", "content": body.content})
        histories[backend.label] = history
    replies = fan_out(backends, histories)

    # Surface every column that could not answer: a startup failure carries
    # more context than the downstream connection error, so it wins.
    errors: dict[str, str] = {k: v for k, v in startup_errors.items() if v}

    # Persist the user turn, then each column's reply. fan_out isolates
    # failures, so the columns that answered always land. S75: a column that
    # failed no longer vanishes — it lands as a status="error" row carrying
    # the same reason the live errors map shows, so the transcript survives a
    # reload (and the errors map itself stays unchanged for live callers).
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
        else:
            reason = errors.get(reply.label) or reply.error or "no reply"
            errors.setdefault(reply.label, reason)
            created.append(
                ChatMessage(
                    chat_session_id=session.id,
                    role="assistant",
                    model_label=reply.label,
                    content=reason,
                    status="error",
                )
            )

    db.add_all(created)
    db.commit()
    for obj in created:
        db.refresh(obj)

    return {"messages": created, "errors": errors}


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


def _owned_session(db: Session, session_id: int, current_user: User) -> ChatSession:
    """Fetch a session or 404. A foreign session reads as missing — the S31
    no-leak rule, same shape as every other owner-only query in this router."""
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


@router.put(
    "/{session_id}/messages/{message_id}/rating", response_model=ChatMessageOut
)
def set_message_rating(
    session_id: int,
    message_id: int,
    body: RatingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """S58: thumbs a single compare reply. 1 = 👍, -1 = 👎, null = clear.

    Only the session owner can rate (404 otherwise, no-leak), and only an
    ANSWERED assistant row is rateable: user turns 400, and S75 error rows 400
    too — scoring a column's connection failure is not feedback about the
    model's answer. Re-rating the same thumb value is a no-op; null clears."""
    session = _owned_session(db, session_id, current_user)
    message = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.id == message_id,
            ChatMessage.chat_session_id == session.id,
        )
        .first()
    )
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
        )
    if message.role != "assistant" or message.model_label is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only model replies can be rated",
        )
    if message.status == "error":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed columns cannot be rated (the reply never happened)",
        )
    message.rating = body.rating
    db.commit()
    db.refresh(message)
    return message


@router.get("/{session_id}/scores", response_model=SessionScores)
def session_scores(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """S58: the session leaderboard — thumbs per column, ranked best-first.

    Built by one pass over the session's answered assistant rows (S75 error
    rows excluded from BOTH replies and rating counts, so a column that kept
    failing is never punished with phantom thumbs-downs it never received).
    Columns that replied but were never rated still appear with net 0 — the
    board should show every live column, not only the judged ones."""
    session = _owned_session(db, session_id, current_user)
    rows = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.chat_session_id == session.id,
            ChatMessage.role == "assistant",
            ChatMessage.model_label.isnot(None),
        )
        .all()
    )
    tally: dict[str, ColumnScore] = {}
    for row in rows:
        entry = tally.setdefault(
            row.model_label,
            ColumnScore(label=row.model_label, up=0, down=0, net=0, replies=0, rated=0),
        )
        if row.status == "error":
            continue  # never an answer: not a reply, not rateable, not scored
        entry.replies += 1
        if row.rating == 1:
            entry.up += 1
            entry.rated += 1
        elif row.rating == -1:
            entry.down += 1
            entry.rated += 1
        entry.net = entry.up - entry.down
    ranked = sorted(
        tally.values(), key=lambda s: (-s.net, -s.up, s.label)
    )
    return SessionScores(
        session_id=session.id,
        total_rated=sum(s.rated for s in ranked),
        scores=ranked,
    )