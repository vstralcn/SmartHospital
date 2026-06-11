from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database import get_db
from models import ConsultationRecord, DoctorUser
from routers.admin_auth_router import get_current_admin

router = APIRouter(
    prefix="/api/admin/consultations",
    dependencies=[Depends(get_current_admin)],
)


def _doctor_label(doctor: DoctorUser | None) -> tuple[str, str]:
    if doctor is None:
        return "未知医生", ""
    return doctor.full_name or doctor.username, doctor.department or ""


@router.get("")
def list_all_consultations(
    page: int = 1,
    page_size: int = 20,
    doctor_id: int | None = None,
    q: str = "",
    db: Session = Depends(get_db),
):
    offset = (max(page, 1) - 1) * page_size
    base = select(ConsultationRecord)
    if doctor_id is not None:
        base = base.where(ConsultationRecord.doctor_id == doctor_id)
    keyword = q.strip()
    if keyword:
        like = f"%{keyword}%"
        base = base.where(
            or_(
                ConsultationRecord.patient_name.like(like),
                ConsultationRecord.emr_text.like(like),
                ConsultationRecord.session_id.like(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    stmt = (
        base.order_by(ConsultationRecord.created_at.desc(), ConsultationRecord.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    records = list(db.scalars(stmt))
    doctor_ids = {r.doctor_id for r in records}
    doctors = {
        d.id: d
        for d in db.scalars(select(DoctorUser).where(DoctorUser.id.in_(doctor_ids)))
    } if doctor_ids else {}

    items = []
    for r in records:
        name, department = _doctor_label(doctors.get(r.doctor_id))
        preview = r.emr_text[:80] + "..." if len(r.emr_text) > 80 else r.emr_text
        items.append({
            "id": r.id,
            "session_id": r.session_id,
            "patient_name": r.patient_name,
            "doctor_id": r.doctor_id,
            "doctor_name": name,
            "department": department,
            "status": r.status,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
            "emr_text_preview": preview,
        })
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/stats")
def consultation_stats(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(ConsultationRecord)) or 0
    doctor_count = db.scalar(
        select(func.count(func.distinct(ConsultationRecord.doctor_id)))
    ) or 0
    return {"total": total, "doctor_count": doctor_count}


@router.get("/{record_id}")
def get_any_consultation(record_id: int, db: Session = Depends(get_db)):
    record = db.get(ConsultationRecord, record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记录不存在")
    name, department = _doctor_label(db.get(DoctorUser, record.doctor_id))
    return {
        "id": record.id,
        "session_id": record.session_id,
        "patient_name": record.patient_name,
        "doctor_id": record.doctor_id,
        "doctor_name": name,
        "department": department,
        "status": record.status,
        "dialogues": json.loads(record.dialogues),
        "structured": json.loads(record.structured) if record.structured else None,
        "emr_text": record.emr_text,
        "risk_alerts": json.loads(record.risk_alerts),
        "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S") if record.created_at else "",
    }


@router.delete("/{record_id}")
def delete_any_consultation(record_id: int, db: Session = Depends(get_db)):
    record = db.get(ConsultationRecord, record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记录不存在")
    db.delete(record)
    db.commit()
    return {"message": "记录已删除"}
