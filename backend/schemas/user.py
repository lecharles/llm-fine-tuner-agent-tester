from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None


class UserOut(BaseModel):
    id: int
    # str, not EmailStr: the local-mode seed user is `local@llmtuner`, which a
    # strict email validator rejects on the way OUT of GET /api/auth/me. Input
    # validation (UserCreate) keeps EmailStr; response rendering must not 500.
    email: str
    display_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}