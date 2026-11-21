from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


def _no_null_bytes(v: str) -> str:
    # S54 kept passlib's NULL-byte rejection at the bcrypt layer; enforcing
    # it in the schema means a bad signup/login *body* 422s before it ever
    # reaches verify_password/hash_password (which raise ValueError on NUL).
    if "\x00" in v:
        raise ValueError("must not contain NULL bytes")
    return v


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None


# S64: account editing. display_name is the ONLY mutable identity field —
# email is the login key (and lane/local@ identities are synthetic), so it
# stays read-only on this surface.
class UserUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=60)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = _no_null_bytes(v).strip()
        if not v:
            raise ValueError("display name cannot be blank")
        return v


# S64: password change. The 8-char floor is new-code policy only — legacy
# rows keep verifying at any length (we never force a rotation); it exists so
# "rotate your shared-instance password" can't quietly set it to "1234567".
class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=4096)

    @field_validator("current_password", "new_password")
    @classmethod
    def no_null(cls, v: str) -> str:
        return _no_null_bytes(v)


class UserOut(BaseModel):
    id: int
    # str, not EmailStr: the local-mode seed user is `local@llmtuner`, which a
    # strict email validator rejects on the way OUT of GET /api/auth/me. Input
    # validation (UserCreate) keeps EmailStr; response rendering must not 500.
    email: str
    display_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}