
import re

from pydantic import EmailStr, field_validator
from sqlmodel import SQLModel, Field


class UserRegister(SQLModel):
    email: EmailStr
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def verify_username(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Username cannot be empty.")

        if len(value) > 50:
            raise ValueError("Username cannot exceed 50 characters.")

        if not re.fullmatch(r"[a-zA-Z0-9_]+", value):
            raise ValueError(
                "Username can contain only letters, numbers, and underscores."
            )

        return value

    @field_validator("password")
    @classmethod
    def verify_password(cls, value: str) -> str:
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain at least one lowercase letter.")

        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain at least one uppercase letter.")

        if not re.search(r"\d", value):
            raise ValueError("Password must contain at least one digit.")

        if not re.search(r"[^a-zA-Z0-9]", value):
            raise ValueError("Password must contain at least one special character.")

        return value


class UserLogin(SQLModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class EmailVerifyToken(SQLModel):
    token: str = Field(min_length=20, max_length=200)

class ResendEmailTokenRequest(SQLModel):
    email: EmailStr

class InvalidRefreshToken(Exception):
    pass

class RefreshTokenReuseDetected(Exception):
    pass

