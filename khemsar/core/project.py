"""Project workspace management, audit trail, and portable .qsarproj.zip bundling."""

from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from khemsar.core.config import default_workspace_root


def sanitize_project_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip())
    return cleaned.strip("._") or "KhemSAR_Study"


class ProjectManager:
    """Manages reproducible QSAR/SAR project directories and artifacts."""

    def __init__(self, root_dir: Path | str | None = None) -> None:
        self.root = Path(root_dir).expanduser().resolve() if root_dir else default_workspace_root()
        self.root.mkdir(parents=True, exist_ok=True)

    def create_project(self, name: str, description: str = "", target: str = "") -> dict[str, Any]:
        slug = sanitize_project_name(name)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        proj_id = f"{slug}_{stamp}"
        proj_dir = self.root / proj_id
        for sub in ("raw", "curated", "models", "plots", "sar", "denovo", "docking_ready"):
            (proj_dir / sub).mkdir(parents=True, exist_ok=True)
        meta = {
            "project_id": proj_id,
            "name": name or slug,
            "target": target,
            "description": description,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "steps_completed": [],
            "audit_log": [],
        }
        self.save_json(proj_id, "project.json", meta)
        return meta

    def project_dir(self, project_id: str) -> Path:
        safe = sanitize_project_name(project_id)
        path = (self.root / safe).resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError("Invalid project path.")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def list_projects(self) -> list[dict[str, Any]]:
        projects: list[dict[str, Any]] = []
        if not self.root.exists():
            return projects
        for child in sorted(self.root.iterdir(), reverse=True):
            meta_file = child / "project.json"
            if child.is_dir() and meta_file.exists():
                try:
                    projects.append(json.loads(meta_file.read_text(encoding="utf-8")))
                except Exception:
                    continue
        return projects

    def save_json(self, project_id: str, relative_path: str, payload: Any) -> Path:
        out = self.project_dir(project_id) / relative_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return out

    def load_json(self, project_id: str, relative_path: str) -> Any | None:
        target = self.project_dir(project_id) / relative_path
        if not target.exists():
            return None
        return json.loads(target.read_text(encoding="utf-8"))

    def append_audit(self, project_id: str, step: str, details: dict[str, Any]) -> None:
        meta = self.load_json(project_id, "project.json") or {"project_id": project_id, "audit_log": []}
        meta.setdefault("audit_log", []).append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "step": step,
                "details": details,
            }
        )
        steps = meta.setdefault("steps_completed", [])
        if step not in steps:
            steps.append(step)
        self.save_json(project_id, "project.json", meta)

    def export_bundle(self, project_id: str, dest_dir: Path | str | None = None) -> Path:
        pdir = self.project_dir(project_id)
        out_dir = Path(dest_dir).expanduser().resolve() if dest_dir else self.root
        out_dir.mkdir(parents=True, exist_ok=True)
        archive_path = out_dir / f"{pdir.name}.qsarproj.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for item in pdir.rglob("*"):
                if item.is_file():
                    zf.write(item, arcname=item.relative_to(pdir))
        return archive_path

    def import_bundle(self, archive_path: Path | str) -> dict[str, Any]:
        src = Path(archive_path).expanduser().resolve()
        if not src.exists():
            raise FileNotFoundError(f"Bundle not found: {src}")
        stem = src.name.replace(".qsarproj.zip", "")
        proj_id = sanitize_project_name(stem)
        dest = self.project_dir(proj_id)
        with zipfile.ZipFile(src, "r") as zf:
            for member in zf.namelist():
                member_path = (dest / member).resolve()
                if dest not in member_path.parents and member_path != dest:
                    raise ValueError("Unsafe path inside bundle.")
            zf.extractall(dest)
        return self.load_json(proj_id, "project.json") or {"project_id": proj_id}
