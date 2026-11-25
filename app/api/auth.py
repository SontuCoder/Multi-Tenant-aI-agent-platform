from fastapi import APIRouter, status, Depends, HTTPException, Response, Request
from sqlmodel import Session
from sqlalchemy.exc import IntegrityError
from uuid import UUID
from datetime import datetime, timezone, timedelta
from core import settings
from database import get_session, User, Tenant, TenantMembership, TenantRole
from models import UserRegister, UserLogin, EmailVerifyToken, ResendEmailTokenRequest, RefreshTokenReuseDetected, InvalidRefreshToken
from auth_services import register_user, verify_email, resend_verification_token, login_user, set_cookie_details, refresh_tokens, revoke_active_refresh_tokens, delete_cookie_details, get_cookie_details

import traceback

route = APIRouter(prefix="/api/auth", tags=["Authentication"])

@route.post("/registration", status_code=status.HTTP_201_CREATED)
async def register_user_route(user: UserRegister, session: Session = Depends(get_session)):
    try:
        user, email_verification_token = await register_user(user, session)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc)
        )

    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or username is already registered."
        )

    except Exception as excp:
        # traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again."
        )
    
    email_sent = True

    return {
        "status": "SUCCESS",
        "message": "Account created. Please verify your email.",
        "verification_email_sent": email_sent,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "is_email_verified": user.is_email_verified
        }
    }

@route.post("/verify-email", status_code=status.HTTP_200_OK)
def verify_email_endpoint(
    request: EmailVerifyToken,
    session: Session = Depends(get_session)
):
    try:
        verify_email(request, session)

        return {
            "status": "SUCCESS",
            "message": "Email verified successfully."
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

@route.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification(
    email_request: ResendEmailTokenRequest,
    session: Session = Depends(get_session)
):
    try:
        user, verification_token = await resend_verification_token(
            email_request.email,
            session
        )

        return {
            "status": "SUCCESS",
            "message": "Verification email sent successfully."
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to process verification request."
        )

@route.post("/login", status_code=status.HTTP_200_OK)
def login(
    user_data: UserLogin,
    request: Request,
    response: Response,
    session: Session = Depends(get_session)
):
    try:
        user, access_token, refresh_token = login_user(
            user_data=user_data,
            session=session,
            device_name=request.headers.get("X-Device-Name"),
            user_agent=request.headers.get("user-agent"),
            ip_address=(
                request.client.host if request.client else None
            )
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc)
        )

    except ValueError as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc)
        )

    except Exception as excp:
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process login."
        )
    set_cookie_details("refresh_token", refresh_token, settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60, "/api/auth", response)

    return {
        "status": "SUCCESS",
        "message": "Login successful.",
        "token_type": "Bearer",
        "access_token": access_token,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username
        }
    }

@route.post("/refresh", status_code=status.HTTP_200_OK)
def get_refresh_token(
    request: Request,
    response: Response,
    session: Session = Depends(get_session)
):

    try:
        # 1. Retrieve refresh token from HttpOnly cookie.
        raw_refresh_token = get_cookie_details(
            cookie_key="refresh_token",
            request=request
        )

        # 2. Validate and rotate refresh token.
        # Returns:
        # (user, access_token, new_refresh_token, expiry)
        refresh_data = refresh_tokens(
            raw_token=raw_refresh_token,
            session=session
        )

        user = refresh_data[0]
        access_token = refresh_data[1]
        new_refresh_token = refresh_data[2]
        refresh_expires_at = refresh_data[3]

        # 3. Calculate remaining refresh-token lifetime.
        now = datetime.now(timezone.utc)

        max_token_age = max(
            0,
            int((refresh_expires_at - now).total_seconds())
        )

        # 4. Set replacement refresh-token cookie.
        set_cookie_details(
            key="refresh_token",
            value=new_refresh_token,
            max_age=max_token_age,
            path="/api/auth",
            response=response
        )

        # 5. Return new access token.
        return {
            "status": "SUCCESS",
            "message": "Refresh successful.",
            "token_type": "bearer",
            "access_token": access_token,
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "username": user.username
            }
        }

    except RefreshTokenReuseDetected as exc:

        delete_cookie_details(
            key="refresh_token",
            path="/api/auth",
            response=response
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc)
        )

    except InvalidRefreshToken as exc:
        delete_cookie_details(
            key="refresh_token",
            path="/api/auth",
            response=response
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc)
        )

    except HTTPException:
        raise

    except Exception as exc:
        session.rollback()
        print(f"Unexpected refresh error: {exc}")
        traceback.print_exc()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process refresh request."
        )

