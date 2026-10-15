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
    # S26 (#29) split note: this is a *device-local* path. It is only ever a
    # real file from inside the LOCAL_MODE backend on the Mac that trained
    # (H3's 425 preflight means a hosted server never trains and therefore
    # never owns these bytes). Hosted rows read this column as metadata for
    # display only — never open it; device artifacts are tracked in
    # models/device_artifact.py.
    gguf_path = Column(String)
    format = Column(String, default="gguf")
    size_mb = Column(Integer)
    status = Column(String, nullable=False, default="training")
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp())

    user = relationship("User", back_populates="fine_tuned_models")
    training_run = relationship("TrainingRun", back_populates="fine_tuned_model")
    chat_sessions = relationship("ChatSession", back_populates="fine_tuned_model")