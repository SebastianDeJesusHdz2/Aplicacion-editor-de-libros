from __future__ import annotations

import json
import os
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from .models import Project, create_empty_project, now_iso


APP_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(os.environ.get("PESCRITURA_DATA_DIR", APP_ROOT)).expanduser()
LIBRARY_DIR = DATA_ROOT / "library"
EXPORTS_DIR = DATA_ROOT / "exports"
PROJECT_FILE = "project.json"


def ensure_runtime_dirs() -> None:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-")
    return clean or "obra"


def unique_project_dir(title: str) -> Path:
    ensure_runtime_dirs()
    base = LIBRARY_DIR / slugify(title)
    candidate = base
    index = 2
    while (candidate / PROJECT_FILE).exists():
        candidate = LIBRARY_DIR / f"{base.name}-{index}"
        index += 1
    return candidate


def project_file_from_path(path: Path) -> Path:
    if path.is_dir():
        return path / PROJECT_FILE
    return path


def create_project(title: str, author: str = "") -> tuple[Project, Path]:
    project = create_empty_project(title=title, author=author)
    project_dir = unique_project_dir(project.title)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "assets").mkdir(exist_ok=True)
    save_project(project, project_dir)
    return project, project_dir


def load_project(path: Path) -> tuple[Project, Path]:
    project_file = project_file_from_path(path)
    with project_file.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    project = Project.from_dict(data)
    return project, project_file.parent


def save_project(project: Project, project_dir: Path) -> None:
    project.ensure_defaults()
    project.updated_at = now_iso()
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "assets").mkdir(exist_ok=True)
    target = project_dir / PROJECT_FILE
    tmp = target.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(project.to_dict(), handle, ensure_ascii=False, indent=2)
    tmp.replace(target)


def list_projects() -> list[Path]:
    ensure_runtime_dirs()
    return sorted(LIBRARY_DIR.glob(f"*/{PROJECT_FILE}"), key=lambda item: item.stat().st_mtime, reverse=True)


def safe_asset_name(source: Path, existing_names: set[str]) -> str:
    stem = slugify(source.stem)
    suffix = source.suffix.lower() or ".img"
    candidate = f"{stem}{suffix}"
    index = 2
    while candidate in existing_names:
        candidate = f"{stem}-{index}{suffix}"
        index += 1
    return candidate


def copy_asset(project_dir: Path, source_path: Path, namespace: str = "general") -> str:
    assets_dir = project_dir / "assets" / slugify(namespace)
    assets_dir.mkdir(parents=True, exist_ok=True)
    existing = {item.name for item in assets_dir.iterdir() if item.is_file()}
    destination_name = safe_asset_name(source_path, existing)
    destination = assets_dir / destination_name
    shutil.copy2(source_path, destination)
    return destination.relative_to(project_dir).as_posix()


def resolve_asset(project_dir: Path, relative_path: str) -> Path:
    return (project_dir / relative_path).resolve()


def default_pdf_path(project: Project) -> Path:
    ensure_runtime_dirs()
    return EXPORTS_DIR / f"{slugify(project.title)}.pdf"


def default_csv_path(project: Project) -> Path:
    ensure_runtime_dirs()
    return EXPORTS_DIR / f"{slugify(project.title)}.csv"


def create_project_from_csv(csv_path: Path) -> tuple[Project, Path]:
    from .csv_export import import_project_csv

    project = import_project_csv(csv_path)
    project_dir = unique_project_dir(project.title)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "assets").mkdir(exist_ok=True)
    save_project(project, project_dir)
    return project, project_dir


def create_project_backup(project_dir: Path) -> Path:
    project_file = project_dir / PROJECT_FILE
    if not project_file.exists():
        raise FileNotFoundError("No existe project.json para respaldar.")
    backups_dir = project_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backups_dir / f"respaldo-{timestamp}.zip"
    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in project_dir.rglob("*"):
            if item == backup_path or backups_dir in item.parents:
                continue
            if item.is_file():
                archive.write(item, item.relative_to(project_dir))
    return backup_path
