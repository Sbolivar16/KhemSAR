"""Cross-platform configuration and runtime settings for KhemSAR."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def default_workspace_root() -> Path:
    """Return a portable user-local workspace directory across macOS, Linux, and Windows."""
    env_dir = os.environ.get("KHEMSAR_WORKSPACE")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return Path.home() / "KhemSAR_Workspaces"


def default_config_path() -> Path:
    """Return portable user-level configuration file path outside the repository."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif os.uname().sysname == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "KhemSAR" / "settings.json"


@dataclass
class AISettings:
    provider: str = "offline"  # offline | ollama | gemini | openai | anthropic
    model: str = "llama3.1"
    ollama_url: str = "http://localhost:11434"
    api_key: str = ""


@dataclass
class CloudSettings:
    sync_provider: str = "local"  # local | terabox | gdrive | dropbox
    custom_sync_dir: str = ""
    cloud_folder_url: str = ""
    gdrive_client_id: str = ""
    dropbox_app_key: str = ""


@dataclass
class AppSettings:
    language: str = "es"  # es | en | pt
    plot_language: str = "en"  # en | match_ui
    workspace_root: str = field(default_factory=lambda: str(default_workspace_root()))
    ai: AISettings = field(default_factory=AISettings)
    cloud: CloudSettings = field(default_factory=CloudSettings)


def load_settings(config_path: Path | None = None) -> AppSettings:
    """Load settings from disk, falling back to safe portable defaults."""
    path = config_path or default_config_path()
    if not path.exists():
        return AppSettings()
    try:
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        ai_raw = raw.get("ai", {})
        cloud_raw = raw.get("cloud", {})
        return AppSettings(
            language=raw.get("language", "es"),
            plot_language=raw.get("plot_language", "en"),
            workspace_root=raw.get("workspace_root", str(default_workspace_root())),
            ai=AISettings(**{k: v for k, v in ai_raw.items() if k in AISettings.__dataclass_fields__}),
            cloud=CloudSettings(
                **{k: v for k, v in cloud_raw.items() if k in CloudSettings.__dataclass_fields__}
            ),
        )
    except Exception:
        return AppSettings()


def save_settings(settings: AppSettings, config_path: Path | None = None) -> Path:
    """Persist settings to the user's local configuration directory."""
    path = config_path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2, ensure_ascii=False), encoding="utf-8")
    return path
