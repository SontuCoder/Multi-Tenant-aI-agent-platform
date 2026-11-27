from sqlmodel import Session, select
from uuid import UUID
from database import User, Tenant, TenantMembership, TenantRole, KnowledgeBase
from datetime import datetime, timezone
from models import TenantDetails, TenantWholeDetails, UserDetails, KnowledgeResponse
from fastapi import HTTPException, status

now = datetime.now(timezone.utc)

def user_has_tenant_access(user_id:UUID, tenant_id:UUID, session: Session)-> TenantMembership:
    membership = session.exec(select(TenantMembership).where(TenantMembership.tenant_id==tenant_id, TenantMembership.user_id==user_id)).first()
    if membership is None: 
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorize to access the tenant."
        )
    return membership.role

def get_user_tenants(
    user: User,
    session: Session
) -> list[TenantDetails]:

    statement = (
        select(
            TenantMembership.tenant_id,
            TenantMembership.role,
            Tenant.name
        )
        .join(
            Tenant,
            Tenant.id == TenantMembership.tenant_id
        )
        .where(
            TenantMembership.user_id == user.id
        )
    )

    results = session.exec(statement).all()

    return [
        TenantDetails(
            tenant_id=tenant_id,
            role=role,
            name=name
        )
        for tenant_id, role, name in results
    ]

def create_tenant(user: User, tenant_name: str, session: Session):
    try:
        old_tenant = session.exec( select(Tenant).where(Tenant.name == tenant_name)).first()
    
        if old_tenant is not None:
            raise ValueError("Tenant with this name already exist.")
    
        new_tenant = Tenant(name = tenant_name, created_by=user.id)
        session.add(new_tenant)
        session.flush()
    
        new_tenant_member = TenantMembership(tenant_id=new_tenant.id, user_id=user.id, role=TenantRole.ADMIN)
        session.add(new_tenant_member)
        session.commit()

        session.refresh(new_tenant)
        session.refresh(new_tenant_member)

        return new_tenant, new_tenant_member

    except:
        session.rollback()
        raise

def select_tenant(user: User, tenant_id: UUID, session: Session) -> TenantWholeDetails:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found."
        )
    
    tenant_permission = session.exec(select(TenantMembership).where(TenantMembership.tenant_id==tenant_id, TenantMembership.user_id == user.id)).first()
    if tenant_permission is None: 
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorize to get tenant details."
        )
    
    projects = session.exec(select(KnowledgeBase).where(KnowledgeBase.tenant_id==tenant_id)).all()
    tenant_details = TenantWholeDetails(
        tenant_id=tenant.id, 
        tenant_name=tenant.name,
        tenant_relation=tenant_permission.role,
        user=UserDetails(user_id=user.id, name= user.username),
        projects=[ KnowledgeResponse(
            id=knowledge.id,
            name=knowledge.name,
            tenant_id=knowledge.tenant_id,
            description=knowledge.description,
            is_active=knowledge.is_active,
            created_at=knowledge.created_at, 
            updated_at=knowledge.updated_at
        ) 
        for knowledge in projects
        ] 
    )
    return tenant_details

def invite_user(user: User, tenant_id: UUID, session: Session, new_user_email: str, user_role: TenantRole):
    try:

        if user_role==TenantRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin role can't be assigned through invitation."
            )
        if(user.email == new_user_email.strip().lower()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You can't add your self."
            )
        
        tenant = session.get(Tenant, tenant_id)
        if tenant is None: 
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found."
            )
        
        tenant_permission = session.exec(select(TenantMembership).where(TenantMembership.tenant_id==tenant_id, TenantMembership.user_id == user.id)).first()
        if tenant_permission is None: 
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorize to add tenant user."
            )
        
        if tenant_permission.role != TenantRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorize to add new user in this tenant."
            )
        
        user_exist = session.exec(select(User).where(User.email==new_user_email.strip().lower())).first()
        
        if user_exist is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found with this email."
            )
        if not user_exist.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User must verify their email before joining a tenant."
            )
        
        user_added_tenant = session.exec(select(TenantMembership).where(TenantMembership.tenant_id==tenant_id, TenantMembership.user_id == user_exist.id)).first()

        if user_added_tenant is None: 
            user_added_tenant = TenantMembership(tenant_id=tenant_id, user_id=user_exist.id, role=user_role)
            session.add(user_added_tenant)
        else:
            if user_added_tenant.role == user_role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User already has this role."
                )
            user_added_tenant.role = user_role
        session.commit()
        session.refresh(user_added_tenant)
    except:
        session.rollback()
        raise

def get_all_tenant_users(user:User, tenant_id: UUID, session: Session):
    tenant_role = user_has_tenant_access(user.id, tenant_id, session)
    users = session.exec(select(
        User.id, User.username, User.email, TenantMembership.role
    ).join(User, TenantMembership.user_id==User.id).where(TenantMembership.tenant_id==tenant_id)).all()

    return [
        {
            "user_id": user[0],
            "user_name": user[1],
            "user_email": user[2],
            "tenant_role": user[3]
        }for user in users
    ]

def delete_tenant_member(user:User, member_id: UUID, tenant_id: UUID, session: Session):
    try:
        if user.id == member_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You didn't remove your self."
            )
        tenant_exist = session.get(Tenant, tenant_id)
        if tenant_exist is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant is not found."
            )

        tenant_role = user_has_tenant_access(user.id, tenant_id, session)
        if tenant_role != TenantRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You didn't have access to remove user."
            )

        membership = session.exec(select(TenantMembership).where(TenantMembership.tenant_id==tenant_id, TenantMembership.user_id==member_id)).first()
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant member not found."
            )
        
        session.delete(membership)
        session.commit()
    except Exception:
        session.rollback()
        raise

