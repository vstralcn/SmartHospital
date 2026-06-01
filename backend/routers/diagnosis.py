from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from models.dialogue import DialogueSegment

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class StartRequest(BaseModel):
    doctor_id: Optional[int] = None


class StartResponse(BaseModel):
    session_id: str
    message: str


class TranscribeRequest(BaseModel):
    session_id: str
    dialogues: List[Dict[str, Any]]


class CompleteRequest(BaseModel):
    session_id: str


class GenerateEMRRequest(BaseModel):
    session_id: str


class FollowUpResponse(BaseModel):
    suggestions: List[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_session(request: Request, session_id: str) -> dict:
    sessions: dict = request.app.state.sessions
    if session_id not in sessions:
        sessions[session_id] = {
            "dialogues": [],
            "structured": None,
            "emr_text": "",
            "risk_alerts": [],
            "status": "idle",
        }
    return sessions[session_id]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/start", response_model=StartResponse)
async def start_diagnosis(request: Request, body: StartRequest = None):
    if body is None:
        body = StartRequest()
    session_id = uuid.uuid4().hex[:12]
    request.app.state.sessions[session_id] = {
        "dialogues": [],
        "structured": None,
        "emr_text": "",
        "risk_alerts": [],
        "status": "recording",
        "doctor_id": body.doctor_id,
    }
    return StartResponse(session_id=session_id, message="诊断会话已开始")


@router.post("/transcribe")
async def transcribe(body: TranscribeRequest, request: Request):
    session = _get_session(request, body.session_id)
    diarization = request.app.state.diarization_service

    segments = [DialogueSegment.model_validate(d) for d in body.dialogues]
    labeled = diarization.assign_roles(segments)
    session["dialogues"].extend(labeled)

    return {
        "session_id": body.session_id,
        "dialogues": [seg.model_dump() for seg in session["dialogues"]],
    }


@router.post("/complete")
async def complete_diagnosis(body: CompleteRequest, request: Request):
    session = _get_session(request, body.session_id)
    orchestrator: Any = request.app.state.orchestrator

    dialogues = session["dialogues"]
    if not dialogues:
        session["status"] = "done"
        return {
            "session_id": body.session_id,
            "structured": None,
            "emr_text": "",
            "risk_alerts": [],
            "dialogues": [],
        }

    # Run the multi-agent pipeline in a thread pool to avoid blocking the event
    # loop (which would stall WebSocket audio forwarding).
    result = await asyncio.to_thread(
        orchestrator.build_full_result, dialogues, body.session_id
    )
    session["structured"] = result.structured.model_dump()
    session["emr_text"] = result.emr_text
    session["risk_alerts"] = result.risk_alerts
    session["status"] = "done"

    return {
        "session_id": body.session_id,
        "structured": result.structured.model_dump(),
        "emr_text": result.emr_text,
        "risk_alerts": result.risk_alerts,
        "dialogues": [seg.model_dump() for seg in dialogues],
    }


@router.post("/generate-emr")
async def generate_emr(body: GenerateEMRRequest, request: Request):
    session = _get_session(request, body.session_id)
    orchestrator: Any = request.app.state.orchestrator

    dialogues = session["dialogues"]
    if not dialogues:
        return {"error": "没有对话记录，请先开始诊断"}

    # Run the multi-agent pipeline in a thread pool to avoid blocking the event loop
    result = await asyncio.to_thread(
        orchestrator.build_full_result, dialogues, body.session_id
    )
    session["structured"] = result.structured.model_dump()
    session["emr_text"] = result.emr_text
    session["risk_alerts"] = result.risk_alerts

    return {
        "session_id": body.session_id,
        "structured": result.structured.model_dump(),
        "emr_text": result.emr_text,
        "risk_alerts": result.risk_alerts,
    }


@router.get("/follow-up", response_model=FollowUpResponse)
async def follow_up(session_id: str, request: Request):
    session = _get_session(request, session_id)
    emr_svc: Any = request.app.state.emr_service

    structured_data = session.get("structured")
    if not structured_data:
        return FollowUpResponse(suggestions=[])

    from models.emr import StructuredEMR
    structured = StructuredEMR.model_validate(structured_data)
    suggestions = await asyncio.to_thread(emr_svc.build_follow_up_questions, structured)
    return FollowUpResponse(suggestions=suggestions)
