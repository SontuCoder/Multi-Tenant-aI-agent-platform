
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlmodel import SQLModel, Field
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    DateTime,
    Enum as SAEnum,
    ForeignKeyConstraint,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector


# ==========================================
# 1. ENUM DEFINITIONS
# ==========================================

class FileType(str, PyEnum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"


class DocumentStatus(str, PyEnum):
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ==========================================
# 2. KNOWLEDGE BASES
# ==========================================

class KnowledgeBase(SQLModel, table=True):

    __tablename__ = "knowledge_bases"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    tenant_id: UUID = Field(
        nullable=False,
        index=True
    )

    name: str = Field(
        sa_type=String(255),
        nullable=False
    )

    description: str | None = Field(
        default=None,
        sa_type=Text
    )

    is_active: bool = Field(
        default=True,
        nullable=False
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        nullable=False
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        nullable=False,
        sa_column_kwargs={"onupdate": func.now()}
    )

    __table_args__ = (
        UniqueConstraint(
            "id", "tenant_id",
            name="uq_knowledge_base_tenant"
        ),
    )


# ==========================================
# 3. DOCUMENTS
# ==========================================

class Document(SQLModel, table=True):

    __tablename__ = "documents"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    knowledge_base_id: UUID = Field(
        nullable=False,
        index=True
    )

    tenant_id: UUID = Field(
        nullable=False,
        index=True
    )

    filename: str = Field(
        sa_type=String(500),
        nullable=False
    )

    file_path: str = Field(
        sa_type=Text,
        nullable=False
    )

    file_type: FileType = Field(
        default=FileType.TXT,
        sa_column=Column(
            SAEnum(FileType, name="file_type_enum"),
            nullable=False,
            default=FileType.TXT
        )
    )

    file_hash: str = Field(
        sa_type=String(128),
        nullable=False
    )

    status: DocumentStatus = Field(
        default=DocumentStatus.UPLOADING,
        sa_column=Column(
            SAEnum(DocumentStatus, name="document_status_enum"),
            nullable=False,
            default=DocumentStatus.UPLOADING
        )
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        nullable=False
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        nullable=False,
        sa_column_kwargs={"onupdate": func.now()}
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["knowledge_base_id", "tenant_id"],
            ["knowledge_bases.id", "knowledge_bases.tenant_id"],
            ondelete="CASCADE",
            name="fk_document_knowledge_base_tenant"
        ),

        UniqueConstraint(
            "id", "knowledge_base_id", "tenant_id",
            name="uq_document_kb_tenant"
        ),

        Index(
            "idx_document_hash",
            "knowledge_base_id",
            "file_hash"
        ),
    )


# ==========================================
# 4. DOCUMENT CHUNKS
# ==========================================

class DocumentChunk(SQLModel, table=True):

    __tablename__ = "document_chunks"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    knowledge_base_id: UUID = Field(
        nullable=False
    )

    document_id: UUID = Field(
        nullable=False,
        index=True
    )

    tenant_id: UUID = Field(
        nullable=False,
        index=True
    )

    chunk_index: int = Field(
        sa_type=Integer,
        nullable=False
    )

    chunk_text: str = Field(
        sa_type=Text,
        nullable=False
    )

    # Must match the embedding model dimensions.
    embedding: list[float] | None = Field(
        default=None,
        sa_type=Vector(1536)
    )

    chunk_metadata: dict = Field(
        default_factory=dict,
        sa_type=JSONB,
        nullable=False
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        nullable=False
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        nullable=False,
        sa_column_kwargs={"onupdate": func.now()}
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "knowledge_base_id", "tenant_id"],
            ["documents.id", "documents.knowledge_base_id","documents.tenant_id"],
            ondelete="CASCADE",
            name="fk_chunk_document_kb_tenant"
        ),

        UniqueConstraint(
            "document_id", "chunk_index",
            name="uq_document_chunk_index"
        ),

        Index(
            "idx_chunk_tenant_kb",
            "tenant_id",
            "knowledge_base_id"
        ),

        Index(
            "idx_chunk_document",
            "document_id"
        ),
    )


# ==========================================
# 5. EMBEDDING MODELS
# ==========================================

class EmbeddingModel(SQLModel, table=True):

    __tablename__ = "embedding_models"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    model_name: str = Field(
        sa_type=String(255),
        nullable=False
    )

    provider: str = Field(
        sa_type=String(100),
        nullable=False
    )

    dimensions: int = Field(
        sa_type=Integer,
        nullable=False
    )

    is_active: bool = Field(
        default=True,
        nullable=False
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        nullable=False
    )
