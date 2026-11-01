from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    # S44: sessions are always listed per user (and per model in the compare UI).
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    fine_tuned_model_id = Column(Integer, ForeignKey("fine_tuned_models.id"), nullable=False, index=True)
    title = Column(String)
    compare_model_a = Column(String)
    compare_model_b = Column(String)
    # S13 (#15): optional fifth column backed by an installed Ollama model.
    # null = the compare runs with the four default columns.
    compare_ollama_model = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp())

    user = relationship("User", back_populates="chat_sessions")
    fine_tuned_model = relationship("FineTunedModel", back_populates="chat_sessions")
    chat_messages = relationship("ChatMessage", back_populates="chat_session")