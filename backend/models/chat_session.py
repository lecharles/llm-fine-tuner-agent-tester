from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    fine_tuned_model_id = Column(Integer, ForeignKey("fine_tuned_models.id"), nullable=False)
    title = Column(String)
    compare_model_a = Column(String)
    compare_model_b = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="chat_sessions")
    fine_tuned_model = relationship("FineTunedModel", back_populates="chat_sessions")
    chat_messages = relationship("ChatMessage", back_populates="chat_session")