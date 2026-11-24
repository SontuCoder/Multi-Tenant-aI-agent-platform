from sqlmodel import Session, select
from core import hash_token, generate_secure_token, decode_access_token, create_access_token, verify_password, hash_password
from uuid import UUID
from database import User, EmailVerificationToken
from datetime import datetime, timezone, timedelta
from models import UserRegister

def check_email_exists(email: str, session: Session)-> bool:
    query = select(User).where(User.email == email)
    user = session.exec(query).first()
    return user is not None

def create_user(email: str, password: str, username: str, session: Session)-> User:
    hased_pass = hash_password(password)
    new_user = User(email=email, password_hash=hased_pass, username=username, is_email_verified=False)

    session.add(new_user)
    session.flush()
    return new_user

def create_save_email_verification_token(email: str, user_id: UUID, session: Session)-> str:
    verification_token = generate_secure_token()
    verification_token_hash = hash_token(verification_token)
    query = select(EmailVerificationToken).where(EmailVerificationToken.email==email, EmailVerificationToken.consumed_at.is_(None))
    old_entries = session.exec(query).all()
    for token in old_entries:
        token.consumed_at = datetime.now(timezone.utc)
    
    email_verification_entry = EmailVerificationToken(email=email, user_id=user_id, token_hash=verification_token_hash,expires_at=datetime.now(timezone.utc)+ timedelta(minutes=15))  
    session.add(email_verification_entry)
    session.flush()
    return verification_token

def register_user(user_data: UserRegister, session: Session):
    try:
        if check_email_exists(user.email, session):
            raise ValueError("Email is already registered.")

        user = create_user(
            email=user_data.email,
            password=user_data.password,
            username=user_data.username,
            session=session
        )

        verification_token = create_save_email_verification_token(
            email=user.email,
            user_id=user.id,
            session=session
        )

        session.commit()
        session.refresh(user)

        return user, verification_token

    except Exception:
        session.rollback()
        raise