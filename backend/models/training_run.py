from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, ForeignKey
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
    # S33 (#35) advanced hyperparameters: LoRA width (rank) and its scaling
    # factor (alpha). mlx_lm.lora's own defaults are 8/16; we persist them per
    # run so the UI can show and replay exactly what a run trained with.
    lora_rank = Column(Integer, nullable=False, default=8)
    lora_alpha = Column(Integer, nullable=False, default=16)
    status = Column(String, nullable=False, default="queued")
    # #42: when a run fails we persist the exception text + log tail here so the
    # failure is visible in the API and the Train UI instead of being silent.
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp())
    completed_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="training_runs")
    dataset = relationship("Dataset")
    fine_tuned_model = relationship("FineTunedModel", back_populates="training_run", uselist=False)