from __future__ import annotations

import json
from typing import Any, Dict, List

from .base_agent import BaseAgent
from .messages import AgentMessage


class DiagnosisAgent(BaseAgent):
    """Generates candidate diseases and reasoning from interview output.

    Uses the Disease MCP server to ground its candidates in a knowledge base
    rather than relying purely on the LLM.
    """

    name = "diagnosis_agent"
    role_prompt = (
        "你是诊断推理智能体(DiagnosisAgent)。基于问诊智能体提取的症状与病史，"
        "并参考疾病知识库证据，给出候选疾病与推理。"
        "必须只输出一个 JSON 对象，包含键："
        "primary_diagnosis(首要考虑诊断,字符串), reasoning(整体推理,字符串), "
        "candidate_diseases(数组,每项含 name, icd10, confidence(0-1之间小数), "
        "reasoning, recommended_labs(字符串数组))。"
    )

    def handle(self, message: AgentMessage) -> Dict[str, Any]:
        interview: Dict[str, Any] = message.payload.get("interview", {})
        symptoms: List[str] = list(interview.get("symptoms", []))
        complaint = interview.get("chief_complaint", "")

        # --- ground candidates via the Disease MCP server ------------------
        match_result = self.call_tool("match_by_symptoms", symptoms=symptoms)
        matches: List[Dict[str, Any]] = match_result.get("data") or []

        evidence: List[Dict[str, Any]] = []
        for match in matches:
            disease = self.call_tool("query_disease", name=match["name"]).get("data")
            if disease:
                evidence.append(
                    {
                        "name": disease.get("name"),
                        "icd10": disease.get("icd10", ""),
                        "matched_symptoms": match.get("matched_symptoms", []),
                        "score": match.get("score", 0),
                        "recommended_labs": disease.get("recommended_labs", []),
                        "recommended_drugs": disease.get("recommended_drugs", []),
                        "risk_factors": disease.get("risk_factors", []),
                    }
                )

        prompt = json.dumps(
            {
                "chief_complaint": complaint,
                "symptoms": symptoms,
                "present_illness": interview.get("present_illness", ""),
                "knowledge_base_evidence": evidence,
            },
            ensure_ascii=False,
        )

        try:
            result = self.invoke_llm_json(prompt)
            parsed = result if isinstance(result, dict) else {}
        except Exception:
            parsed = {}

        heuristic = self._heuristic(evidence, symptoms)
        candidates = parsed.get("candidate_diseases") or heuristic["candidate_diseases"]
        primary = parsed.get("primary_diagnosis") or heuristic["primary_diagnosis"]
        reasoning = parsed.get("reasoning") or heuristic["reasoning"]

        return {
            "diagnosis": {
                "primary_diagnosis": primary,
                "reasoning": reasoning,
                "candidate_diseases": candidates,
                "recommended_drugs": heuristic["recommended_drugs"],
            }
        }

    def _heuristic(
        self, evidence: List[Dict[str, Any]], symptoms: List[str]
    ) -> Dict[str, Any]:
        candidates: List[Dict[str, Any]] = []
        total = sum(item.get("score", 0) for item in evidence) or 1
        recommended_drugs: List[str] = []
        for item in evidence:
            confidence = round(item.get("score", 0) / total, 2)
            matched = "、".join(item.get("matched_symptoms", []))
            candidates.append(
                {
                    "name": item["name"],
                    "icd10": item.get("icd10", ""),
                    "confidence": confidence,
                    "reasoning": f"命中典型症状：{matched}。" if matched else "症状部分吻合。",
                    "recommended_labs": item.get("recommended_labs", []),
                }
            )
            for drug in item.get("recommended_drugs", []):
                if drug not in recommended_drugs:
                    recommended_drugs.append(drug)

        if candidates:
            primary = candidates[0]["name"]
            reasoning = (
                f"根据症状（{('、'.join(symptoms)) or '未明确'}）与疾病知识库匹配，"
                f"首先考虑{primary}，建议结合推荐检查进一步明确。"
            )
        else:
            primary = "待明确"
            reasoning = "现有症状信息不足以匹配明确疾病，建议补充问诊与检查。"

        return {
            "primary_diagnosis": primary,
            "reasoning": reasoning,
            "candidate_diseases": candidates,
            "recommended_drugs": recommended_drugs,
        }
