from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    count: int = Field(default=20, ge=1, le=100)