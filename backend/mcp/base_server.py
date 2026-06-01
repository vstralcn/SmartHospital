from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List

_DATA_DIR = Path(__file__).resolve().parent / "data"
_MCP_DB_PATH = _DATA_DIR / "mcp.db"

# A single shared lock keeps the SQLite access thread-safe across the
# concurrently-running agents that talk to the mock MCP servers.
_DB_LOCK = threading.Lock()


@dataclass
class MCPTool:
    """A single callable tool exposed by an MCP server.

    Mirrors the shape of a Model Context Protocol tool definition: a name,
    a human-readable description, a JSON-schema-like parameter spec and the
    handler that actually performs the lookup.
    """

    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Any] = field(repr=False)

    def to_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class MCPServer:
    """Base class for the simulated MCP servers.

    Each server owns one SQLite table that is lazily seeded from a bundled
    JSON file. Records are stored as a normalized search name plus the raw
    JSON document, which keeps the mock layer simple while still exercising a
    real database round-trip for every tool call.
    """

    table_name: str = ""
    seed_file: str = ""

    def __init__(self) -> None:
        self.name = self.__class__.__name__
        self._tools: Dict[str, MCPTool] = {}
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_table()
        self._seed_if_empty()
        self.register_tools()

    # -- database helpers ---------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(_MCP_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self) -> None:
        with _DB_LOCK, self._connect() as conn:
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {self.table_name} ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "search_name TEXT NOT NULL, "
                "document TEXT NOT NULL)"
            )

    def _seed_if_empty(self) -> None:
        seed_path = _DATA_DIR / self.seed_file
        if not seed_path.exists():
            return
        with _DB_LOCK, self._connect() as conn:
            count = conn.execute(
                f"SELECT COUNT(*) AS c FROM {self.table_name}"
            ).fetchone()["c"]
            if count:
                return
            records: List[Dict[str, Any]] = json.loads(
                seed_path.read_text(encoding="utf-8")
            )
            for record in records:
                names = [record.get("name", "")] + list(record.get("aliases", []))
                search_name = "|".join(n.lower() for n in names if n)
                conn.execute(
                    f"INSERT INTO {self.table_name} (search_name, document) "
                    "VALUES (?, ?)",
                    (search_name, json.dumps(record, ensure_ascii=False)),
                )

    def _find_one(self, query: str) -> Dict[str, Any] | None:
        target = (query or "").strip().lower()
        if not target:
            return None
        with _DB_LOCK, self._connect() as conn:
            rows = conn.execute(
                f"SELECT document FROM {self.table_name}"
            ).fetchall()
        candidates = [json.loads(row["document"]) for row in rows]
        # Exact / alias match first, then substring match on names.
        for doc in candidates:
            names = [doc.get("name", "")] + list(doc.get("aliases", []))
            if any(target == n.lower() for n in names if n):
                return doc
        for doc in candidates:
            names = [doc.get("name", "")] + list(doc.get("aliases", []))
            if any(target in n.lower() or n.lower() in target for n in names if n):
                return doc
        return None

    def _all(self) -> List[Dict[str, Any]]:
        with _DB_LOCK, self._connect() as conn:
            rows = conn.execute(
                f"SELECT document FROM {self.table_name}"
            ).fetchall()
        return [json.loads(row["document"]) for row in rows]

    # -- tool registration / dispatch --------------------------------------
    def register_tools(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def add_tool(self, tool: MCPTool) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> List[Dict[str, Any]]:
        return [tool.to_schema() for tool in self._tools.values()]

    def call_tool(self, tool_name: str, **kwargs: Any) -> Dict[str, Any]:
        tool = self._tools.get(tool_name)
        if tool is None:
            return {"ok": False, "error": f"未知工具: {tool_name}", "data": None}
        try:
            data = tool.handler(**kwargs)
            return {"ok": True, "error": "", "data": data}
        except Exception as exc:  # noqa: BLE001 - mock layer surfaces all errors
            return {"ok": False, "error": str(exc), "data": None}
