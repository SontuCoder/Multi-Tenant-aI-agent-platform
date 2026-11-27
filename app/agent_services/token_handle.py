from fastapi import HTTPException, status
from models import APITokenResponse, APITokenCreated, APITokenCreate
from database import User, Tenant, TenantMembership, TenantRole, KnowledgeBase, AgentAPIToken
from sqlmodel import Session, select
from uuid import UUID
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
    except:
        session.rollback()
        raise

def get_all_agent_tokens(user: User, tenant_id: UUID, knowledge_id: UUID, session: Session)-> list[APITokenResponse]:
    try:
        pass
    except:
        session.rollback()
        raise