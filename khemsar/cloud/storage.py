"""Portable cloud sync (Google Drive, Dropbox, TeraBox 1 TB), folder-link helpers, OAuth PKCE & Colab export."""

from __future__ import annotations

import base64
import hashlib
import os
import platform
import re
import secrets
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlencode


def detect_cloud_sync_folders() -> list[dict[str, str]]:
    """Detect local desktop sync directories for Google Drive, Dropbox, and TeraBox across OSes."""
    home = Path.home()
    candidates: list[tuple[str, str, list[Path]]] = [
        (
            "terabox",
            "TeraBox (1 TB Free)",
            [
                home / "TeraBox",
                home / "Documents" / "TeraBox",
                home / "Downloads" / "TeraBox",
                home / "Library" / "CloudStorage" / "TeraBox",
            ],
        ),
        (
            "gdrive",
            "Google Drive (Gmail)",
            [
                home / "Google Drive",
                home / "My Drive",
                home / "Drive",
                *(list((home / "Library" / "CloudStorage").glob("GoogleDrive-*")) if (home / "Library" / "CloudStorage").exists() else []),
            ],
        ),
        (
            "dropbox",
            "Dropbox",
            [
                home / "Dropbox",
                home / "Library" / "CloudStorage" / "Dropbox",
            ],
        ),
    ]

    found: list[dict[str, str]] = []
    for provider_id, label, paths in candidates:
        existing = next((p for p in paths if p.exists() and p.is_dir()), None)
        found.append(
            {
                "provider": provider_id,
                "label": label,
                "detected_path": str(existing) if existing else "",
                "status": "detected" if existing else "not_detected_locally",
            }
        )
    return found


def extract_google_drive_file_id(url: str) -> str | None:
    """Extract a Google Drive file ID from standard share links."""
    if not url:
        return None
    patterns = [
        r"drive\.google\.com/file/d/([A-Za-z0-9_-]+)",
        r"drive\.google\.com/open\?id=([A-Za-z0-9_-]+)",
        r"drive\.google\.com/uc\?[^#]*\bid=([A-Za-z0-9_-]+)",
    ]
    for pat in patterns:
        m = re.search(pat, url.strip())
        if m:
            return m.group(1)
    return None


def build_google_drive_direct_download_url(url: str) -> str | None:
    """Convert a shared Google Drive file link into a direct-download URL."""
    fid = extract_google_drive_file_id(url)
    if not fid:
        return None
    return f"https://drive.google.com/uc?export=download&id={fid}"


def open_local_folder_in_file_manager(path: Path | str) -> bool:
    """Reveal a local directory in Finder (macOS), Explorer (Windows), or xdg-open (Linux)."""
    target = Path(path).expanduser().resolve()
    folder = target if target.is_dir() else target.parent
    if not folder.exists():
        return False
    sys_name = platform.system()
    try:
        if sys_name == "Darwin":
            subprocess.Popen(["open", str(folder)])
            return True
        if sys_name == "Windows":
            os.startfile(str(folder))  # type: ignore[attr-defined]
            return True
        subprocess.Popen(["xdg-open", str(folder)])
        return True
    except Exception:
        return False


def generate_pkce_pair() -> tuple[str, str]:
    """Generate OAuth 2.0 PKCE code_verifier and S256 code_challenge."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_google_drive_oauth_url(client_id: str, redirect_uri: str, code_challenge: str) -> str:
    params = {
        "client_id": client_id.strip(),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/drive.file openid email",
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def build_dropbox_oauth_url(app_key: str, redirect_uri: str, code_challenge: str) -> str:
    params = {
        "client_id": app_key.strip(),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "token_access_type": "offline",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"https://www.dropbox.com/oauth2/authorize?{urlencode(params)}"


def sync_bundle_to_folder(bundle_path: Path | str, target_folder: Path | str) -> dict[str, Any]:
    """Copy a portable .qsarproj.zip bundle into a cloud-synced directory (TeraBox/Drive/Dropbox)."""
    src = Path(bundle_path).expanduser().resolve()
    dst_dir = Path(target_folder).expanduser().resolve() / "KhemSAR_Backups"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    shutil.copy2(src, dst)
    return {"ok": True, "synced_path": str(dst), "size_bytes": dst.stat().st_size}


def build_colab_notebook(project_name: str, target_query: str = "PTGS2") -> dict[str, Any]:
    """Generate a Google Colab .ipynb notebook with Google Drive mount & KhemSAR workflow."""
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                f"# KhemSAR — Google Colab Cloud Runner ({project_name})\n",
                "Run heavy QSAR hyperparameter searches, Y-scrambling, and 3D ETKDGv3/MMFF94 conformer generation on free Google Colab compute and save outputs directly to your Google Drive.\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 1. Mount Google Drive (sign in with your Gmail account)\n",
                "from google.colab import drive\n",
                "drive.mount('/content/drive')\n",
                "WORK_DIR = '/content/drive/MyDrive/KhemSAR_Projects'\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 2. Install KhemSAR directly from GitHub\n",
                "!pip install -q git+https://github.com/Sbolivar16/KhemSAR.git\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                f"# 3. Run reproducible curation + QSAR + De Novo pipeline for {target_query}\n",
                "import asyncio, os\n",
                "from khemsar.connectors.orchestrator import run_multidb_search\n",
                "from khemsar.chemistry.curation import curate_bioactivity_dataset, CurationConfig\n",
                "from khemsar.qsar.modeling import train_and_validate_qsar, QSARTrainConfig\n\n",
                f"raw = asyncio.run(run_multidb_search('{target_query}', max_records=1500))\n",
                "curated = curate_bioactivity_dataset(raw['bioactivities'], CurationConfig())\n",
                "os.makedirs(WORK_DIR, exist_ok=True)\n",
                "model_path = os.path.join(WORK_DIR, 'qsar_bundle.joblib')\n",
                "qsar_res = train_and_validate_qsar(curated['curated_records'], QSARTrainConfig(), artifact_path=model_path)\n",
                "print('Best QSAR:', qsar_res['best_algorithm'], qsar_res['best_metrics'])\n",
            ],
        },
    ]
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "colab": {"name": f"KhemSAR_{project_name}.ipynb", "provenance": []},
        },
        "cells": cells,
    }
