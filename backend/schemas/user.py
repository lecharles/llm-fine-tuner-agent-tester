from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None


class UserOut(BaseModel):
    id: int
    email: EmailStr
    display_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}