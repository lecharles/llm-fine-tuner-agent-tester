from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True)  # S44
    role = Column(String, nullable=False)
    model_label = Column(String)
    content = Column(Text, nullable=False)
    # S75: per-column failure persistence. "error" marks a row whose content is
    # the failure reason (role stays "assistant" so the transcript keeps its
    # turn shape); NULL is a normal reply. Error rows are rendered in the
    # transcript but NEVER replayed into a column's model history (see the
    # rebuild guard in routers/chat.py) — the original schema comment's leak
    # concern is handled by exclusion, not by skipping the write.
    status = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp())

    chat_session = relationship("ChatSession", back_populates="chat_messages")