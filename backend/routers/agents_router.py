from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from database import get_db
from services.agent_log_service import AgentLogService

router = APIRouter(prefix="/api/agents", tags=["agents"])


# Static description of the collaboration pipeline, consumed by the frontend
# Agent Monitor to render the flowchart skeleton even before any run exists.
_PIPELINE = [
    {
        "name": "interview_agent",
        "label": "问诊采集",
        "description": "从 ASR 转写中提取主诉、症状与既往史",
    },
    {
        "name": "diagnosis_agent",
        "label": "诊断推理",
        "description": "结合疾病知识库生成候选疾病与推理",
    },
    {
        "name": "drug_agent",
        "label": "用药推荐",
        "description": "推荐药物并通过 MCP 工具检查禁忌",
    },
    {
        "name": "emr_agent",
        "label": "病历整合",
        "description": "汇总各智能体输出生成结构化病历",
    },
    {
        "name": "quality_control_agent",
        "label": "质控审核",
        "description": "审核病历完整性与逻辑一致性",
    },
]


@router.get("/pipeline")
def get_pipeline() -> dict:
    return {"pipeline": _PIPELINE}


@router.get("/servers")
def list_mcp_servers(request: Request) -> dict:
    registry: Any = getattr(request.app.state, "mcp_registry", None)
    if registry is None:
        return {"servers": []}
    return {"servers": registry.list_servers()}


@router.get("/runs")
def list_runs(limit: int = 20, db: Session = Depends(get_db)) -> dict:
    return {"runs": AgentLogService(db).list_recent_tasks(limit=limit)}


@router.get("/runs/latest")
def latest_run(db: Session = Depends(get_db)) -> dict:
    service = AgentLogService(db)
    task_id = service.latest_task()
    if not task_id:
        return {"task_id": "", "pipeline": _PIPELINE, "logs": []}
    return {
        "task_id": task_id,
        "pipeline": _PIPELINE,
        "logs": service.list_by_task(task_id),
    }


@router.get("/runs/session/{session_id}")
def run_by_session(session_id: str, db: Session = Depends(get_db)) -> dict:
    service = AgentLogService(db)
    task_id = service.latest_task_for_session(session_id)
    if not task_id:
        return {"task_id": "", "pipeline": _PIPELINE, "logs": []}
    return {
        "task_id": task_id,
        "pipeline": _PIPELINE,
        "logs": service.list_by_task(task_id),
    }


@router.get("/runs/{task_id}")
def run_by_task(task_id: str, db: Session = Depends(get_db)) -> dict:
    return {
        "task_id": task_id,
        "pipeline": _PIPELINE,
        "logs": AgentLogService(db).list_by_task(task_id),
    }
