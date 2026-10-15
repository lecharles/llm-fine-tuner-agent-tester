from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from database import Base


class DeviceArtifact(Base):
    """S26 (#29): the metadata half of the local/hosted data split.

    The rule this table encodes: the hosted database owns the *account* —
    users, datasets, Q&A pairs, chat, run history — and only ever a
    POINTER to artifact bytes (adapters, fused models, GGUFs, train logs)
    that physically stay on the device that produced them. The hub never
    opens, stats, serves, or reopens `device_path`; it is a display-only
    string captured at report time.

    Companion reports land through the hub `artifacts` frame
    (routers/bridge.py); rows are keyed per (permission, device_run_id,
    kind) so re-reporting updates last_seen/metrics instead of duplicating.
    Forgetting a row via DELETE /api/bridge/artifacts/{id} erases the
    pointer only — the bytes were never here to begin with.
    """

    __tablename__ = "device_artifacts"
    __table_args__ = (
        UniqueConstraint("permission_id", "device_run_id", "kind",
                         name="uq_device_artifacts_run_kind"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    permission_id = Column(Integer, ForeignKey("bridge_permissions.id"),
                           nullable=False, index=True)
    device_run_id = Column(Integer, nullable=False)
    kind = Column(String(20), nullable=False)          # adapter | fused | gguf | trainlog
    name = Column(String(120), nullable=False)
    base_model = Column(String)
    size_bytes = Column(BigInteger)
    sha256 = Column(String(64))                        # optional fingerprint, hex or NULL
    device_path = Column(Text)                         # display-only; never opened by the hub
    first_reported_at = Column(DateTime(timezone=True),
                               server_default=func.current_timestamp())
    last_seen_at = Column(DateTime(timezone=True),
                          server_default=func.current_timestamp())
