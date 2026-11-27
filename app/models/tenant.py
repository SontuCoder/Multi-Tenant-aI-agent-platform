from sqlmodel import SQLModel, Field
from uuid import UUID
from database import TenantRole
from pydantic import field_validator
import re
from datetime import datetime
from .knowledge import KnowledgeResponse
from pydantic import EmailStr

class TenantDetails(SQLModel):
    tenant_id: UUID
    role: TenantRole
    name: str

class TenantCreate(SQLModel):
    name: str = Field(max_length=100, min_length=1)

    @field_validator("name")
    @classmethod
    def name_validate(cls, value:str):
        value = value.strip()
        if len(value)==0 or len(value)>100:
            raise ValueError("Tenant name length must be between 1 to 100.")
        if not re.fullmatch(r"[a-zA-Z0-9_ ]+", value):
            raise ValueError(
                "Tenant name can contain only letters, numbers, and underscores."
            )
        return value

class TenantResponse(SQLModel):
    id: UUID
    name: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime

class UserDetails(SQLModel):
    user_id: UUID
    name: str

class TenantWholeDetails(SQLModel):
    tenant_id: UUID
    tenant_relation: TenantRole
    tenant_name: str
    user: UserDetails
    projects: list[KnowledgeResponse]

class InviteNewUser(SQLModel):
    email: EmailStr
    access_role: TenantRole


    