"""Installer-pack export from a saved selection."""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from . import cabinet
from . import paths
from . import pdfutil


def export_pack(
    conn: sqlite3.Connection,
    job_ref: str,
    selection_name: str,
    dest_dir: Path | None = None,
) -> Path:
    sel = cabinet.get_selection(conn, job_ref, selection_name)
    if not sel:
        raise KeyError(f"no saved selection {selection_name!r} for {job_ref}")
    items = [i for i in sel["items"] if i]
    dest_dir = dest_dir or (paths.exports_dir() / job_ref / f"{selection_name}-pack")
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    media_dir = dest_dir / "media"
    media_dir.mkdir(parents=True)

    manifest = {
        "job_ref": job_ref,
        "site_identity": paths.site_name(job_ref),
        "selection": selection_name,
        "limitation": None,
        "items": [],
    }
    pages = [
        {
            "title": f"Installer pack — {job_ref}",
            "lines": [
                f"Site: {paths.site_name(job_ref)}",
                f"Selection: {selection_name}",
                "Instructions are only those already confirmed in the cabinet.",
                "Nothing was invented from image appearance.",
            ],
        }
    ]
    confirmed = 0
    for n, item in enumerate(items, 1):
        src = Path(item["cabinet_path"])
        dest_name = f"{n:03d}-{Path(item['source_path']).name}"
        if src.is_file():
            shutil.copy2(src, media_dir / dest_name)
        instruction = item.get("observation_confirmed")
        if instruction:
            confirmed += 1
        else:
            instruction = "unknown — no confirmed observation"
        entry = {
            "order": n,
            "cabinet_id": item["id"],
            "job_ref": item.get("filed_job_ref") or item.get("staged_job_ref") or job_ref,
            "site_identity": item.get("site_identity") or paths.site_name(job_ref),
            "phase": item.get("phase") or "unknown",
            "roof_area": item.get("roof_area") or "unknown",
            "component": item.get("component") or "unknown",
            "instruction": instruction,
            "caption": item.get("observation_confirmed") or "unknown",
            "wording_source": item.get("observation_source") or "none",
            "confirmation_state": item.get("confirmation_state"),
            "source_path": item.get("source_path"),
            "file_hash": item.get("file_hash"),
            "media_file": f"media/{dest_name}",
        }
        manifest["items"].append(entry)
        image = media_dir / dest_name if (media_dir / dest_name).is_file() and item.get("media_kind") == "image" else None
        pages.append(
            {
                "title": f"{n:03d} {Path(item['source_path']).name}",
                "lines": [
                    f"Job: {entry['job_ref']}",
                    f"Phase: {entry['phase']}",
                    f"Location: {entry['roof_area']}",
                    f"Component: {entry['component']}",
                    f"Instruction: {entry['instruction']}",
                    f"Caption: {entry['caption']}",
                    f"Provenance: hash {entry['file_hash']} · {entry['source_path']}",
                    f"Wording: {entry['wording_source']} · {entry['confirmation_state']}",
                ],
                "image": image,
            }
        )

    if confirmed == 0:
        manifest["limitation"] = (
            "No fully evidenced installation instruction set in this selection. "
            "Pack contains the selected files and provenance only."
        )
        pages[0]["lines"].append(manifest["limitation"])

    (dest_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    pdf_path = dest_dir / "pack.pdf"
    pdfutil.write_pdf(pdf_path, pages)
    cabinet.record_publication(
        conn,
        job_ref=job_ref,
        selection_name=selection_name,
        kind="pack",
        output_path=str(dest_dir),
        item_ids=[i["id"] for i in items],
        payload_path=str(dest_dir / "manifest.json"),
    )
    return dest_dir
