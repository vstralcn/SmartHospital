from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.admin import Base, TimestampMixin


class ConsultationRecord(Base, TimestampMixin):
    __tablename__ = "consultation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doctor_id: Mapped[int] = mapped_column(Integer, ForeignKey("doctor_users.id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dialogues: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    structured: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    emr_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    risk_alerts: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="done", nullable=False)
    patient_name: Mapped[str] = mapped_column(String(128), default="", nullable=False)
