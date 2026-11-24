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
    func
)
from sqlalchemy.dialects.postgresql import JSONB, INET


def utc_now():
    return datetime.now(timezone.utc)

#==========================================
# 1. Enums
# ==========================================

class TenantRole(str, PyEnum):
    ADMIN = "admin"
    FOLDER_ADMINISTRATOR = "folder_administrator"
    AI_USER = "ai_user"

#==========================================
# 1. User Table
# ==========================================

class User(SQLModel, table=True):
    __tablename__ = "user"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    username: str = Field(sa_type=String(100), nullable=False)
    email: str = Field(sa_type=String(255), nullable=False, unique=True)
    password_hash: str = Field(sa_type=String(255), nullable=False)
    is_email_verified: bool = Field(default=False, sa_type=Boolean, nullable=False)
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

#==========================================
# 2. Tenant Table
# ==========================================

class Tenant(SQLModel, table=True):
    __tablename__ = "tenant"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(sa_type=String(100), nullable=False)
    created_by: UUID = Field(nullable=False)
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
            ["created_by"],
            ["user.id"],
            ondelete="RESTRICT",
            name="fk_tenant_user"
        ),
        UniqueConstraint(
            "name", "created_by",
            name="uq_tenant_user"
        ),
        Index(
            "idx_tenant_user",
            "created_by"
        )
    )

#==========================================
# 3. User_Tenant Table
# ==========================================

class TenantMembership(SQLModel, table=True):
    __tablename__ = "tenant_memberships"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(nullable=False)
    user_id: UUID = Field(nullable=False)
    role: TenantRole = Field(nullable=False)
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
            ["tenant_id"],
            ["tenant.id"],
            ondelete="CASCADE"
        ),

        ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="CASCADE"
        ),
        UniqueConstraint(
            "tenant_id", "user_id",
            name="uq_tenant_user_role"
        ),
        Index(
            "idx_tenant",
            "tenant_id"
        ),
        Index(
            "idx_user",
            "user_id"
        )
    )

#==========================================
# 4. Auth Session Table
# ==========================================

class AuthSession(SQLModel, table=True):

    __tablename__ = "auth_sessions"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    user_id: UUID = Field(nullable=False)

    device_name: str | None = Field(
        default=None,
        sa_type=String(150),
        nullable=True
    )

    user_agent: str | None = Field(
        default=None,
        sa_type=Text,
        nullable=True
    )

    ip_address: str | None = Field(
        default=None,
        sa_type=INET,
        nullable=True
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False
    )

    last_activity_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False
    )

    idle_expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False
    )

    absolute_expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False
    )

    revoked_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True
    )

    revocation_reason: str | None = Field(
        default=None,
        sa_type=String(100),
        nullable=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="CASCADE",
            name="fk_auth_session_user"
        ),

        Index(
            "idx_auth_session_user",
            "user_id"
        ),

        Index(
            "idx_auth_session_expires",
            "absolute_expires_at"
        ),
    )

#==========================================
# 5. Email Verified Table
# ==========================================

class EmailVerificationToken(SQLModel, table=True):

    __tablename__ = "email_verification_tokens"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    user_id: UUID = Field(nullable=False)

    # SHA-256 digest of a random verification token.
    token_hash: str = Field(
        sa_type=String(64),
        nullable=False,
        unique=True
    )

    # Snapshot of the email being verified.
    email: str = Field(
        sa_type=String(255),
        nullable=False
    )

    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False
    )

    consumed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True)
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="CASCADE",
            name="fk_email_verification_user"
        ),

        Index(
            "idx_email_verification_user",
            "user_id"
        ),

        Index(
            "idx_email_verification_expiry",
            "expires_at"
        ),
    )

# ==========================================
# 6. REFRESH TOKENS
# ==========================================

class RefreshToken(SQLModel, table=True):

    __tablename__ = "refresh_tokens"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    session_id: UUID = Field(nullable=False)

    # Store only the digest, never the raw refresh token.
    token_hash: str = Field(
        sa_type=String(64),
        nullable=False,
        unique=True
    )

    issued_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False
    )

    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False
    )

    consumed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True)
    )

    revoked_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True)
    )

    replaced_by_id: UUID | None = Field(
        default=None
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id"],
            ["auth_sessions.id"],
            ondelete="CASCADE",
            name="fk_refresh_token_session"
        ),

        ForeignKeyConstraint(
            ["replaced_by_id"],
            ["refresh_tokens.id"],
            ondelete="SET NULL",
            name="fk_refresh_token_replacement"
        ),

        Index(
            "idx_refresh_token_session",
            "session_id"
        ),

        Index(
            "idx_refresh_token_expiry",
            "expires_at"
        ),
    )

# ==========================================
# 7. PASSWORD RESET TOKENS
# ==========================================

class PasswordResetToken(SQLModel, table=True):

    __tablename__ = "password_reset_tokens"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    user_id: UUID = Field(nullable=False)

    token_hash: str = Field(
        sa_type=String(64),
        nullable=False,
        unique=True
    )

    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False
    )

    consumed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True)
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="CASCADE",
            name="fk_password_reset_user"
        ),

        Index(
            "idx_password_reset_user",
            "user_id"
        ),

        Index(
            "idx_password_reset_expiry",
            "expires_at"
        ),
    )


# ==========================================
# 8. AUTHENTICATION SECURITY EVENTS
# ==========================================

class AuthSecurityEvent(SQLModel, table=True):

    __tablename__ = "auth_security_events"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    user_id: UUID | None = Field(
        default=None
    )

    session_id: UUID | None = Field(
        default=None
    )

    event_type: str = Field(
        sa_type=String(100),
        nullable=False
    )

    ip_address: str | None = Field(
        default=None,
        sa_type=INET
    )

    user_agent: str | None = Field(
        default=None,
        sa_type=Text
    )

    event_metadata: dict = Field(
        default_factory=dict,
        sa_column=Column(
            "metadata",
            JSONB,
            nullable=False
        )
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="SET NULL",
            name="fk_auth_event_user"
        ),

        ForeignKeyConstraint(
            ["session_id"],
            ["auth_sessions.id"],
            ondelete="SET NULL",
            name="fk_auth_event_session"
        ),

        Index(
            "idx_auth_event_user",
            "user_id"
        ),

        Index(
            "idx_auth_event_created",
            "created_at"
        ),

        Index(
            "idx_auth_event_type",
            "event_type"
        ),
    )


