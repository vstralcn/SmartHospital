from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import DoctorUser
from routers.admin_auth_router import get_current_admin

router = APIRouter(prefix="/api/admin/doctors", dependencies=[Depends(get_current_admin)])


class DoctorCreateRequest(BaseModel):
    username: str
    password: str | None = None
    full_name: str
    department: str = ""
    is_active: bool = True


class DoctorUpdateRequest(BaseModel):
    username: str
    full_name: str
    department: str = ""
    is_active: bool = True
    password: str | None = None


@router.get("")
def list_doctors(db: Session = Depends(get_db)):
    stmt = select(DoctorUser).order_by(DoctorUser.created_at.desc(), DoctorUser.id.desc())
    doctors = list(db.scalars(stmt))
    return [
        {
            "id": doctor.id,
            "username": doctor.username,
            "full_name": doctor.full_name,
            "department": doctor.department,
            "is_active": doctor.is_active,
            "created_at": doctor.created_at,
        }
        for doctor in doctors
    ]


@router.post("")
def create_doctor(body: DoctorCreateRequest, request: Request, db: Session = Depends(get_db)):
    existing = db.scalar(select(DoctorUser).where(DoctorUser.username == body.username).limit(1))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
    password = body.password or secrets.token_urlsafe(8)
    auth_service = request.app.state.auth_service
    doctor = DoctorUser(
        username=body.username,
        password_hash=auth_service.hash_password(password),
        full_name=body.full_name,
        department=body.department,
        is_active=body.is_active,
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return {
        "id": doctor.id,
        "username": doctor.username,
        "full_name": doctor.full_name,
        "department": doctor.department,
        "is_active": doctor.is_active,
        "created_at": doctor.created_at,
        "generated_password": None if body.password else password,
    }


@router.put("/{doctor_id}")
def update_doctor(doctor_id: int, body: DoctorUpdateRequest, request: Request, db: Session = Depends(get_db)):
    doctor = db.get(DoctorUser, doctor_id)
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="医生账号不存在")
    duplicate = db.scalar(
        select(DoctorUser).where(DoctorUser.username == body.username, DoctorUser.id != doctor_id).limit(1)
    )
    if duplicate is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
    doctor.username = body.username
    doctor.full_name = body.full_name
    doctor.department = body.department
    doctor.is_active = body.is_active
    if body.password:
        doctor.password_hash = request.app.state.auth_service.hash_password(body.password)
    db.commit()
    db.refresh(doctor)
    return {
        "id": doctor.id,
        "username": doctor.username,
        "full_name": doctor.full_name,
        "department": doctor.department,
        "is_active": doctor.is_active,
        "created_at": doctor.created_at,
    }


@router.post("/{doctor_id}/enable")
def enable_doctor(doctor_id: int, enabled: bool, db: Session = Depends(get_db)):
    doctor = db.get(DoctorUser, doctor_id)
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="医生账号不存在")
    doctor.is_active = enabled
    db.commit()
    db.refresh(doctor)
    return {
        "id": doctor.id,
        "username": doctor.username,
        "full_name": doctor.full_name,
        "department": doctor.department,
        "is_active": doctor.is_active,
        "created_at": doctor.created_at,
    }


@router.post("/{doctor_id}/reset-password")
def reset_doctor_password(doctor_id: int, request: Request, db: Session = Depends(get_db)):
    doctor = db.get(DoctorUser, doctor_id)
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="医生账号不存在")
    new_password = secrets.token_urlsafe(8)
    doctor.password_hash = request.app.state.auth_service.hash_password(new_password)
    db.commit()
    return {"message": "密码已重置", "password": new_password}
