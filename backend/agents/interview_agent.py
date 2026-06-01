from __future__ import annotations

import json
from typing import Any, Dict, List

from .base_agent import BaseAgent
from .messages import AgentMessage

# Common Chinese symptom keywords used by the heuristic fallback so the agent
# still produces useful structured output when running against the Mock
# provider (no real LLM configured).
_SYMPTOM_KEYWORDS = [
    "胸闷", "胸痛", "气短", "心悸", "头晕", "头痛", "发热", "咳嗽", "咳痰",
    "乏力", "恶心", "呕吐", "腹痛", "腹泻", "多饮", "多尿", "体重下降",
    "出汗", "大汗", "心前区不适", "放射痛", "烧心", "反酸", "呼吸困难",
]


class InterviewAgent(BaseAgent):
    """Extracts chief complaint, symptoms and history from ASR transcripts."""

    name = "interview_agent"
    role_prompt = (
        "你是问诊采集智能体(InterviewAgent)。请阅读医患对话转写，提取结构化问诊信息。"
        "只能使用对话中明确出现的信息，不得编造。"
        "必须只输出一个 JSON 对象，包含键："
        "chief_complaint(主诉,字符串), present_illness(现病史,字符串), "
        "symptoms(症状关键词,字符串数组), past_history, allergy_history, "
        "medication_history, family_history, surgical_history(均为字符串), "
        "missing_info(缺失要素,字符串数组), needs_confirmation(需确认信息,字符串数组)。"
    )

    def handle(self, message: AgentMessage) -> Dict[str, Any]:
        dialogues: List[Dict[str, Any]] = message.payload.get("dialogues", [])
        prompt = json.dumps({"dialogues": dialogues}, ensure_ascii=False)

        parsed: Dict[str, Any]
        try:
            result = self.invoke_llm_json(prompt)
            parsed = result if isinstance(result, dict) else {}
        except Exception:
            parsed = {}

        heuristic = self._heuristic(dialogues)
        merged = {**heuristic, **{k: v for k, v in parsed.items() if v}}
        # symptoms must always be present and a list
        if not merged.get("symptoms"):
            merged["symptoms"] = heuristic["symptoms"]
        return {"interview": merged}

    def _heuristic(self, dialogues: List[Dict[str, Any]]) -> Dict[str, Any]:
        patient_lines = [
            str(d.get("text", "")).strip()
            for d in dialogues
            if d.get("speaker") == "patient" and str(d.get("text", "")).strip()
        ]
        all_lines = [
            str(d.get("text", "")).strip()
            for d in dialogues
            if str(d.get("text", "")).strip()
        ]
        source = patient_lines or all_lines
        blob = " ".join(all_lines)

        symptoms = [kw for kw in _SYMPTOM_KEYWORDS if kw in blob]

        chief = source[0][:80] if source else ""
        present = "；".join(source[:4]) if source else ""

        missing: List[str] = []
        if not chief:
            missing.append("主诉")
        if not present:
            missing.append("现病史")
        if "过敏" not in blob:
            missing.append("过敏史")

        return {
            "chief_complaint": chief,
            "present_illness": present,
            "symptoms": symptoms,
            "past_history": "否认慢性病史。" if "否认" in blob else "",
            "allergy_history": "" ,
            "medication_history": "",
            "family_history": "",
            "surgical_history": "",
            "missing_info": missing,
            "needs_confirmation": [],
        }
