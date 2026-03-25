from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class TaskResult(BaseModel):
    success: bool
    message: str = ""
    payload: Optional[Any] = None
