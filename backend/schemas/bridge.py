from pydantic import BaseModel, Field, field_validator

from core.bridge import JOB_KINDS

# S26 (#29): the artifact kinds a device may report metadata about. These
# rows are POINTER ONLY — the bytes stay on the device; nothing host-side
# ever resolves `device_path` against a filesystem.
ARTIFACT_KINDS = ("adapter", "fused", "gguf", "trainlog")
ARTIFACT_ITEMS_MAX = 200


class DeviceArtifactItem(BaseModel):
    """One entry of a companion's `artifacts` manifest frame."""

    device_run_id: int = Field(ge=0)
    kind: str
    name: str = Field(min_length=1, max_length=120)
    base_model: str | None = Field(default=None, max_length=200)
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = None
    device_path: str | None = Field(default=None, max_length=500)

    @field_validator("kind")
    @classmethod
    def kind_known(cls, v: str) -> str:
        if v not in ARTIFACT_KINDS:
            raise ValueError(f"unknown artifact kind {v!r} (allowed: {', '.join(ARTIFACT_KINDS)})")
        return v

    @field_validator("sha256")
    @classmethod
    def sha_is_hex(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v):
            raise ValueError("sha256 must be 64 hex chars")
        return v


class ArtifactsFrame(BaseModel):
    """`{"type":"artifacts","items":[...]}` inbound frame (S26)."""

    type: str
    items: list[DeviceArtifactItem] = Field(min_length=1, max_length=ARTIFACT_ITEMS_MAX)

    @field_validator("type")
    @classmethod
    def must_be_artifacts(cls, v: str) -> str:
        if v != "artifacts":
            raise ValueError("type must be 'artifacts'")
        return v


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
