from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class TrainingRun(Base):
    __tablename__ = "training_runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    base_model = Column(String, nullable=False)
    method = Column(String, nullable=False, default="qlora")
    iters = Column(Integer, nullable=False, default=300)
    learning_rate = Column(Numeric)
    status = Column(String, nullable=False, default="queued")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="training_runs")
    dataset = relationship("Dataset")
    fine_tuned_model = relationship("FineTunedModel", back_populates="training_run", uselist=False)