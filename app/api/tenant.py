from fastapi import APIRouter, status, Depends, HTTPException, Query
from sqlmodel import Session
from uuid import UUID
from database import get_session
from models import TenantDetails, TenantCreate, TenantResponse, TenantWholeDetails, InviteNewUser
from tenant_service import get_user_tenants, create_tenant, select_tenant, invite_user, get_all_tenant_users, delete_tenant_member
from auth_services import CurrentAuth, get_current_user

import traceback


route = APIRouter(prefix="/api/tenant", tags=["Tenant"])

@route.get("", response_model=list[TenantDetails], status_code=status.HTTP_200_OK)
def get_tenants(current_auth: CurrentAuth = Depends(get_current_user), session: Session = Depends(get_session)):
    try:
        tenants=get_user_tenants(current_auth.user, session)
        return tenants
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to get Tenants."
        )

@route.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_new_tenant(new_tenant_details: TenantCreate, current_auth: CurrentAuth = Depends(get_current_user), session: Session = Depends(get_session)):
    try:
        new_tenant, new_tenant_relation = create_tenant(current_auth.user, new_tenant_details.name, session)
        return new_tenant
    
    except ValueError as excp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(excp)
        )
    
    except HTTPException:
        raise

    except Exception:
        session.rollback()
        # traceback.print_exc()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create Tenants."
        )

@route.get("/{tenant_id}/select", response_model=TenantWholeDetails, status_code=status.HTTP_200_OK)
def get_tenant_details(tenant_id: UUID, current_auth: CurrentAuth = Depends(get_current_user), session: Session = Depends(get_session)):
    try:
        return select_tenant(current_auth.user, tenant_id, session)

    except HTTPException:
        raise

    except Exception:
        traceback.print_exc()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to get Tenant details."
        )


@route.post("/{tenant_id}/invite", status_code=status.HTTP_201_CREATED)
def invite_or_edit_user_role(tenant_id: UUID, new_user: InviteNewUser,  current_auth: CurrentAuth = Depends(get_current_user), session: Session = Depends(get_session)):
    try:
        invite_user(current_auth.user, tenant_id, session, new_user.email, new_user.access_role)
        return {
            "status": "SUCCESS",
            "message": "New user added to this tenant."
        }
    except HTTPException:
        raise

    except Exception:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to get Tenant details."
        )


@route.get("/{tenant_id}/users", status_code=status.HTTP_200_OK)
def get_all_tenant_members(tenant_id: UUID, current_auth: CurrentAuth = Depends(get_current_user), session: Session = Depends(get_session)):
    try:
        return get_all_tenant_users(current_auth.user, tenant_id, session)
    except HTTPException:
            raise
    
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to get Tenant details."
        )

@route.delete("/{tenant_id}/delete", status_code=status.HTTP_200_OK)
def get_all_tenant_members(tenant_id: UUID, member: UUID = Query(), current_auth: CurrentAuth = Depends(get_current_user), session: Session = Depends(get_session)):
    try:
        delete_tenant_member(current_auth.user, member, tenant_id, session)
        return {
            "status":"SUCCESS",
            "message": "Member delete successfully."
        }
    except HTTPException:
            raise
    except Exception:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to get Tenant details."
        )


