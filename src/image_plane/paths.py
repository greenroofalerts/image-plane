"""Default on-machine locations. Override with IMAGE_PLANE_ROOT."""

from __future__ import annotations

import os
from pathlib import Path

PANCRAS_JOB = "1892-26"
PANCRAS_SITE = "Greengage, 6 Pancras Square"
MESH_HOST = "192.168.178.61"
DEFAULT_PORT = 8790

# Display names only — never used as an identity lane.
KNOWN_SITES = {
    "1892-26": "Greengage, 6 Pancras Square",
    "1831-25": "3 Pancras Square",
    "1124-19": "Trinity Crescent",
}

IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".tiff", ".tif", ".bmp", ".webp", ".heic", ".heif",
}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".3gp"}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS


def root() -> Path:
    env = os.environ.get("IMAGE_PLANE_ROOT")
    if env:
        return Path(env).expanduser()
    mini = Path("/Users/macminia/image-plane")
    if mini.exists():
        return mini
    return Path.home() / "image-plane"


def incoming_google() -> Path:
    return root() / "incoming" / "google"


def pancras_incoming() -> Path:
    return incoming_google() / PANCRAS_JOB


def cabinet_dir() -> Path:
    return Path(os.environ.get("IMAGE_PLANE_CABINET") or (root() / "cabinet"))


def media_dir() -> Path:
    return cabinet_dir() / "media"


def thumbs_dir() -> Path:
    return cabinet_dir() / "thumbs"


def exports_dir() -> Path:
    return cabinet_dir() / "exports"


def gra_export_dir() -> Path:
    return cabinet_dir() / "gra_export"


def lock_path() -> Path:
    return cabinet_dir() / "writer.lock"


def job_url(job_ref: str, host: str | None = None, port: int = DEFAULT_PORT) -> str:
    host = host or os.environ.get("IMAGE_PLANE_HOST") or MESH_HOST
    return f"http://{host}:{port}/job/{job_ref}"


def site_name(job_ref: str | None) -> str:
    if not job_ref:
        return "unknown"
    names_path = root() / "grind" / "site_names.json"
    if names_path.exists():
        try:
            import json

            data = json.loads(names_path.read_text())
            if isinstance(data, dict) and data.get(job_ref):
                return str(data[job_ref])
        except (OSError, ValueError):
            pass
    return KNOWN_SITES.get(job_ref, "unknown")
