from __future__ import annotations

from typing import List

from models.dialogue import DialogueSegment


class DiarizationService:
    def assign_roles(self, dialogues: List[DialogueSegment]) -> List[DialogueSegment]:
        labeled: List[DialogueSegment] = []
        current_speaker = "patient"
        for segment in dialogues:
            text = segment.text.strip()
            if "？" in text or "?" in text:
                current_speaker = "doctor"
            labeled.append(segment.model_copy(update={"speaker": current_speaker}))
            if current_speaker == "doctor":
                current_speaker = "patient"
        return labeled
