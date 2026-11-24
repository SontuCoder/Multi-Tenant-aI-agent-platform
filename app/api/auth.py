from fastapi import APIRouter, status, Depends, HTTPException
from sqlmodel import Session
from uuid import UUID
from database import get_session, User, Tenant, TenantMembership, TenantRole
from models import *

route = APIRouter(prefix="/api/auth", tags=["Auth"])





