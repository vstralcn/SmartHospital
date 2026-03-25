from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class StructuredEMR(BaseModel):
    chief_complaint: str = ""
    present_illness: str = ""
    past_history: str = ""
    surgical_history: str = ""
    allergy_history: str = ""
    medication_history: str = ""
    family_history: str = ""
    missing_info: List[str] = Field(default_factory=list)
    needs_confirmation: List[str] = Field(default_factory=list)


class EMRGenerationResult(BaseModel):
    structured: StructuredEMR
    emr_text: str
    report_text: str = ""
    risk_alerts: List[str] = Field(default_factory=list)
