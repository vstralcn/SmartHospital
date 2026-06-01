from __future__ import annotations

import json
from typing import Any, Dict, List

from .base_agent import BaseAgent
from .messages import AgentMessage

# EMR sections that should normally be populated for a complete record.
_REQUIRED_SECTIONS = {
    "chief_complaint": "主诉",
    "present_illness": "现病史",
    "past_history": "既往史",
    "allergy_history": "过敏史",
}


class QualityControlAgent(BaseAgent):
    """Audits the final EMR for completeness and logical consistency."""

    name = "quality_control_agent"
    role_prompt = (
        "你是质控审核智能体(QualityControlAgent)。审核最终病历的完整性与逻辑一致性，"
        "指出缺失项、矛盾点与潜在风险。必须只输出一个 JSON 对象，包含键："
        "passed(布尔), score(0-100整数), issues(字符串数组), "
        "risk_alerts(字符串数组), suggestions(字符串数组)。"
    )

    def handle(self, message: AgentMessage) -> Dict[str, Any]:
        emr: Dict[str, Any] = message.payload.get("emr", {})
        diagnosis: Dict[str, Any] = message.payload.get("diagnosis", {})
        drug: Dict[str, Any] = message.payload.get("drug", {})
        structured: Dict[str, Any] = emr.get("structured", {})

        audit = self._audit(structured, diagnosis, drug)

        prompt = json.dumps(
            {
                "structured": structured,
                "emr_text": emr.get("emr_text", ""),
                "diagnosis": diagnosis,
                "drug_alerts": drug.get("contraindication_alerts", []),
            },
            ensure_ascii=False,
        )
        try:
            result = self.invoke_llm_json(prompt)
            if isinstance(result, dict):
                for extra in result.get("issues", []) or []:
                    if extra and extra not in audit["issues"]:
                        audit["issues"].append(str(extra))
                for extra in result.get("risk_alerts", []) or []:
                    if extra and extra not in audit["risk_alerts"]:
                        audit["risk_alerts"].append(str(extra))
        except Exception:
            pass

        audit["passed"] = not audit["issues"]
        audit["score"] = max(0, 100 - len(audit["issues"]) * 15 - len(audit["risk_alerts"]) * 5)
        return {"quality_control": audit}

    def _audit(
        self,
        structured: Dict[str, Any],
        diagnosis: Dict[str, Any],
        drug: Dict[str, Any],
    ) -> Dict[str, Any]:
        issues: List[str] = []
        suggestions: List[str] = []
        risk_alerts: List[str] = []

        for key, label in _REQUIRED_SECTIONS.items():
            if not str(structured.get(key, "")).strip():
                issues.append(f"{label}缺失或为空")
                suggestions.append(f"建议补充{label}相关问诊内容")

        if not diagnosis.get("primary_diagnosis") or diagnosis.get("primary_diagnosis") == "待明确":
            issues.append("缺少明确的初步诊断")

        for missing in structured.get("missing_info", []) or []:
            risk_alerts.append(f"病历要素缺失：{missing}")
        for confirm in structured.get("needs_confirmation", []) or []:
            risk_alerts.append(f"待确认信息：{confirm}")
        for alert in drug.get("contraindication_alerts", []) or []:
            risk_alerts.append(alert)

        score = max(0, 100 - len(issues) * 15 - len(risk_alerts) * 5)
        return {
            "passed": not issues,
            "score": score,
            "issues": issues,
            "risk_alerts": risk_alerts,
            "suggestions": suggestions,
        }
