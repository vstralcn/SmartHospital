from __future__ import annotations

from models.emr import EMRGenerationResult


class EMRService:
    FOLLOW_UP_QUESTION_MAP = {
        "主诉": "系统建议提问：您这次最不舒服、最主要想解决的问题是什么？",
        "现病史": "系统建议提问：这次不舒服大概从什么时候开始？期间症状怎么变化的？",
        "既往史": "系统建议提问：您既往有高血压、糖尿病、冠心病等慢性病吗？",
        "心血管病史": "系统建议提问：您以前有高血压、冠心病、心律失常或其他心血管疾病吗？",
        "家族史": "系统建议提问：您的直系亲属里有人得过心脏病、高血压或猝死吗？",
        "过敏史": "系统建议提问：您有没有药物、食物或其他过敏史？",
        "用药史": "系统建议提问：您平时长期在服用哪些药物？最近有没有自行用药？",
        "手术史": "系统建议提问：您以前做过手术或住院治疗吗？",
        "吸烟饮酒史": "系统建议提问：您平时吸烟、饮酒吗？大概多久、多少量？",
        "患者年龄": "系统建议提问：请再确认一下您的年龄是多少？",
        "患者性别": "系统建议提问：请确认一下您的性别。",
        "体格检查结果": "系统建议提问：本次查体有没有阳性体征或生命体征异常？",
        "实验室及辅助检查结果": "系统建议提问：目前有化验、心电图或影像检查结果吗？",
        "胸痛具体性质、部位、放射痛（如有）": "系统建议提问：胸痛具体在什么部位？是什么性质？会不会向肩背或左臂放射？",
        "胸闷具体诱因（如劳累、情绪激动等）": "系统建议提问：胸闷通常在什么情况下出现？劳累、活动或情绪激动时会加重吗？",
        "胸闷缓解因素": "系统建议提问：休息、停下活动或服药后，胸闷会不会缓解？",
    }

    def __init__(self, llm_service) -> None:
        self.llm_service = llm_service

    def build_structured_record(self, dialogues):
        structured = self.llm_service.extract_structured_info(dialogues)
        structured = self._fill_core_fields_from_dialogues(structured, dialogues)
        return self._normalize_structured(structured)

    def build_emr_text(self, structured_record) -> str:
        return self.llm_service.generate_emr(structured_record)

    def build_follow_up_questions(self, structured) -> list[str]:
        suggestions = []
        for item in list(structured.missing_info) + list(structured.needs_confirmation):
            text = str(item).strip()
            if not text:
                continue
            suggestion = self.FOLLOW_UP_QUESTION_MAP.get(text)
            if suggestion is None:
                suggestion = f"系统建议提问：请进一步补充{text}。"
            if suggestion not in suggestions:
                suggestions.append(suggestion)
        return suggestions[:8]

    def build_full_result(self, dialogues):
        structured = None
        emr_text = ""
        try:
            structured, emr_text = self.llm_service.generate_aligned_emr(dialogues)
            structured = self._fill_core_fields_from_dialogues(structured, dialogues)
            structured = self._normalize_structured(structured)
        except Exception:
            structured = self.build_structured_record(dialogues)
            emr_text = self.build_emr_text(structured)
        try:
            risk_alerts = self.llm_service.risk_check(dialogues, structured, emr_text)
        except Exception:
            risk_alerts = []
        return EMRGenerationResult(
            structured=structured,
            emr_text=emr_text,
            report_text="",
            risk_alerts=risk_alerts,
        )

    def _normalize_structured(self, structured):
        missing = list(structured.missing_info)
        if not structured.chief_complaint:
            missing.append("主诉")
        if not structured.present_illness:
            missing.append("现病史")
        return structured.model_copy(update={"missing_info": sorted(set(missing))})

    def _fill_core_fields_from_dialogues(self, structured, dialogues):
        if structured.chief_complaint and structured.present_illness:
            return structured

        patient_lines = [
            getattr(item, "text", "").strip()
            for item in dialogues
            if getattr(item, "speaker", "") == "patient"
            and getattr(item, "text", "").strip()
        ]
        source_lines = patient_lines or [
            getattr(item, "text", "").strip()
            for item in dialogues
            if getattr(item, "text", "").strip()
        ]
        if not source_lines:
            return structured

        updates = {}
        if not structured.chief_complaint:
            updates["chief_complaint"] = source_lines[0][:80]
        if not structured.present_illness:
            updates["present_illness"] = "；".join(source_lines[:3])
        return structured.model_copy(update=updates)
