from __future__ import annotations

import json
from typing import Any, Dict, List

from services.knowledge_base_service import get_knowledge_base

from .base_agent import BaseAgent
from .messages import AgentMessage


class KnowledgeAgent(BaseAgent):
    """Retrieval-Augmented Generation (RAG) agent.

    Grounds the diagnosis in a citable medical knowledge base. It builds a
    query from the upstream diagnosis and interview output, retrieves the most
    relevant evidence chunks from the vector store and (optionally) asks the
    LLM to distil a short evidence summary. Running fully offline under the
    Mock provider simply yields the retrieved references without an LLM
    summary.
    """

    name = "knowledge_agent"
    role_prompt = (
        "你是知识检索智能体(KnowledgeAgent)。基于检索到的循证医学知识片段，"
        "为当前诊断提供简明的循证参考摘要，只能依据给定片段，不得编造。"
        "必须只输出一个 JSON 对象，包含键：summary(字符串,循证要点摘要)。"
    )

    def handle(self, message: AgentMessage) -> Dict[str, Any]:
        diagnosis: Dict[str, Any] = message.payload.get("diagnosis", {})
        interview: Dict[str, Any] = message.payload.get("interview", {})

        query = self._build_query(diagnosis, interview)
        kb = get_knowledge_base()
        references = kb.search(query, k=4)
        # Record the retrieval as a tool call so it appears in the monitor.
        self._tool_calls.append(
            {
                "tool": "rag_search",
                "args": {"query": query, "k": 4, "store_size": kb.size},
                "ok": bool(references),
            }
        )

        summary = self._fallback_summary(references)
        if references:
            prompt = json.dumps(
                {
                    "query": query,
                    "primary_diagnosis": diagnosis.get("primary_diagnosis", ""),
                    "retrieved_references": [
                        {"title": r["title"], "source": r["source"], "snippet": r["snippet"]}
                        for r in references
                    ],
                },
                ensure_ascii=False,
            )
            try:
                result = self.invoke_llm_json(prompt)
                if isinstance(result, dict) and result.get("summary"):
                    summary = str(result["summary"])
            except Exception:
                pass

        return {
            "knowledge": {
                "query": query,
                "references": references,
                "summary": summary,
            }
        }

    def _build_query(self, diagnosis: Dict[str, Any], interview: Dict[str, Any]) -> str:
        parts: List[str] = []
        primary = str(diagnosis.get("primary_diagnosis", "")).strip()
        if primary and primary not in {"待明确", "待确认"}:
            parts.append(primary)
        for candidate in (diagnosis.get("candidate_diseases") or [])[:3]:
            name = str(candidate.get("name", "")).strip()
            if name:
                parts.append(name)
        symptoms = [str(s).strip() for s in interview.get("symptoms", []) if str(s).strip()]
        parts.extend(symptoms[:6])
        if not parts:
            chief = str(interview.get("chief_complaint", "")).strip()
            if chief:
                parts.append(chief)
        return " ".join(dict.fromkeys(parts))  # dedupe, preserve order

    def _fallback_summary(self, references: List[Dict[str, Any]]) -> str:
        if not references:
            return "未检索到匹配的循证参考。"
        titles = "、".join(dict.fromkeys(r["title"] for r in references if r["title"]))
        return f"检索到 {len(references)} 条相关循证参考：{titles}。详见知识参考片段。"
