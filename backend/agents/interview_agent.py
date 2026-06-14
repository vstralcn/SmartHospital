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

# Keyword sets for the heuristic history extraction. They let the agent
# populate 既往史/手术史/过敏史/用药史/家族史 directly from the transcript even
# when no real LLM is configured (or the LLM call fails / returns blanks),
# instead of leaving every history field empty ("待补充").
_PAST_HISTORY_KEYWORDS = [
    "既往", "病史", "以前", "之前", "多年", "患过", "得过", "确诊", "诊断",
    "高血压", "糖尿病", "冠心病", "心脏病", "脑梗", "脑卒中", "中风", "哮喘",
    "乙肝", "肝炎", "肾病", "甲亢", "高血脂", "高血糖", "慢性", "结核",
]
_SURGICAL_KEYWORDS = ["手术", "切除", "开刀", "置换", "术后", "造影", "支架"]
_ALLERGY_KEYWORDS = ["过敏", "皮疹", "青霉素", "头孢"]
_MEDICATION_KEYWORDS = [
    "服用", "口服", "在吃", "吃药", "服药", "用药", "正在吃", "长期吃",
    "降压药", "降糖药", "他汀", "阿司匹林", "硝酸甘油", "胰岛素", "服了",
]
_FAMILY_KEYWORDS = [
    "家族", "家里人", "遗传", "父亲", "母亲", "父母", "爸爸", "妈妈",
    "爷爷", "奶奶", "外公", "外婆", "兄弟", "姐妹", "哥哥", "弟弟", "姐姐",
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
        present = "；".join(source) if source else ""

        # History lives in the answers, not the doctor's questions, so drop
        # interrogative lines to avoid pulling "有没有高血压？" into 既往史.
        statement_lines = [
            line for line in all_lines if "？" not in line and "?" not in line
        ]
        past_history = self._collect(statement_lines, _PAST_HISTORY_KEYWORDS)
        surgical_history = self._collect(statement_lines, _SURGICAL_KEYWORDS)
        allergy_history = self._collect(statement_lines, _ALLERGY_KEYWORDS)
        medication_history = self._collect(statement_lines, _MEDICATION_KEYWORDS)
        family_history = self._collect(statement_lines, _FAMILY_KEYWORDS)

        missing: List[str] = []
        if not chief:
            missing.append("主诉")
        if not present:
            missing.append("现病史")
        if not past_history:
            missing.append("既往史")
        if not allergy_history:
            missing.append("过敏史")
        if not medication_history:
            missing.append("用药史")
        if not family_history:
            missing.append("家族史")

        return {
            "chief_complaint": chief,
            "present_illness": present,
            "symptoms": symptoms,
            "past_history": past_history,
            "allergy_history": allergy_history,
            "medication_history": medication_history,
            "family_history": family_history,
            "surgical_history": surgical_history,
            "missing_info": missing,
            "needs_confirmation": [],
        }

    @staticmethod
    def _collect(lines: List[str], keywords: List[str]) -> str:
        """Join (deduplicated) transcript lines that mention any keyword."""
        hits: List[str] = []
        for line in lines:
            if any(kw in line for kw in keywords) and line not in hits:
                hits.append(line)
        return "；".join(hits)
