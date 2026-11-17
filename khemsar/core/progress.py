"""Thread-safe real-time progress tracker for long-running KhemSAR scientific tasks."""

from __future__ import annotations

import threading
import time
from typing import Any

_LOCK = threading.Lock()
_PROGRESS: dict[str, dict[str, Any]] = {}


def set_progress(
    project_id: str,
    percent: int,
    detail: str,
    active: bool = True,
) -> None:
    """Update real-time progress percentage (0-100) and stage message for a project."""
    if not project_id:
        return
    pct = max(0, min(100, int(percent)))
    with _LOCK:
        _PROGRESS[project_id] = {
            "project_id": project_id,
            "percent": pct,
            "detail": detail,
            "active": active,
            "updated_at": time.time(),
        }


def get_progress(project_id: str) -> dict[str, Any]:
    """Return latest progress snapshot for a project."""
    with _LOCK:
        entry = _PROGRESS.get(project_id)
        if not entry:
            return {
                "project_id": project_id,
                "percent": 0,
                "detail": "",
                "active": False,
                "updated_at": 0.0,
            }
        return dict(entry)
