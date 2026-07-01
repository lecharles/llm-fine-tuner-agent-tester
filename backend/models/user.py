from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    display_name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    datasets = relationship("Dataset", back_populates="user")
    training_runs = relationship("TrainingRun", back_populates="user")
    fine_tuned_models = relationship("FineTunedModel", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user")