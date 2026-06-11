from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph
from loguru import logger

from models.emr import EMRGenerationResult, StructuredEMR

from .base_agent import LogSink
from .diagnosis_agent import DiagnosisAgent
from .drug_agent import DrugAgent
from .emr_agent import EMRAgent
from .followup_agent import FollowUpAgent
from .interview_agent import InterviewAgent
from .knowledge_agent import KnowledgeAgent
from .messages import AgentMessage, MessageType, new_task_id
from .quality_control_agent import QualityControlAgent

# Fixed collaboration pipeline compiled into a LangGraph StateGraph:
# Interview -> Diagnosis -> Knowledge(RAG) -> Drug -> EMR -> QC -> FollowUp.
_AGENT_PIPELINE = [
    InterviewAgent,
    DiagnosisAgent,
    KnowledgeAgent,
    DrugAgent,
    EMRAgent,
    QualityControlAgent,
    FollowUpAgent,
]


class _WorkflowState(TypedDict):
    """State carried between LangGraph nodes.

    The only mutable channel is the A2A ``message`` envelope; each node reads
    the incoming message and returns a new one, so agents never share state by
    reference — they only communicate through the standardized message.
    """

    message: AgentMessage


class Orchestrator:
    """Coordinates the multi-agent medical collaboration workflow.

    The orchestrator wires the agents into a :class:`~langgraph.graph.StateGraph`
    and moves a single :class:`AgentMessage` from one node to the next. Agents
    only ever see the message envelope (A2A protocol) — there is no shared
    mutable state between them. Every agent run is logged through ``log_sink``
    so the execution can be observed in real time.

    The orchestrator itself holds only immutable configuration. Fresh agent
    instances are created for every :meth:`run` call so that overlapping
    pipeline runs (the frontend polls ``generate-emr`` periodically) never
    share the agents' per-run accumulators.
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

    def _build_agents(self) -> List[Any]:
        return [
            agent_cls(provider=self.provider, mcp_registry=self.mcp, log_sink=self.log_sink)
            for agent_cls in _AGENT_PIPELINE
        ]

    def _build_workflow(self, agents: List[Any]) -> Any:
        """Compile the agent pipeline into a LangGraph state machine."""

        workflow = StateGraph(_WorkflowState)

        def make_node(agent: Any, next_target: str):
            def _node(state: _WorkflowState) -> Dict[str, Any]:
                message = agent.run(state["message"], target=next_target)
                return {"message": message}

            return _node

        for index, agent in enumerate(agents):
            next_target = (
                agents[index + 1].name if index + 1 < len(agents) else "orchestrator"
            )
            workflow.add_node(agent.name, make_node(agent, next_target))

        workflow.set_entry_point(agents[0].name)
        for index in range(len(agents) - 1):
            workflow.add_edge(agents[index].name, agents[index + 1].name)
        workflow.add_edge(agents[-1].name, END)

        return workflow.compile()

    def run(
        self,
        dialogues: List[Dict[str, Any]],
        session_id: str = "",
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        task_id = task_id or new_task_id()
        agents = self._build_agents()
        graph = self._build_workflow(agents)

        message = AgentMessage(
            task_id=task_id,
            source="orchestrator",
            target=agents[0].name,
            message_type=MessageType.TASK_REQUEST,
            payload={
                "session_id": session_id,
                "dialogues": [self._as_dict(d) for d in dialogues],
            },
        )

        final_state: _WorkflowState = graph.invoke({"message": message})
        return {"task_id": task_id, "payload": final_state["message"].payload}

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
