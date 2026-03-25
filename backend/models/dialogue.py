from __future__ import annotations

from pydantic import BaseModel, Field


class DialogueSegment(BaseModel):
    speaker: str = Field(default="unknown")
    start: float = 0.0
    end: float = 0.0
    text: str = ""

    @property
    def duration(self) -> float:
        return max(self.end - self.start, 0.0)
