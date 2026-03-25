from __future__ import annotations

from typing import Any, List

from pydantic import BaseModel, Field

from models.emr import StructuredEMR


class ExportPayload(BaseModel):
    transcript: List[Any] = Field(default_factory=list)
    structured: Any = Field(default_factory=StructuredEMR)
    emr_text: str = ""
    emr_html: str = ""
    risk_alerts: List[str] = Field(default_factory=list)
    source_audio: str = ""
