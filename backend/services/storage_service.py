from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


class StorageService:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.settings_path = self.root_dir / "config" / "settings.yaml"
        self.settings = self._load_settings()
        self.output_dir = self.root_dir / self.settings.get("app", {}).get(
            "output_dir", "data/output"
        )
        self.temp_dir = self.root_dir / "data" / "temp"
        self.sample_dir = self.root_dir / "data" / "samples"

    def _load_settings(self) -> Dict[str, Any]:
        if not self.settings_path.exists():
            return {}
        return yaml.safe_load(self.settings_path.read_text(encoding="utf-8")) or {}

    def get_runtime_settings(self, active_model: Any | None = None) -> Dict[str, Any]:
        settings = dict(self.settings)
        settings.setdefault("generation", {})
        settings["generation"].setdefault("refresh_interval_seconds", 5)
        if active_model is None:
            return settings
        settings["llm"] = {
            "provider": active_model.provider,
            "model": active_model.model,
            "api_key": active_model.api_key,
            "base_url": active_model.base_url,
            "temperature": active_model.temperature,
        }
        return settings

    def save_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        from utils.file_utils import ensure_directory

        ensure_directory(self.settings_path.parent)
        self.settings_path.write_text(
            yaml.safe_dump(settings, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        self.settings = settings
        self.output_dir = self.root_dir / self.settings.get("app", {}).get(
            "output_dir", "data/output"
        )
        return self.settings

    def ensure_runtime_layout(self) -> None:
        from utils.file_utils import ensure_directory

        for path in (self.output_dir, self.temp_dir, self.sample_dir):
            ensure_directory(path)
