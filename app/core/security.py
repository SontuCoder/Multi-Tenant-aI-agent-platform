from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from jose import jwt, JWTError
from pwdlib import PasswordHash
from core.config import settings
import secrets
import hashlib

password_hash = PasswordHash.recommended()

def hash_password(password: str)-> str:
    return password_hash.hash(password)

def verify_password(plain_pass: str, hased_pass: str)-> bool:
    return password_hash.verify(plain_pass, hased_pass)

def create_access_token(user_id: UUID, session_id: UUID)-> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "jti": str(uuid4()),
        "iat":int(now.timestamp()),
        "exp": int(
            (
                now + timedelta(
                    minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
                )
            ).timestamp()
        ),
        "type": "access",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )

def decode_access_token(access_token: str)-> dict:
    payload = jwt.decode(access_token, 
                    settings.JWT_SECRET_KEY, 
                    algorithms=[settings.JWT_ALGORITHM], 
                    issuer=settings.JWT_ISSUER,
                    audience=settings.JWT_AUDIENCE)
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")

    required_claims = ["sub", "sid", "jti", "iat", "exp"]

    if not all(payload.get(claim) for claim in required_claims):
        raise JWTError("Missing required token claims")

    return payload


def generate_secure_token()-> str:
    return secrets.token_urlsafe(64)

def hash_token(token: str)-> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()



