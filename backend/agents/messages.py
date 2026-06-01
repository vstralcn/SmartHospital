from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_task_id() -> str:
    return uuid.uuid4().hex[:16]


class AgentMessage(BaseModel):
    """Standardized Agent-to-Agent (A2A) message envelope.

    Every interaction between agents flows through an ``AgentMessage``. Agents
    are not allowed to share state via direct variable references — they only
    read from ``payload`` of an incoming message and emit a new message. This
    mirrors the message-passing contract used by the Internet of Agents (IoA)
    philosophy and keeps the workflow auditable.
    """

    task_id: str = Field(default_factory=new_task_id)
    source: str = "system"
    target: str = ""
    timestamp: str = Field(default_factory=_now_iso)
    message_type: str = "task"
    payload: Dict[str, Any] = Field(default_factory=dict)

    def reply(
        self,
        source: str,
        target: str,
        payload: Dict[str, Any],
        message_type: str = "result",
    ) -> "AgentMessage":
        """Create a downstream message that preserves the task id.

        The new payload is merged on top of the current one so each agent in
        the chain accumulates context without mutating the message it received.
        """

        merged: Dict[str, Any] = dict(self.payload)
        merged.update(payload)
        return AgentMessage(
            task_id=self.task_id,
            source=source,
            target=target,
            timestamp=_now_iso(),
            message_type=message_type,
            payload=merged,
        )
