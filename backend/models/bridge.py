from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func

from database import Base


class BridgePermission(Base):
    """S25 (#28): an explicit, scoped, revocable grant of local hardware.

    Created in the web shell (the consent moment), redeemed by the Mac
    companion dialing the hub (`/companion/ws`) with the one-time pairing
    token. `token_hash` is a sha256 of that token — the plaintext exists
    only in the POST response, never in the DB. `scopes` is a JSON list of
    job kinds the companion may run (status/train/fuse/export/serve).
    Revoking flips status and hard-closes the live session.
    """

    __tablename__ = "bridge_permissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(60), nullable=False)
    scopes = Column(Text, nullable=False, default="[]")
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="active")
    last_capabilities = Column(Text)
    last_seen_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp())
    revoked_at = Column(DateTime(timezone=True))
