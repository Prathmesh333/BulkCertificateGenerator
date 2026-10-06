from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_name: str = Field(min_length=1, max_length=150)
    issue_date: date
    recipients: list[Any] = Field(min_length=1)

    @field_validator("course_name")
    @classmethod
    def title(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 or ord(c) > 126 for c in value):
            raise ValueError("Course name must contain printable ASCII characters.")
        return value


class Recipient(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=150)
    email: EmailStr | None = None
    reference: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def name_valid(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 or ord(c) > 126 for c in value):
            raise ValueError("Name must contain printable ASCII characters.")
        return value
