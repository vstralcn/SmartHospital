from __future__ import annotations

from typing import Any, Dict

from .base_server import MCPServer, MCPTool


class LabServer(MCPServer):
    """Mock MCP server exposing laboratory / examination knowledge lookup."""

    table_name = "mcp_labs"
    seed_file = "labs.json"

    def register_tools(self) -> None:
        self.add_tool(
            MCPTool(
                name="query_lab",
                description="按检验/检查项目名称查询标本要求、参考范围与临床意义。",
                parameters={
                    "name": {"type": "string", "description": "检查项目名称，如『肌钙蛋白』"}
                },
                handler=self.query_lab,
            )
        )

    def query_lab(self, name: str) -> Dict[str, Any] | None:
        return self._find_one(name)
