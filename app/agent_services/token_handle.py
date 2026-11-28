from fastapi import HTTPException, status
from models import APITokenResponse, APITokenCreated, APITokenCreate
from database import User, TenantMembership, TenantRole, KnowledgeBase, AgentAPIToken
from sqlmodel import Session, select
from uuid import UUID
import hmac
from datetime import datetime, timezone, timedelta
from tenant_service import user_has_tenant_access
from core import hash_token, generate_secure_token, settings


now = datetime.now(timezone.utc)

def create_new_agent_token(user: User, name:str, tenant_id: UUID, knowledge_id: UUID, session: Session)-> APITokenCreated:
    try:
        user_has_tenant_access(user.id, tenant_id, session)
        knowledge = session.exec(select(KnowledgeBase).where(KnowledgeBase.id==knowledge_id, KnowledgeBase.tenant_id==tenant_id)).first()
        if knowledge is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge not found."
            )

        if not knowledge.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Knowledge is deactivate. You can't make or use AI for this knowledge."
            )

        new_raw_token = generate_secure_token()
        new_hash_token = hash_token(new_raw_token)
        token_prefix = new_raw_token[0:6] + "*"*6 + new_raw_token[-6:]

        new_ai_token_details = AgentAPIToken(
            user_id=user.id,
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_id,
            name = name,
            token_prefix=token_prefix,
            token_hash=new_hash_token,
            expires_at= now + timedelta(days=settings.AGENT_TOKEN_EXPIRE_DAYS),
            created_at=now
        )
        session.add(new_ai_token_details)
        session.commit()
        session.refresh(new_ai_token_details)
        return APITokenCreated(new_ai_token_details.model_dump(), token=new_raw_token, url=settings.AGENT_URL)
    except Exception:
        session.rollback()
        raise

def get_all_agent_tokens(user: User, tenant_id: UUID, knowledge_id: UUID, session: Session)-> list[APITokenResponse]:
    user_role = user_has_tenant_access(user.id, tenant_id, session)
    knowledge = session.exec(select(KnowledgeBase).where(KnowledgeBase.id==knowledge_id, KnowledgeBase.tenant_id==tenant_id)).first()
    if knowledge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge not found."
        )
    
    query = select(AgentAPIToken, User, TenantMembership).join(User, AgentAPIToken.user_id==User.id).join(TenantMembership, (TenantMembership.user_id == User.id) & (TenantMembership.tenant_id==tenant_id))
    if user_role == TenantRole.ADMIN:
        query = query.where(AgentAPIToken.tenant_id == tenant_id, AgentAPIToken.knowledge_base_id==knowledge_id, AgentAPIToken.revoked_at.is_(None), AgentAPIToken.expires_at> now)
    else:
        query = query.where(AgentAPIToken.tenant_id == tenant_id, AgentAPIToken.knowledge_base_id==knowledge_id, AgentAPIToken.user_id == user.id, AgentAPIToken.revoked_at.is_(None), AgentAPIToken.expires_at> now)
    tokens = session.exec(query).all()
    tokens_response = [
        APITokenResponse(
            id = token.id,
            name = token.name,
            user_id=token_user.id,
            user_name=token_user.username,
            user_email=token_user.email,
            user_role=user_role.role,
            tenant_id=token.tenant_id,
            knowledge_base_id=token.knowledge_base_id,
            token_prefix=token.token_prefix,
            expires_at=token.expires_at,
            created_at=token.created_at
        ) 
        for token, token_user, user_role in tokens
    ]
    return tokens_response

def delete_agent_token(user: User, token_id: UUID, tenant_id: UUID, knowledge_id: UUID, session: Session):
    try:
        user_role = user_has_tenant_access(user.id, tenant_id, session)
        knowledge = session.exec(select(KnowledgeBase).where(KnowledgeBase.id==knowledge_id, KnowledgeBase.tenant_id==tenant_id)).first()
        if knowledge is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge not found."
            )

        query = select(AgentAPIToken).where( AgentAPIToken.id== token_id, AgentAPIToken.tenant_id==tenant_id, AgentAPIToken.knowledge_base_id==knowledge_id, AgentAPIToken.revoked_at.is_(None))
        if user_role != TenantRole.ADMIN:
            query = query.where(AgentAPIToken.user_id==user.id)

        token = session.exec(query).first()
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API token not found."
            )

        token.revoked_at = now
        session.add(token)
        session.commit()
    except Exception:
        session.rollback()
        raise


def get_current_api_token(
    raw_token: str,
    session: Session
) -> AgentAPIToken:

    # 1. Validate input
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API token is required."
        )

    # 2. Hash the incoming token
    incoming_hash = hash_token(raw_token)

    # 3. Retrieve token record
    token = session.exec(
        select(AgentAPIToken).where(
            AgentAPIToken.token_hash == incoming_hash
        )
    ).first()

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token."
        )

    # 4. Constant-time hash comparison
    if not hmac.compare_digest(
        token.token_hash,
        incoming_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token."
        )

    # 5. Check whether token was already revoked
    if token.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API token has been revoked."
        )

    # 6. Check expiry
    if token.expires_at is not None and token.expires_at <= now:

        try:
            token.revoked_at = now
            session.add(token)
            session.commit()
        except Exception:
            session.rollback()
            raise

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API token has expired."
        )

    # 7. Validate tenant membership
    membership = session.exec(
        select(TenantMembership).where(
            TenantMembership.user_id == token.user_id,
            TenantMembership.tenant_id == token.tenant_id
        )
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User no longer belongs to this tenant."
        )

    # 8. Validate knowledge base
    knowledge = session.exec(
        select(KnowledgeBase).where(
            KnowledgeBase.id == token.knowledge_base_id,
            KnowledgeBase.tenant_id == token.tenant_id
        )
    ).first()

    if knowledge is None or not knowledge.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Knowledge base is unavailable."
        )

    # 9. Update last used timestamp
    try:
        token.last_used_at = now
        session.add(token)
        session.commit()
        session.refresh(token)

    except Exception:
        session.rollback()
        raise

    return token

