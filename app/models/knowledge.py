from sqlmodel import SQLModel
from pydantic import field_validator, ConfigDict
from database import FileType, DocumentStatus
import re
from uuid import UUID
from datetime import datetime

class KnowledgeCreate(SQLModel):
    tenant_id: UUID
    name: str
    description: str | None
    is_active: bool | None

    @field_validator("name")
    @classmethod
    def name_validate(cls, value: str):
        pattern = r'^[a-zA-Z0-9_ -]+$'
        if not re.fullmatch(pattern, value):
            raise ValueError("Name can only contain letters, numbers, spaces, underscores (_), ampersands (&), and hyphens (-).")
        return value.strip()

    @field_validator("description")
    @classmethod
    def description_validate(cls, value: str):
        if value is None:
            return value.strip()
        if len(value.strip()) > 100:
            raise ValueError("Description should be under 100 latter")
        return value.strip()

class KnowledgeResponse(SQLModel):

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    name: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class DocumentUploadResponse(SQLModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    knowledge_base_id: UUID
    filename: str
    file_path: str
    file_type: FileType
    file_hash: str
    scenario: str | None
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime

class SemanticSearchResult(SQLModel):
    chunk_id: UUID
    document_id: UUID
    chunk_text: str
    distance: float
    scenario: str | None

class SemanticSearchResponse(SQLModel):
    knowledge_base_id: UUID
    question: str
    results: list[SemanticSearchResult]
