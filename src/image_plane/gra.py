"""GRA publication payload. Image Plane stays master. Approved copies only."""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from PIL import Image, ImageOps

from . import cabinet
from . import paths

CURATED_MAX = 1600


def _derivative(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() in paths.VIDEO_EXTS:
        shutil.copy2(src, dest)
        return dest
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        img.thumbnail((CURATED_MAX, CURATED_MAX), Image.Resampling.LANCZOS)
        # Strip EXIF/GPS by saving a fresh JPEG.
        img.save(dest, format="JPEG", quality=85)
    return dest


def prepare_publication(
    conn: sqlite3.Connection,
    job_ref: str,
    selection_name: str,
    *,
    gra_event_ref: str | None = None,
    dest_dir: Path | None = None,
) -> dict:
    sel = cabinet.get_selection(conn, job_ref, selection_name)
    if not sel:
        raise KeyError(f"no saved selection {selection_name!r} for {job_ref}")
    items = [i for i in sel["items"] if i]
    approved = [i for i in items if i.get("visibility") in {"approved", "published"}]
    rejected = [i for i in items if i.get("visibility") not in {"approved", "published"}]

    dest_dir = dest_dir or (paths.gra_export_dir() / job_ref / selection_name)
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True)

    copied = []
    for item in approved:
        src = Path(item["cabinet_path"])
        if not src.is_file():
            continue
        dest = dest_dir / f"{item['id']}-{item['file_hash'][:12]}{src.suffix.lower() if item['media_kind']=='video' else '.jpg'}"
        _derivative(src, dest)
        copied.append(
            {
                "cabinet_id": item["id"],
                "file_hash": item["file_hash"],
                "source_path": item["source_path"],
                "gra_file": dest.name,
                "visibility": item["visibility"],
                "observation_confirmed": item.get("observation_confirmed"),
                "observation_source": item.get("observation_source"),
            }
        )
        cabinet.set_visibility(conn, [item["id"]], "published")

    payload = {
        "job_ref": job_ref,
        "site_identity": paths.site_name(job_ref),
        "selection": selection_name,
        "gra_event_ref": gra_event_ref,
        "image_plane_master": True,
        "approved_copied": copied,
        "unapproved_excluded": [
            {"cabinet_id": i["id"], "visibility": i.get("visibility"), "file_hash": i.get("file_hash")}
            for i in rejected
        ],
        "blocker": None if gra_event_ref else (
            "No existing correctly identified GRA visit/billable event was supplied. "
            "Payload is complete. Do not invent a visit."
        ),
        "customer_route": "unapproved images are absent from this export",
    }
    payload_path = dest_dir / "publication_payload.json"
    payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    cabinet.record_publication(
        conn,
        job_ref=job_ref,
        selection_name=selection_name,
        kind="gra",
        output_path=str(dest_dir),
        item_ids=[i["id"] for i in approved],
        gra_event_ref=gra_event_ref,
        payload_path=str(payload_path),
    )
    return payload


def customer_visible_hashes(export_dir: Path) -> set[str]:
    payload_path = export_dir / "publication_payload.json"
    if not payload_path.is_file():
        return set()
    data = json.loads(payload_path.read_text())
    return {row["file_hash"] for row in data.get("approved_copied") or []}
