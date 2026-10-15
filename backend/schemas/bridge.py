from pydantic import BaseModel, Field, field_validator

from core.bridge import JOB_KINDS


class BridgePermissionCreate(BaseModel):
    """POST /api/bridge/permissions body (S25, issue #28).

    This request *is* the consent act: the scopes picked here are exactly
    what the paired Mac may run, and nothing else. The response returns the
    pairing token once; only its sha256 is ever stored.
    """

    name: str = Field(min_length=1, max_length=60)
    scopes: list[str]

    @field_validator("scopes")
    @classmethod
    def scopes_known(cls, v: list[str]) -> list[str]:
        cleaned = sorted(set(v))
        if not cleaned:
            raise ValueError("pick at least one scope")
        unknown = [s for s in cleaned if s not in JOB_KINDS]
        if unknown:
            raise ValueError(f"unknown scope(s): {', '.join(unknown)}")
        return cleaned
