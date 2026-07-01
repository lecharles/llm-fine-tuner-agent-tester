from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class FineTunedModel(Base):
    __tablename__ = "fine_tuned_models"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    training_run_id = Column(Integer, ForeignKey("training_runs.id"), unique=True, nullable=False)
    name = Column(String, nullable=False)
    base_model = Column(String, nullable=False)
    gguf_path = Column(String)
    format = Column(String, default="gguf")
    size_mb = Column(Integer)
    status = Column(String, nullable=False, default="training")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="fine_tuned_models")
    training_run = relationship("TrainingRun", back_populates="fine_tuned_model")
    chat_sessions = relationship("ChatSession", back_populates="fine_tuned_model")