from __future__ import annotations

import json
from typing import Any, Dict, List

from .base_provider import BaseLLMProvider


class MockProvider(BaseLLMProvider):
    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        payload = json.loads(prompt)
        prompt_type = (system_prompt or "").splitlines()[0].strip()
        if prompt_type == "structured_extract":
            return json.dumps(self._build_structured(payload.get("dialogues", [])), ensure_ascii=False, indent=2)
        if prompt_type == "emr_generation":
            return self._build_emr_text(payload.get("structured", {}))
        if prompt_type == "risk_check":
            return json.dumps(self._build_risk_alerts(payload), ensure_ascii=False, indent=2)
        return ""

    def _build_structured(self, dialogues: List[Dict[str, Any]]) -> Dict[str, Any]:
        patient_lines = [item.get("text", "") for item in dialogues if item.get("speaker") == "patient"]
        text_blob = " ".join(patient_lines)
        return {
            "chief_complaint": patient_lines[0] if patient_lines else "胸闷 2 天",
            "present_illness": text_blob or "患者自诉胸闷 2 天，活动后稍明显，伴轻度气短。",
            "past_history": "否认高血压、糖尿病等慢性病史。" if "否认" in text_blob else "",
            "surgical_history": "否认手术史。",
            "allergy_history": "否认药物过敏史。",
            "medication_history": "近期未规律服药。",
            "family_history": "未明确提及。",
            "missing_info": ["吸烟饮酒史", "生命体征"],
            "needs_confirmation": ["胸闷是否伴胸痛", "既往心血管病史是否完整"],
        }

    def _build_emr_text(self, structured: Dict[str, Any]) -> str:
        return "\n".join(
            [
                "主诉：" + structured.get("chief_complaint", "待确认"),
                "现病史：" + structured.get("present_illness", "待确认"),
                "既往史：" + (structured.get("past_history") or "待补充"),
                "手术史：" + (structured.get("surgical_history") or "待补充"),
                "过敏史：" + (structured.get("allergy_history") or "待补充"),
                "用药史：" + (structured.get("medication_history") or "待补充"),
                "家族史：" + (structured.get("family_history") or "待补充"),
                "说明：以上内容为问诊整理草稿，需由医生审核确认。",
            ]
        )

    def _build_risk_alerts(self, payload: Dict[str, Any]) -> List[str]:
        structured = payload.get("structured", {})
        alerts: List[str] = []
        if structured.get("missing_info"):
            alerts.append("存在缺失字段，建议补充追问后再确认病历。")
        if structured.get("needs_confirmation"):
            alerts.append("部分信息仍待确认，请避免将未确认内容写成既定事实。")
        return alerts
