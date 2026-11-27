
from sqlmodel import SQLModel
from uuid import UUID
from pydantic import EmailStr, field_validator
from datetime import datetime
import re

class MailData(SQLModel):
    subject: str
    body: str
    sender: EmailStr
    to: EmailStr


class AgentRequest(SQLModel):
    mail_data: MailData | None
    input_language: str
    output_language: str
    user_question: str
    user_prompt: str


class AgentRespones(SQLModel):
    scenario: str
    output_language: str
    ai_message: str
    confident: str


class APITokenCreate(SQLModel):
    name: str

    @field_validator("name")
    @classmethod
    def verify_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Name cannot be empty.")

        if len(value) > 50:
            raise ValueError("Name cannot exceed 50 characters.")

        if not re.fullmatch(r"[a-zA-Z0-9_ ]+", value):
            raise ValueError(
                "Name can contain only letters, numbers, and underscores."
            )

        return value


class APITokenResponse(SQLModel):
    id: UUID
    name: str
    tenant_id: UUID
    knowledge_base_id: UUID
    token_prefix: str
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class APITokenCreated(APITokenResponse):
    token: str
    url: str
