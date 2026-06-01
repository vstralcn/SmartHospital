from __future__ import annotations

from typing import Any, Dict, List

from .base_server import MCPServer, MCPTool


class DiseaseServer(MCPServer):
    """Mock MCP server exposing disease knowledge lookup."""

    table_name = "mcp_diseases"
    seed_file = "diseases.json"

    def register_tools(self) -> None:
        self.add_tool(
            MCPTool(
                name="query_disease",
                description="按疾病名称或别名查询典型症状、危险因素、推荐检查与用药。",
                parameters={
                    "name": {"type": "string", "description": "疾病名称，如『冠心病』"}
                },
                handler=self.query_disease,
            )
        )
        self.add_tool(
            MCPTool(
                name="match_by_symptoms",
                description="根据症状关键词列表，返回最可能的候选疾病（按命中症状数排序）。",
                parameters={
                    "symptoms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "症状关键词列表",
                    }
                },
                handler=self.match_by_symptoms,
            )
        )

    def query_disease(self, name: str) -> Dict[str, Any] | None:
        return self._find_one(name)

    def match_by_symptoms(self, symptoms: List[str] | None = None) -> List[Dict[str, Any]]:
        symptoms = symptoms or []
        blob = " ".join(s.lower() for s in symptoms if s)
        scored: List[Dict[str, Any]] = []
        for disease in self._all():
            score = 0
            matched: List[str] = []
            for symptom in disease.get("typical_symptoms", []):
                key = symptom.lower()
                if key and (key in blob or any(tok and tok in key for tok in blob.split())):
                    score += 1
                    matched.append(symptom)
            if score:
                scored.append(
                    {
                        "name": disease.get("name", ""),
                        "icd10": disease.get("icd10", ""),
                        "score": score,
                        "matched_symptoms": matched,
                        "recommended_labs": disease.get("recommended_labs", []),
                        "recommended_drugs": disease.get("recommended_drugs", []),
                    }
                )
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:5]
