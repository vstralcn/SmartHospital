from __future__ import annotations

import json
from pathlib import Path
from typing import List

from models.emr import StructuredEMR
from utils.json_utils import parse_json_from_text


class LLMService:
    def __init__(self, provider, prompt_dir: Path) -> None:
        self.provider = provider
        self.prompt_dir = prompt_dir

    def extract_structured_info(self, dialogues):
        prompt_template = self.load_prompt("structured_extract.txt")
        prompt = json.dumps(
            {
                "dialogues": [item.model_dump() for item in dialogues],
            },
            ensure_ascii=False,
        )
        response = self.provider.generate(
            prompt,
            system_prompt=self._build_system_prompt(
                "structured_extract", prompt_template
            ),
        )
        parsed_payload = parse_json_from_text(response)
        return StructuredEMR.model_validate(parsed_payload)

    def generate_emr(self, structured_info) -> str:
        prompt_template = self.load_prompt("emr_generation.txt")
        prompt = json.dumps(
            {
                "structured": structured_info.model_dump(),
            },
            ensure_ascii=False,
        )
        return self.provider.generate(
            prompt,
            system_prompt=self._build_system_prompt("emr_generation", prompt_template),
        )

    def generate_aligned_emr(self, dialogues):
        prompt_template = self.load_prompt("aligned_emr_generation.txt")
        prompt = json.dumps(
            {
                "dialogues": [item.model_dump() for item in dialogues],
            },
            ensure_ascii=False,
        )
        response = self.provider.generate(
            prompt,
            system_prompt=self._build_system_prompt(
                "aligned_emr_generation", prompt_template
            ),
        )
        parsed_payload = parse_json_from_text(response)
        structured = StructuredEMR.model_validate(parsed_payload.get("structured", {}))
        emr_text = str(parsed_payload.get("emr_text", "") or "")
        return structured, emr_text

    def risk_check(self, dialogues, structured_info, emr_text: str):
        prompt_template = self.load_prompt("risk_check.txt")
        prompt = json.dumps(
            {
                "dialogues": [item.model_dump() for item in dialogues],
                "structured": structured_info.model_dump(),
                "emr_text": emr_text,
            },
            ensure_ascii=False,
        )
        response = self.provider.generate(
            prompt,
            system_prompt=self._build_system_prompt("risk_check", prompt_template),
        )
        try:
            parsed_payload = parse_json_from_text(response)
            if isinstance(parsed_payload, list):
                return [
                    str(item).strip() for item in parsed_payload if str(item).strip()
                ]
        except Exception:
            pass
        return self._fallback_risk_alerts_from_text(response)

    def load_prompt(self, prompt_name: str) -> str:
        prompt_path = self.prompt_dir / prompt_name
        if not prompt_path.exists():
            return ""
        return prompt_path.read_text(encoding="utf-8")

    def _build_system_prompt(self, task_name: str, prompt_template: str) -> str:
        template = prompt_template.strip()
        if not template:
            return task_name
        return f"{task_name}\n\n{template}"

    def _fallback_risk_alerts_from_text(self, response_text: str) -> List[str]:
        text = (response_text or "").strip()
        if not text:
            return []

        lowered = text.lower()
        if lowered in {"[]", "none", "null"}:
            return []
        if any(
            token in text for token in ["无明显", "未见", "无风险", "暂无风险", "无"]
        ):
            return []

        lines = [
            line.strip(" -\t\r\n*0123456789.、")
            for line in text.splitlines()
            if line.strip()
        ]
        cleaned = [line for line in lines if line]
        if cleaned:
            return cleaned[:8]
        return [text[:120]]
