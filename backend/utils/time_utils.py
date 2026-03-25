from __future__ import annotations


def format_timestamp(seconds: float) -> str:
    total_seconds = max(int(seconds), 0)
    minutes, remain = divmod(total_seconds, 60)
    return f"{minutes:02d}:{remain:02d}"
