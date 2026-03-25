from __future__ import annotations

import io
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models.emr import StructuredEMR
from models.report import ExportPayload

router = APIRouter()


class ExportRequest(BaseModel):
    session_id: str
    emr_text: str = ""
    emr_html: str = ""


@router.post("/docx")
async def export_docx(body: ExportRequest, request: Request):
    session = request.app.state.sessions.get(body.session_id, {})
    export_svc: Any = request.app.state.export_service

    structured_data = session.get("structured", {})
    structured = StructuredEMR.model_validate(structured_data) if structured_data else StructuredEMR()

    payload = ExportPayload(
        transcript=session.get("dialogues", []),
        structured=structured,
        emr_text=body.emr_text or session.get("emr_text", ""),
        emr_html=body.emr_html,
        risk_alerts=session.get("risk_alerts", []),
    )

    output_path = export_svc.export_docx(payload)
    file_bytes = output_path.read_bytes()

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={output_path.name}"},
    )


@router.post("/json")
async def export_json(body: ExportRequest, request: Request):
    session = request.app.state.sessions.get(body.session_id, {})

    structured_data = session.get("structured", {})
    structured = StructuredEMR.model_validate(structured_data) if structured_data else StructuredEMR()

    payload = ExportPayload(
        transcript=session.get("dialogues", []),
        structured=structured,
        emr_text=body.emr_text or session.get("emr_text", ""),
        emr_html=body.emr_html,
        risk_alerts=session.get("risk_alerts", []),
    )

    return payload.model_dump()
