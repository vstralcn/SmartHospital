from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from models.emr import EMRGenerationResult, StructuredEMR

from .base_agent import LogSink
from .diagnosis_agent import DiagnosisAgent
from .drug_agent import DrugAgent
from .emr_agent import EMRAgent
from .interview_agent import InterviewAgent
from .messages import AgentMessage, new_task_id
from .quality_control_agent import QualityControlAgent

# Fixed collaboration pipeline: Interview -> Diagnosis -> Drug -> EMR -> QC.
_AGENT_PIPELINE = [
    InterviewAgent,
    DiagnosisAgent,
    DrugAgent,
    EMRAgent,
    QualityControlAgent,
]


class Orchestrator:
    """Coordinates the multi-agent medical collaboration workflow.

    The orchestrator wires the agents into a sequential pipeline and moves a
    single :class:`AgentMessage` from one agent to the next. Agents only ever
    see the message envelope (A2A protocol) — there is no shared mutable state
    between them. Every agent run is logged through ``log_sink`` so the
    execution can be observed in real time.
    """

    def __init__(
        self,
        provider: Any,
        mcp_registry: Any,
        log_sink: Optional[LogSink] = None,
    ) -> None:
        self.provider = provider
        self.mcp = mcp_registry
        self.log_sink = log_sink
        self.agents = [
            agent_cls(provider=provider, mcp_registry=mcp_registry, log_sink=log_sink)
            for agent_cls in _AGENT_PIPELINE
        ]

    def run(
        self,
        dialogues: List[Dict[str, Any]],
        session_id: str = "",
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        task_id = task_id or new_task_id()
        message = AgentMessage(
            task_id=task_id,
            source="orchestrator",
            target=self.agents[0].name,
            message_type="task",
            payload={
                "session_id": session_id,
                "dialogues": [self._as_dict(d) for d in dialogues],
            },
        )

        for index, agent in enumerate(self.agents):
            next_target = (
                self.agents[index + 1].name
                if index + 1 < len(self.agents)
                else "orchestrator"
            )
            message = agent.run(message, target=next_target)

        return {"task_id": task_id, "payload": message.payload}

    def build_full_result(
        self, dialogues: List[Any], session_id: str = ""
    ) -> EMRGenerationResult:
        """Drop-in replacement for the legacy monolithic EMR pipeline."""

        outcome = self.run(dialogues, session_id=session_id)
        payload = outcome["payload"]

        emr = payload.get("emr", {})
        structured_data = emr.get("structured", {})
        try:
            structured = StructuredEMR.model_validate(structured_data)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to validate structured EMR, using defaults: {exc}")
            structured = StructuredEMR()

        qc = payload.get("quality_control", {})
        risk_alerts = list(qc.get("risk_alerts", []))

        return EMRGenerationResult(
            structured=structured,
            emr_text=str(emr.get("emr_text", "")),
            report_text="",
            risk_alerts=risk_alerts,
        )

    @staticmethod
    def _as_dict(item: Any) -> Dict[str, Any]:
        if hasattr(item, "model_dump"):
            return item.model_dump()
        if isinstance(item, dict):
            return item
        return {"text": str(item)}
