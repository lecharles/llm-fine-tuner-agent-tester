from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String, nullable=False)
    model_label = Column(String)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chat_session = relationship("ChatSession", back_populates="chat_messages")