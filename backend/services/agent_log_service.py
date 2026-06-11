from __future__ import annotations

import json
from typing import Any, Dict, List

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from models import AgentExecutionLog


class AgentLogService:
    """Persistence + query helpers for agent execution logs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record(self, log: Dict[str, Any]) -> AgentExecutionLog:
        entry = AgentExecutionLog(
            task_id=str(log.get("task_id", "")),
            session_id=str(log.get("session_id", "")),
            agent_name=str(log.get("agent_name", "")),
            status=str(log.get("status", "success")),
            started_at=log["started_at"],
            ended_at=log["ended_at"],
            duration_ms=int(log.get("duration_ms", 0)),
            prompt_tokens=int(log.get("prompt_tokens", 0)),
            completion_tokens=int(log.get("completion_tokens", 0)),
            total_tokens=int(log.get("total_tokens", 0)),
            llm_calls=int(log.get("llm_calls", 0)),
            tool_calls=json.dumps(log.get("tool_calls", []), ensure_ascii=False),
            input_payload=json.dumps(log.get("input_payload", {}), ensure_ascii=False),
            output_payload=json.dumps(log.get("output_payload", {}), ensure_ascii=False),
            error=str(log.get("error", "")),
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def list_by_task(self, task_id: str) -> List[Dict[str, Any]]:
        stmt = (
            select(AgentExecutionLog)
            .where(AgentExecutionLog.task_id == task_id)
            .order_by(AgentExecutionLog.id.asc())
        )
        return [self._serialize(row) for row in self.db.scalars(stmt)]

    def latest_task_for_session(self, session_id: str) -> str | None:
        stmt = (
            select(AgentExecutionLog.task_id)
            .where(AgentExecutionLog.session_id == session_id)
            .order_by(AgentExecutionLog.id.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def latest_task(self) -> str | None:
        stmt = (
            select(AgentExecutionLog.task_id)
            .order_by(AgentExecutionLog.id.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def list_recent_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        # Aggregate per task for the run history list.
        stmt = (
            select(
                AgentExecutionLog.task_id,
                AgentExecutionLog.session_id,
                func.max(AgentExecutionLog.created_at).label("created_at"),
                func.sum(AgentExecutionLog.duration_ms).label("duration_ms"),
                func.sum(AgentExecutionLog.total_tokens).label("total_tokens"),
                func.count().label("agent_count"),
                func.sum(
                    case((AgentExecutionLog.status == "error", 1), else_=0)
                ).label("error_count"),
            )
            .group_by(AgentExecutionLog.task_id)
            .order_by(func.max(AgentExecutionLog.id).desc())
            .limit(limit)
        )
        rows = self.db.execute(stmt).all()
        return [
            {
                "task_id": row.task_id,
                "session_id": row.session_id,
                "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S")
                if row.created_at
                else "",
                "duration_ms": int(row.duration_ms or 0),
                "total_tokens": int(row.total_tokens or 0),
                "agent_count": int(row.agent_count or 0),
                "status": "error" if (row.error_count or 0) else "success",
            }
            for row in rows
        ]

    def stats(self) -> Dict[str, Any]:
        task_total = self.db.scalar(
            select(func.count(func.distinct(AgentExecutionLog.task_id)))
        ) or 0
        execution_total = self.db.scalar(
            select(func.count()).select_from(AgentExecutionLog)
        ) or 0
        token_total = self.db.scalar(
            select(func.sum(AgentExecutionLog.total_tokens))
        ) or 0
        error_total = self.db.scalar(
            select(func.count()).where(AgentExecutionLog.status == "error")
        ) or 0
        return {
            "task_total": int(task_total),
            "execution_total": int(execution_total),
            "token_total": int(token_total),
            "error_total": int(error_total),
        }

    def _serialize(self, row: AgentExecutionLog) -> Dict[str, Any]:
        return {
            "id": row.id,
            "task_id": row.task_id,
            "session_id": row.session_id,
            "agent_name": row.agent_name,
            "status": row.status,
            "started_at": row.started_at.isoformat() if row.started_at else "",
            "ended_at": row.ended_at.isoformat() if row.ended_at else "",
            "duration_ms": row.duration_ms,
            "prompt_tokens": row.prompt_tokens,
            "completion_tokens": row.completion_tokens,
            "total_tokens": row.total_tokens,
            "llm_calls": row.llm_calls,
            "tool_calls": self._loads(row.tool_calls, []),
            "input_payload": self._loads(row.input_payload, {}),
            "output_payload": self._loads(row.output_payload, {}),
            "error": row.error,
        }

    @staticmethod
    def _loads(raw: str, default: Any) -> Any:
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return default
