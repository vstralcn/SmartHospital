from __future__ import annotations

import json
from pathlib import Path

from models.dialogue import DialogueSegment


class AsrService:
    def __init__(self, sample_dir: Path) -> None:
        self.sample_dir = sample_dir

    def transcribe(self, audio_path: str | Path):
        audio_path = Path(audio_path)
        candidate_json = audio_path.with_suffix(".json")
        if candidate_json.exists():
            return self._load_segments(candidate_json)

        bundled_sample = self.sample_dir / "demo_transcript.json"
        if bundled_sample.exists():
            return self._load_segments(bundled_sample)

        return [
            DialogueSegment(speaker="unknown", start=0.0, end=2.8, text="医生，我这两天胸口有点闷。"),
            DialogueSegment(speaker="unknown", start=2.9, end=4.2, text="持续多久了？有没有胸痛？"),
            DialogueSegment(speaker="unknown", start=4.3, end=8.0, text="大概两天，没有明显胸痛，活动后会更明显一点。"),
        ]

    def _load_segments(self, file_path: Path):
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return [DialogueSegment.model_validate(item) for item in data]
