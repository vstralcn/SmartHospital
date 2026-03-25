from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import Admin

router = APIRouter(prefix="/api/admin/auth")
security = HTTPBearer(auto_error=False)


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminUserResponse(BaseModel):
    id: int
    username: str
    is_active: bool


class AdminLoginResponse(BaseModel):
    token: str
    user: AdminUserResponse


def get_current_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> Admin:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    payload = request.app.state.auth_service.decode_token(credentials.credentials)
    admin_id = int(payload.get("sub", 0) or 0)
    admin = db.get(Admin, admin_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员不可用")
    return admin


@router.post("/login", response_model=AdminLoginResponse)
def login(body: AdminLoginRequest, request: Request, db: Session = Depends(get_db)):
    stmt = select(Admin).where(Admin.username == body.username).limit(1)
    admin = db.scalar(stmt)
    auth_service = request.app.state.auth_service
    if admin is None or not admin.is_active or not auth_service.verify_password(body.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = auth_service.create_token(admin.id, admin.username)
    return AdminLoginResponse(
        token=token,
        user=AdminUserResponse(id=admin.id, username=admin.username, is_active=admin.is_active),
    )


@router.get("/me", response_model=AdminUserResponse)
def me(admin: Admin = Depends(get_current_admin)):
    return AdminUserResponse(id=admin.id, username=admin.username, is_active=admin.is_active)


@router.post("/logout")
def logout():
    return {"message": "已退出登录"}
