from __future__ import annotations

import json
from typing import Any, Dict, List

from .base_agent import BaseAgent
from .messages import AgentMessage


class DrugAgent(BaseAgent):
    """Recommends medications and checks contraindications via MCP tools."""

    name = "drug_agent"
    role_prompt = (
        "你是用药推荐智能体(DrugAgent)。基于诊断结果与药品知识库证据，"
        "推荐药物并提示禁忌。必须只输出一个 JSON 对象，包含键："
        "recommendations(数组,每项含 name, usage, indications(字符串数组), "
        "category), contraindication_alerts(字符串数组,禁忌/慎用提示)。"
    )

    def handle(self, message: AgentMessage) -> Dict[str, Any]:
        diagnosis: Dict[str, Any] = message.payload.get("diagnosis", {})
        interview: Dict[str, Any] = message.payload.get("interview", {})

        candidate_drugs: List[str] = list(diagnosis.get("recommended_drugs", []))
        # Patient conditions used for contraindication screening.
        conditions = self._collect_conditions(interview)

        recommendations: List[Dict[str, Any]] = []
        alerts: List[str] = []
        for drug_name in candidate_drugs:
            drug = self.call_tool("search_drug", name=drug_name).get("data")
            if not drug:
                continue
            check = self.call_tool(
                "check_contraindication", name=drug_name, conditions=conditions
            ).get("data") or {}
            recommendations.append(
                {
                    "name": drug.get("name", drug_name),
                    "category": drug.get("category", ""),
                    "usage": drug.get("usage", ""),
                    "indications": drug.get("indications", []),
                    "contraindications": drug.get("contraindications", []),
                    "contraindication_check": check,
                }
            )
            for hit in check.get("hits", []):
                alerts.append(f"{drug.get('name', drug_name)}：患者存在『{hit}』，属于禁忌/慎用，请复核。")

        # Let the LLM optionally refine the textual advice; fall back silently.
        prompt = json.dumps(
            {
                "primary_diagnosis": diagnosis.get("primary_diagnosis", ""),
                "candidate_drugs": candidate_drugs,
                "patient_conditions": conditions,
                "tool_results": recommendations,
            },
            ensure_ascii=False,
        )
        try:
            result = self.invoke_llm_json(prompt)
            if isinstance(result, dict) and result.get("recommendations"):
                # keep MCP-grounded data but allow LLM to add alerts
                for extra in result.get("contraindication_alerts", []) or []:
                    if extra and extra not in alerts:
                        alerts.append(str(extra))
        except Exception:
            pass

        return {
            "drug": {
                "recommendations": recommendations,
                "contraindication_alerts": alerts,
                "screened_conditions": conditions,
            }
        }

    def _collect_conditions(self, interview: Dict[str, Any]) -> List[str]:
        text_fields = [
            interview.get("past_history", ""),
            interview.get("allergy_history", ""),
            interview.get("medication_history", ""),
            interview.get("present_illness", ""),
        ]
        blob = " ".join(str(t) for t in text_fields if t)
        known = [
            "阿司匹林过敏", "活动性消化道出血", "活动性消化道溃疡", "重度心动过缓",
            "支气管哮喘急性发作", "活动性肝病", "妊娠期及哺乳期", "重度肾功能不全(eGFR<30)",
            "收缩压低于90mmHg",
        ]
        hits = [item for item in known if any(part in blob for part in item.split("("))]
        # Also surface raw allergy text as a condition token.
        allergy = str(interview.get("allergy_history", "")).strip()
        if allergy and allergy not in hits:
            hits.append(allergy)
        return hits
