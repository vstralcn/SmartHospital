from __future__ import annotations

import json
from typing import Any, Dict, List

from .base_agent import BaseAgent
from .messages import AgentMessage

# Default follow-up window keyed by suspected condition family.
_FOLLOWUP_WINDOW = {
    "急性心肌梗死": "出院后 1 周内心内科门诊复诊，并按胸痛中心要求随访",
    "冠状动脉粥样硬化性心脏病": "2 周内心内科门诊复诊",
    "心绞痛": "2 周内心内科门诊复诊",
    "原发性高血压": "2-4 周内复诊评估血压控制情况",
    "2型糖尿病": "1 个月内复诊，3 个月复查糖化血红蛋白",
    "胃食管反流病": "用药 2-4 周后消化内科复诊评估疗效",
}

# Condition-specific precautions surfaced to the patient.
_PRECAUTIONS = {
    "急性心肌梗死": ["如再次出现持续胸痛/大汗/濒死感立即拨打120", "严格规律服用抗血小板及他汀类药物", "戒烟限酒、低盐低脂饮食"],
    "冠状动脉粥样硬化性心脏病": ["随身携带硝酸甘油，胸痛发作时舌下含服", "避免劳累与情绪激动", "控制血压、血脂、血糖"],
    "心绞痛": ["发作时立即休息并含服硝酸甘油", "避免饱餐、寒冷与剧烈运动", "如发作频率增加或不缓解及时就诊"],
    "原发性高血压": ["每日定时自测血压并记录", "坚持限盐、规律服药，勿自行停药", "控制体重、适度运动"],
    "2型糖尿病": ["规律监测血糖并记录", "饮食控制与适度运动", "注意足部护理，预防低血糖"],
    "胃食管反流病": ["睡前 3 小时避免进食、抬高床头", "避免高脂、辛辣及刺激性饮食", "戒烟限酒、控制体重"],
}


class FollowUpAgent(BaseAgent):
    """Generates a structured follow-up plan from the final EMR + diagnosis."""

    name = "followup_agent"
    role_prompt = (
        "你是随访智能体(FollowUpAgent)。根据诊断结果与病历，制定随访计划，"
        "包括复诊时间、复查项目与注意事项。必须只输出一个 JSON 对象，包含键："
        "next_visit(字符串,复诊建议), review_items(字符串数组,复查项目), "
        "precautions(字符串数组,注意事项)。"
    )

    def handle(self, message: AgentMessage) -> Dict[str, Any]:
        diagnosis: Dict[str, Any] = message.payload.get("diagnosis", {})
        emr: Dict[str, Any] = message.payload.get("emr", {})
        drug: Dict[str, Any] = message.payload.get("drug", {})

        plan = self._heuristic(diagnosis, drug)

        prompt = json.dumps(
            {
                "primary_diagnosis": diagnosis.get("primary_diagnosis", ""),
                "candidate_diseases": diagnosis.get("candidate_diseases", []),
                "structured": emr.get("structured", {}),
                "recommendations": drug.get("recommendations", []),
            },
            ensure_ascii=False,
        )
        try:
            result = self.invoke_llm_json(prompt)
            if isinstance(result, dict):
                if result.get("next_visit"):
                    plan["next_visit"] = str(result["next_visit"])
                for item in result.get("review_items", []) or []:
                    if item and item not in plan["review_items"]:
                        plan["review_items"].append(str(item))
                for item in result.get("precautions", []) or []:
                    if item and item not in plan["precautions"]:
                        plan["precautions"].append(str(item))
        except Exception:
            pass

        return {"follow_up": plan}

    def _heuristic(self, diagnosis: Dict[str, Any], drug: Dict[str, Any]) -> Dict[str, Any]:
        primary = str(diagnosis.get("primary_diagnosis", "")).strip()

        next_visit = _FOLLOWUP_WINDOW.get(primary, "2 周内门诊复诊，如症状加重随时就诊")

        review_items: List[str] = []
        for candidate in diagnosis.get("candidate_diseases") or []:
            for lab in candidate.get("recommended_labs", []) or []:
                if lab and lab not in review_items:
                    review_items.append(lab)
        if not review_items:
            review_items = ["血常规", "心电图"]

        precautions = list(_PRECAUTIONS.get(primary, [
            "遵医嘱规律服药，勿自行停药或加量",
            "保持健康作息，清淡饮食",
            "症状加重或出现新发不适及时就诊",
        ]))

        alerts = drug.get("contraindication_alerts") or []
        if alerts:
            precautions.append("用药存在禁忌/慎用提示，请严格遵医嘱并复核相互作用")

        return {
            "next_visit": next_visit,
            "review_items": review_items[:8],
            "precautions": precautions[:8],
        }
