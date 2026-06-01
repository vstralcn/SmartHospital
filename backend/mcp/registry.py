from __future__ import annotations

from typing import Any, Dict, List

from .disease_server import DiseaseServer
from .drug_server import DrugServer
from .lab_server import LabServer


class MCPRegistry:
    """Routes tool calls to the appropriate simulated MCP server.

    Agents never touch the servers directly; they call ``registry.call`` with
    a tool name, which keeps the Model Context Protocol boundary explicit and
    mirrors how a real MCP client dispatches requests to multiple servers.
    """

    def __init__(self) -> None:
        self.servers = {
            "drug": DrugServer(),
            "disease": DiseaseServer(),
            "lab": LabServer(),
        }
        # Flat map of tool_name -> server_key for convenient dispatch.
        self._tool_index: Dict[str, str] = {}
        for key, server in self.servers.items():
            for tool in server.list_tools():
                self._tool_index[tool["name"]] = key

    def list_servers(self) -> List[Dict[str, Any]]:
        return [
            {
                "server": key,
                "name": server.name,
                "tools": server.list_tools(),
            }
            for key, server in self.servers.items()
        ]

    def call(self, tool_name: str, **kwargs: Any) -> Dict[str, Any]:
        server_key = self._tool_index.get(tool_name)
        if server_key is None:
            return {"ok": False, "error": f"未注册的工具: {tool_name}", "data": None}
        return self.servers[server_key].call_tool(tool_name, **kwargs)

    # Convenience wrappers used by the agents -----------------------------
    def search_drug(self, name: str) -> Dict[str, Any]:
        return self.call("search_drug", name=name)

    def check_contraindication(
        self, name: str, conditions: List[str] | None = None
    ) -> Dict[str, Any]:
        return self.call("check_contraindication", name=name, conditions=conditions or [])

    def query_disease(self, name: str) -> Dict[str, Any]:
        return self.call("query_disease", name=name)

    def match_by_symptoms(self, symptoms: List[str] | None = None) -> Dict[str, Any]:
        return self.call("match_by_symptoms", symptoms=symptoms or [])

    def query_lab(self, name: str) -> Dict[str, Any]:
        return self.call("query_lab", name=name)
