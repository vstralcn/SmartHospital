from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_task_id() -> str:
    return uuid.uuid4().hex[:16]


def new_message_id() -> str:
    return "msg_" + uuid.uuid4().hex[:12]


class MessageType:
    """Canonical Agent-to-Agent (A2A) message types.

    The Internet of Agents (IoA) protocol distinguishes between several kinds
    of envelope so that receivers can branch on intent without inspecting the
    payload. They are defined as plain string constants (rather than an Enum)
    so they serialise transparently to JSON and to the SQLite log.
    """

    TASK_REQUEST = "task_request"
    TASK_RESULT = "task_result"
    KNOWLEDGE_QUERY = "knowledge_query"
    KNOWLEDGE_RESULT = "knowledge_result"
    CONSENSUS_VOTE = "consensus_vote"


class AgentMessage(BaseModel):
    """Standardized Agent-to-Agent (A2A) message envelope.

    Every interaction between agents flows through an ``AgentMessage``. Agents
    are not allowed to share state via direct variable references — they only
    read from ``payload`` of an incoming message and emit a new message. This
    mirrors the message-passing contract used by the Internet of Agents (IoA)
    philosophy and keeps the workflow auditable.

    Fields follow the IoA protocol definition: a globally unique
    ``message_id``, the originating/destination agents (``source`` / ``target``,
    a.k.a. *from_agent* / *to_agent*), a ``task_id`` that correlates every
    message of one consultation, a ``timestamp`` and the structured ``payload``.
    """

    message_id: str = Field(default_factory=new_message_id)
    task_id: str = Field(default_factory=new_task_id)
    source: str = "system"
    target: str = ""
    timestamp: str = Field(default_factory=_now_iso)
    message_type: str = MessageType.TASK_REQUEST
    payload: Dict[str, Any] = Field(default_factory=dict)

    # Aliases that match the protocol vocabulary used in the design docs.
    @property
    def from_agent(self) -> str:
        return self.source

    @property
    def to_agent(self) -> str:
        return self.target

    def reply(
        self,
        source: str,
        target: str,
        payload: Dict[str, Any],
        message_type: str = MessageType.TASK_RESULT,
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
