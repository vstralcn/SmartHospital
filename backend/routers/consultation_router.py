from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_db
from models import ConsultationRecord, DoctorUser
from routers.doctor_auth_router import get_current_doctor

router = APIRouter(prefix="/api/consultations", dependencies=[Depends(get_current_doctor)])


class SaveConsultationRequest(BaseModel):
    session_id: str
    patient_name: str = ""


class ConsultationListItem(BaseModel):
    id: int
    session_id: str
    patient_name: str
    status: str
    created_at: str
    emr_text_preview: str


class ConsultationDetail(BaseModel):
    id: int
    session_id: str
    patient_name: str
    status: str
    dialogues: list
    structured: dict | None
    emr_text: str
    risk_alerts: list
    created_at: str


@router.get("")
def list_consultations(
    page: int = 1,
    page_size: int = 20,
    doctor: DoctorUser = Depends(get_current_doctor),
    db: Session = Depends(get_db),
):
    offset = (max(page, 1) - 1) * page_size
    base = select(ConsultationRecord).where(ConsultationRecord.doctor_id == doctor.id)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    stmt = base.order_by(ConsultationRecord.created_at.desc()).offset(offset).limit(page_size)
    records = list(db.scalars(stmt))
    items = []
    for r in records:
        preview = r.emr_text[:80] + "..." if len(r.emr_text) > 80 else r.emr_text
        items.append(ConsultationListItem(
            id=r.id,
            session_id=r.session_id,
            patient_name=r.patient_name,
            status=r.status,
            created_at=r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
            emr_text_preview=preview,
        ))
    return {"total": total, "page": page, "page_size": page_size, "items": [item.model_dump() for item in items]}


@router.get("/{record_id}")
def get_consultation(
    record_id: int,
    doctor: DoctorUser = Depends(get_current_doctor),
    db: Session = Depends(get_db),
):
    record = db.get(ConsultationRecord, record_id)
    if record is None or record.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记录不存在")
    return ConsultationDetail(
        id=record.id,
        session_id=record.session_id,
        patient_name=record.patient_name,
        status=record.status,
        dialogues=json.loads(record.dialogues),
        structured=json.loads(record.structured) if record.structured else None,
        emr_text=record.emr_text,
        risk_alerts=json.loads(record.risk_alerts),
        created_at=record.created_at.strftime("%Y-%m-%d %H:%M:%S") if record.created_at else "",
    ).model_dump()


@router.post("")
def save_consultation(
    body: SaveConsultationRequest,
    request: Request,
    doctor: DoctorUser = Depends(get_current_doctor),
    db: Session = Depends(get_db),
):
    sessions: dict = request.app.state.sessions
    session = sessions.get(body.session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在或已过期")

    dialogues_data = session.get("dialogues", [])
    serialized_dialogues = []
    for d in dialogues_data:
        if hasattr(d, "model_dump"):
            serialized_dialogues.append(d.model_dump())
        elif isinstance(d, dict):
            serialized_dialogues.append(d)

    record = ConsultationRecord(
        doctor_id=doctor.id,
        session_id=body.session_id,
        dialogues=json.dumps(serialized_dialogues, ensure_ascii=False),
        structured=json.dumps(session.get("structured") or {}, ensure_ascii=False),
        emr_text=session.get("emr_text", ""),
        risk_alerts=json.dumps(session.get("risk_alerts", []), ensure_ascii=False),
        status=session.get("status", "done"),
        patient_name=body.patient_name,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "message": "问诊记录已保存",
    }


@router.delete("/{record_id}")
def delete_consultation(
    record_id: int,
    doctor: DoctorUser = Depends(get_current_doctor),
    db: Session = Depends(get_db),
):
    record = db.get(ConsultationRecord, record_id)
    if record is None or record.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记录不存在")
    db.delete(record)
    db.commit()
    return {"message": "记录已删除"}
