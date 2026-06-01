from __future__ import annotations

from typing import Any, Dict, List

from .base_server import MCPServer, MCPTool


class DrugServer(MCPServer):
    """Mock MCP server exposing drug lookup and contraindication checks."""

    table_name = "mcp_drugs"
    seed_file = "drugs.json"

    def register_tools(self) -> None:
        self.add_tool(
            MCPTool(
                name="search_drug",
                description="按药品名称或别名查询药物说明、用法、禁忌与相互作用。",
                parameters={
                    "name": {"type": "string", "description": "药品名称，如『阿司匹林』"}
                },
                handler=self.search_drug,
            )
        )
        self.add_tool(
            MCPTool(
                name="check_contraindication",
                description="根据患者已知病史/状态列表，检查指定药物是否存在禁忌或慎用。",
                parameters={
                    "name": {"type": "string", "description": "药品名称"},
                    "conditions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "患者病史或当前状态关键词列表",
                    },
                },
                handler=self.check_contraindication,
            )
        )

    def search_drug(self, name: str) -> Dict[str, Any] | None:
        return self._find_one(name)

    def check_contraindication(
        self, name: str, conditions: List[str] | None = None
    ) -> Dict[str, Any]:
        drug = self._find_one(name)
        conditions = conditions or []
        if drug is None:
            return {"drug": name, "found": False, "hits": [], "safe": True}

        hits: List[str] = []
        contra_text = "；".join(drug.get("contraindications", []))
        for condition in conditions:
            token = (condition or "").strip()
            if token and token in contra_text:
                hits.append(token)
        return {
            "drug": drug.get("name", name),
            "found": True,
            "contraindications": drug.get("contraindications", []),
            "hits": hits,
            "safe": not hits,
        }
