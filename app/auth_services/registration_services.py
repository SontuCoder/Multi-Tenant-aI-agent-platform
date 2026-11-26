from sqlmodel import Session, select
from core import settings
from core import hash_token, generate_secure_token, decode_access_token, create_access_token, verify_password, hash_password
from uuid import UUID
from database import User, EmailVerificationToken, AuthSession, RefreshToken, get_session, PasswordResetToken
from datetime import datetime, timezone, timedelta
from models import UserRegister, EmailVerifyToken, UserLogin, InvalidRefreshToken, RefreshTokenReuseDetected
from .email_service import send_verification_email, send_password_reset_email, send_password_reset_success_email
from fastapi import HTTPException, Response, Request, status, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from dataclasses import dataclass
from jose import JWTError


bearer_scheme = HTTPBearer(auto_error=False)


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

async def register_user(user_data: UserRegister, session: Session):
    try:
        if check_email_exists(user_data.email, session):
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
        await send_verification_email(user.email, verification_token)
        session.commit()
        session.refresh(user)

        return user, verification_token

    except Exception:
        session.rollback()
        raise

def verify_email(raw_token: EmailVerifyToken, session: Session)-> bool:
    try:
        token = raw_token.token
        now=datetime.now(timezone.utc)
        token_hash = hash_token(token)
        query = select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash
        ) 
        verification_data = session.exec(query).first()

        if verification_data is None:
            raise ValueError("Invalid verification token.")

        if verification_data.consumed_at is not None:
            raise ValueError("Verification token has already been used.")

        if verification_data.expires_at <= now:
            raise ValueError("Verification token has expired.")

        user_query = select(User).where(
            User.id == verification_data.user_id
        )

        user = session.exec(user_query).first()

        if user is None:
            raise ValueError("User account not found.")

        if user.is_email_verified:
            raise ValueError("Email is already verified.")

        user.is_email_verified = True
        verification_data.consumed_at = now

        session.add(user)
        session.add(verification_data)
        session.commit()

        return True
    except:
        session.rollback()
        raise

async def resend_verification_token(email: str, session: Session):
    try:
        query = select(User).where(User.email == email)
        user = session.exec(query).first()

        if user is None:
            raise ValueError("Account not found.")

        if user.is_email_verified:
            raise ValueError("Email is already verified.")

        verification_token = create_save_email_verification_token(
            email=user.email,
            user_id=user.id,
            session=session
        )

        session.commit()
        await send_verification_email(email, verification_token)

        return user, verification_token

    except Exception:
        session.rollback()
        raise


def authenticate_user(user_data: UserLogin, session: Session)-> User:
    query = select(User).where(User.email == user_data.email)
    user = session.exec(query).first()

    # Do not reveal whether the email exists.
    if user is None:
        raise ValueError("Invalid email or password.")

    if not verify_password(user_data.password, user.password_hash):
        raise ValueError("Invalid email or password.")

    if not user.is_email_verified:
        raise PermissionError(
            "Please verify your email before logging in."
        )

    return user

def create_auth_session(
    user_id,
    session: Session,
    device_name: str | None = None,
    user_agent: str | None = None,
    ip_address: str | None = None
) -> AuthSession:

    now = datetime.now(timezone.utc)

    absolute_expiry = now + timedelta(days=30)
    idle_expiry = min(
        now + timedelta(days=7),
        absolute_expiry
    )

    auth_session = AuthSession(
        user_id=user_id,
        device_name=device_name,
        user_agent=user_agent,
        ip_address=ip_address,
        created_at=now,
        last_activity_at=now,
        idle_expires_at=idle_expiry,
        absolute_expires_at=absolute_expiry
    )

    session.add(auth_session)
    session.flush()

    return auth_session

def create_refresh_token(
    auth_session: AuthSession,
    session: Session
) -> str:

    raw_token = generate_secure_token()

    refresh_token = RefreshToken(
        session_id=auth_session.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=int(settings.REFRESH_TOKEN_EXPIRE_DAYS))
    )

    session.add(refresh_token)
    session.flush()

    return raw_token


def login_user(user_data: UserLogin, session: Session, device_name: str | None = None, user_agent: str | None = None, ip_address: str | None = None):
    try:
        user = authenticate_user(
            user_data=user_data,
            session=session
        )
        auth_session = create_auth_session(
            user_id=user.id,
            session=session,
            device_name=device_name,
            user_agent=user_agent,
            ip_address=ip_address
        )

        # 3. Generate access JWT.
        access_token = create_access_token(
            user_id=user.id,
            session_id=auth_session.id
        )

        # 4. Generate and store refresh-token hash.
        raw_refresh_token = create_refresh_token(
            auth_session=auth_session,
            session=session
        )

        session.commit()
        return user, access_token, raw_refresh_token
    except: 
        session.rollback()
        raise

def set_cookie_details(key:str, value: str, max_age: int, path: int, response: Response)-> None:
    response.set_cookie(
        key=key,
        value=value,
        httponly=True,
        secure=settings.IS_Prod,
        samesite="lax",
        max_age=max_age,
        path=path
    )

def get_cookie_details(cookie_key: str, request: Request)-> str:
    cookie_data = request.cookies.get(cookie_key)
    if not cookie_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You have not this permission"
        )
    return cookie_data.strip()

def delete_cookie_details(key:str, path: int, response: Response)-> None:
    response.delete_cookie(
        key=key,
        path=path,
        secure=settings.IS_Prod,
        httponly=True,
        samesite="lax"
    )


def revoke_active_refresh_tokens(
    auth_session: AuthSession,
    session: Session,
    now: datetime
) -> None:
    """
    Revoke all active refresh tokens belonging to a session.

    The AuthSession row must already be locked.
    """

    query = (
        select(RefreshToken)
        .where(
            RefreshToken.session_id == auth_session.id,
            RefreshToken.consumed_at.is_(None),
            RefreshToken.revoked_at.is_(None)
        )
        .with_for_update()
    )

    active_tokens = session.exec(query).all()

    for token in active_tokens:
        token.revoked_at = now

def refresh_tokens(
    raw_token: str,
    session: Session
) -> tuple[User, str, str, datetime]:

    now = datetime.now(timezone.utc)

    try:
        # --------------------------------------------
        # 1. Hash incoming refresh token.
        # --------------------------------------------

        token_digest = hash_token(raw_token)

        # --------------------------------------------
        # 2. Read refresh token WITHOUT locking.
        # We need its session_id first.
        # --------------------------------------------

        initial_token = session.exec(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_digest
            )
        ).first()

        if initial_token is None:
            raise InvalidRefreshToken(
                "Invalid refresh token."
            )

        session_id = initial_token.session_id

        # --------------------------------------------
        # 3. Lock AuthSession FIRST.
        # --------------------------------------------

        auth_session = session.exec(
            select(AuthSession)
            .where(AuthSession.id == session_id)
            .with_for_update()
        ).first()

        if auth_session is None:
            raise InvalidRefreshToken(
                "Session not found."
            )

        # --------------------------------------------
        # 4. Lock RefreshToken SECOND.
        # Re-fetch after acquiring session lock.
        # --------------------------------------------

        old_token = session.exec(
            select(RefreshToken)
            .where(
                RefreshToken.token_hash == token_digest,
                RefreshToken.session_id == auth_session.id
            )
            .with_for_update()
        ).first()

        if old_token is None:
            raise InvalidRefreshToken(
                "Invalid refresh token."
            )

        # --------------------------------------------
        # 5. Validate session revocation.
        # --------------------------------------------

        if auth_session.revoked_at is not None:
            raise InvalidRefreshToken(
                "Session has been revoked."
            )

        # --------------------------------------------
        # 6. Validate session expiration.
        # --------------------------------------------

        expiration_reason = None

        if auth_session.absolute_expires_at <= now:
            expiration_reason = "absolute_expired"

        elif auth_session.idle_expires_at <= now:
            expiration_reason = "idle_expired"

        if expiration_reason:

            auth_session.revoked_at = now
            auth_session.revocation_reason = expiration_reason

            revoke_active_refresh_tokens(
                auth_session,
                session,
                now
            )

            # Persist session expiration.
            session.commit()

            raise InvalidRefreshToken(
                "Session has expired."
            )

        # --------------------------------------------
        # 7. Detect refresh-token reuse.
        # --------------------------------------------

        if old_token.consumed_at is not None:

            auth_session.revoked_at = now
            auth_session.revocation_reason = (
                "refresh_token_reuse"
            )

            revoke_active_refresh_tokens(
                auth_session,
                session,
                now
            )

            # Persist security action before raising.
            session.commit()

            raise RefreshTokenReuseDetected(
                "Refresh token reuse detected. "
                "Please log in again."
            )

        # --------------------------------------------
        # 8. Validate refresh-token status.
        # --------------------------------------------

        if old_token.revoked_at is not None:
            raise InvalidRefreshToken(
                "Refresh token has been revoked."
            )

        if old_token.expires_at <= now:
            raise InvalidRefreshToken(
                "Refresh token has expired."
            )

        # --------------------------------------------
        # 9. Find and validate user.
        # --------------------------------------------

        user = session.exec(
            select(User).where(
                User.id == auth_session.user_id
            )
        ).first()

        if user is None or not user.is_email_verified:
            raise InvalidRefreshToken(
                "User account is unavailable."
            )

        # --------------------------------------------
        # 10. Consume old refresh token.
        # --------------------------------------------

        old_token.consumed_at = now

        # --------------------------------------------
        # 11. Update session activity.
        # Extend idle expiry but never absolute expiry.
        # --------------------------------------------

        absolute_expiry = auth_session.absolute_expires_at

        auth_session.last_activity_at = now

        auth_session.idle_expires_at = min(
            now + timedelta(
                days=settings.SESSION_IDLE_TIMEOUT_DAYS
            ),
            absolute_expiry
        )

        # --------------------------------------------
        # 12. Generate replacement refresh token.
        # --------------------------------------------

        new_raw_token = generate_secure_token()

        new_token_expiry = min(
            now + timedelta(
                days=settings.REFRESH_TOKEN_EXPIRE_DAYS
            ),
            absolute_expiry
        )

        new_token = RefreshToken(
            session_id=auth_session.id,
            token_hash=hash_token(new_raw_token),
            issued_at=now,
            expires_at=new_token_expiry
        )

        session.add(new_token)

        session.flush()

        # --------------------------------------------
        # 13. Link old token to replacement.
        # --------------------------------------------

        old_token.replaced_by_id = new_token.id

        # --------------------------------------------
        # 14. Generate new access token.
        # Cap expiry at absolute session expiry.
        # --------------------------------------------

        access_token = create_access_token(
            user_id=user.id,
            session_id=auth_session.id,
            expires_at=absolute_expiry
        )

        # --------------------------------------------
        # 15. Commit token rotation atomically.
        # --------------------------------------------

        session.commit()

        return (
            user,
            access_token,
            new_raw_token,
            new_token_expiry
        )

    except RefreshTokenReuseDetected:
        # Revocation was already committed.
        raise

    except InvalidRefreshToken:
        # Some invalid-token branches intentionally
        # commit session revocation before raising.
        raise

    except Exception:
        session.rollback()
        raise

def logout_user(user_id: UUID, session_id: UUID,session: Session):
    now = datetime.now(timezone.utc)

    # 1. Lock the current authentication session.
    auth_session = session.exec(
        select(AuthSession)
        .where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id
        )
        .with_for_update()
    ).first()

    if auth_session is None:
        raise InvalidRefreshToken("Authentication session not found.")

    # 2. Check whether the session is already revoked.
    if auth_session.revoked_at is not None:
        return

    # 3. Revoke the current session.
    auth_session.revoked_at = now
    auth_session.revocation_reason = "logout"

    # 4. Revoke all active refresh tokens.
    revoke_active_refresh_tokens(
        auth_session=auth_session,
        session=session,
        now=now
    )

    # 5. Commit changes.
    session.commit()

def logout_all_devices(
    user_id: UUID,
    session: Session
) -> int:

    now = datetime.now(timezone.utc)

    try:
        # 1. Find all active sessions for the user.
        auth_sessions = session.exec(
            select(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None)
            )
            .order_by(AuthSession.id)
            .with_for_update()
        ).all()

        # 2. Revoke every active session.
        for auth_session in auth_sessions:

            auth_session.revoked_at = now
            auth_session.revocation_reason = "logout_all"

            # 3. Revoke associated active refresh tokens.
            revoke_active_refresh_tokens(
                auth_session=auth_session,
                session=session,
                now=now
            )

        # 4. Commit all changes.
        session.commit()

        return len(auth_sessions)

    except Exception:
        session.rollback()
        raise

@dataclass
class CurrentAuth:
    user: User
    auth_session: AuthSession


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: Session = Depends(get_session)
) -> CurrentAuth:

    # 1. Check whether the Authorization header exists.
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials are missing.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        # 2. Decode and validate the access JWT.
        payload = decode_access_token(credentials.credentials)

        # 3. Extract and validate UUID claims.
        user_id = UUID(payload["sub"])
        session_id = UUID(payload["sid"])

    except (JWTError, ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 4. Get the user from the database.
    user = session.exec(
        select(User).where(User.id == user_id)
    ).first()

    if user is None or not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is unavailable.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 5. Get the corresponding authentication session.
    auth_session = session.exec(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id
        )
    ).first()

    if auth_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication session not found.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 6. Check whether the session has been revoked.
    if auth_session.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has been revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 7. Check idle and absolute session expiry.
    now = datetime.now(timezone.utc)

    if (
        auth_session.idle_expires_at <= now
        or auth_session.absolute_expires_at <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 8. Return authenticated user and session.
    return CurrentAuth(
        user=user,
        auth_session=auth_session
    )


async def forgot_pass_request(email: str, session: Session):
    query = select(User).where(User.email == email)
    user = session.exec(query).first()
    if user is None: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found with this email."
        )
    now = datetime.now(timezone.utc)

    query = select(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.expires_at >= now, PasswordResetToken.consumed_at.is_(None))
    old_reset_tokens = session.exec(query).all()
    for token in old_reset_tokens:
        token.consumed_at=now

    reset_token = generate_secure_token()
    token_hash = hash_token(reset_token)
    new_pass_reset = PasswordResetToken(user_id=user.id,
        token_hash=token_hash, created_at=now, 
        expires_at=now + timedelta(minutes=15))
    session.add(new_pass_reset)
    session.commit()

    await send_password_reset_email(user.email, reset_token)

async def reset_password_requst(token: str, new_password: str, session: Session, device_name: str|None=None):
    
    try: 
        hased_token = hash_token(token)
        hashed_pass = hash_password(new_password)
        now = datetime.now(timezone.utc)
    
        query = select(PasswordResetToken).where(PasswordResetToken.token_hash == hased_token).with_for_update()
        reset_token_entry = session.exec(query).first()
    
        if reset_token_entry is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password reset token."
            )
        if reset_token_entry.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password reset token has expired."
            )
        if reset_token_entry.consumed_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Password reset token has already been used."
            )
    
        query = select(User).where(User.id == reset_token_entry.user_id)
        user = session.exec(query).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        if verify_password(new_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot reuse your current password."
            )
        
        auth_sessions = session.exec(
            select(AuthSession)
            .where(
                AuthSession.user_id == user.id,
                AuthSession.revoked_at.is_(None)
            )
            .order_by(AuthSession.id)
            .with_for_update()
        ).all()

        # 8. Revoke all active sessions and refresh tokens.
        for auth_session in auth_sessions:

            auth_session.revoked_at = now
            auth_session.revocation_reason = "password_reset"

            revoke_active_refresh_tokens(
                auth_session=auth_session,
                session=session,
                now=now
            )

        reset_token_entry.consumed_at = now
        user.password_hash = hashed_pass
    
        session.commit()
    except:
        session.rollback()
        raise

    await send_password_reset_success_email(user.email, device_name)

