from __future__ import annotations

import json
from typing import Any, Dict, List

from .base_agent import BaseAgent
from .messages import AgentMessage


class EMRAgent(BaseAgent):
    """Compiles all upstream agent outputs into a structured EMR."""

    name = "emr_agent"
    role_prompt = (
        "你是病历整合智能体(EMRAgent)。综合问诊、诊断与用药结果，"
        "生成规范结构化电子病历。必须只输出一个 JSON 对象，包含键："
        "structured(对象,含 chief_complaint, present_illness, past_history, "
        "surgical_history, allergy_history, medication_history, family_history, "
        "missing_info(数组), needs_confirmation(数组)), emr_text(完整病历文本,字符串)。"
    )

    def handle(self, message: AgentMessage) -> Dict[str, Any]:
        interview: Dict[str, Any] = message.payload.get("interview", {})
        diagnosis: Dict[str, Any] = message.payload.get("diagnosis", {})
        drug: Dict[str, Any] = message.payload.get("drug", {})

        prompt = json.dumps(
            {"interview": interview, "diagnosis": diagnosis, "drug": drug},
            ensure_ascii=False,
        )

        structured = self._build_structured(interview)
        emr_text = self._build_emr_text(structured, diagnosis, drug)

        try:
            result = self.invoke_llm_json(prompt)
            if isinstance(result, dict):
                llm_structured = result.get("structured")
                if isinstance(llm_structured, dict):
                    structured = {**structured, **{k: v for k, v in llm_structured.items() if v}}
                if result.get("emr_text"):
                    emr_text = str(result["emr_text"])
        except Exception:
            pass

        return {"emr": {"structured": structured, "emr_text": emr_text}}

    def _build_structured(self, interview: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chief_complaint": interview.get("chief_complaint", ""),
            "present_illness": interview.get("present_illness", ""),
            "past_history": interview.get("past_history", ""),
            "surgical_history": interview.get("surgical_history", ""),
            "allergy_history": interview.get("allergy_history", ""),
            "medication_history": interview.get("medication_history", ""),
            "family_history": interview.get("family_history", ""),
            "missing_info": list(interview.get("missing_info", [])),
            "needs_confirmation": list(interview.get("needs_confirmation", [])),
        }

    def _build_emr_text(
        self,
        structured: Dict[str, Any],
        diagnosis: Dict[str, Any],
        drug: Dict[str, Any],
    ) -> str:
        lines: List[str] = [
            "主诉：" + (structured.get("chief_complaint") or "待确认"),
            "现病史：" + (structured.get("present_illness") or "待确认"),
            "既往史：" + (structured.get("past_history") or "待补充"),
            "手术史：" + (structured.get("surgical_history") or "待补充"),
            "过敏史：" + (structured.get("allergy_history") or "待补充"),
            "用药史：" + (structured.get("medication_history") or "待补充"),
            "家族史：" + (structured.get("family_history") or "待补充"),
        ]

        primary = diagnosis.get("primary_diagnosis")
        if primary:
            lines.append("初步诊断：" + primary)
        candidates = diagnosis.get("candidate_diseases") or []
        if candidates:
            names = "、".join(
                f"{c.get('name')}(置信度{c.get('confidence')})" for c in candidates[:3]
            )
            lines.append("鉴别诊断：" + names)
        if diagnosis.get("reasoning"):
            lines.append("诊断依据：" + diagnosis["reasoning"])

        recs = drug.get("recommendations") or []
        if recs:
            med = "；".join(f"{r.get('name')} {r.get('usage')}" for r in recs[:5])
            lines.append("处置建议：" + med)

        lines.append("说明：以上内容由多智能体协作整理生成，需由医生审核确认。")
        return "\n".join(lines)
