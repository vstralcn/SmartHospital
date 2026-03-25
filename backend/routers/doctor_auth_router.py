from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import DoctorUser

router = APIRouter(prefix="/api/doctor/auth")
security = HTTPBearer(auto_error=False)


class DoctorLoginRequest(BaseModel):
    username: str
    password: str


class DoctorUserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    department: str
    is_active: bool


class DoctorLoginResponse(BaseModel):
    token: str
    user: DoctorUserResponse


def get_current_doctor(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> DoctorUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    payload = request.app.state.auth_service.decode_token(credentials.credentials)
    if payload.get("role") != "doctor":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的医生令牌")
    doctor_id = int(payload.get("sub", 0) or 0)
    doctor = db.get(DoctorUser, doctor_id)
    if doctor is None or not doctor.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="医生账号不可用")
    return doctor


@router.post("/login", response_model=DoctorLoginResponse)
def login(body: DoctorLoginRequest, request: Request, db: Session = Depends(get_db)):
    stmt = select(DoctorUser).where(DoctorUser.username == body.username).limit(1)
    doctor = db.scalar(stmt)
    auth_service = request.app.state.auth_service
    if doctor is None or not doctor.is_active or not auth_service.verify_password(body.password, doctor.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = auth_service.create_token(doctor.id, doctor.username, role="doctor")
    return DoctorLoginResponse(
        token=token,
        user=DoctorUserResponse(
            id=doctor.id,
            username=doctor.username,
            full_name=doctor.full_name,
            department=doctor.department,
            is_active=doctor.is_active,
        ),
    )


@router.get("/me", response_model=DoctorUserResponse)
def me(doctor: DoctorUser = Depends(get_current_doctor)):
    return DoctorUserResponse(
        id=doctor.id,
        username=doctor.username,
        full_name=doctor.full_name,
        department=doctor.department,
        is_active=doctor.is_active,
    )


@router.post("/logout")
def logout():
    return {"message": "已退出登录"}
