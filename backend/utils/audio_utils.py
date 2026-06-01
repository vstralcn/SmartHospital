from __future__ import annotations

from pathlib import Path

SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac"}


def is_supported_audio_file(file_path: Path) -> bool:
    return file_path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
