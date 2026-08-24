"""Report output from a named saved selection. Confirmed wording only."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from . import cabinet
from . import notes
from . import paths
from . import pdfutil


def selection_items(conn: sqlite3.Connection, job_ref: str, name: str, confirmed_only: bool = True) -> dict:
    sel = cabinet.get_selection(conn, job_ref, name)
    if not sel:
        raise KeyError(f"no saved selection {name!r} for {job_ref}")
    items = [i for i in sel["items"] if i]
    if confirmed_only:
        items = [i for i in items if i.get("confirmation_state") == "confirmed" and i.get("observation_confirmed")]
    return {"selection": sel, "items": items}


def build_report_pdf(
    conn: sqlite3.Connection,
    job_ref: str,
    selection_name: str,
    dest: Path | None = None,
) -> Path:
    sel = cabinet.get_selection(conn, job_ref, selection_name)
    if not sel:
        raise KeyError(f"no saved selection {selection_name!r} for {job_ref}")
    items = [i for i in sel["items"] if i]
    ctx = notes.job_context(job_ref)
    site = paths.site_name(job_ref)
    existing = ctx.get("existing_report") or {}
    visit = ctx.get("visit") or {}

    dest = dest or (paths.exports_dir() / job_ref / f"{selection_name}-report.pdf")
    pages = []
    header_lines = [
        f"Job {job_ref}",
        f"Site: {site}",
        f"Visit: {visit.get('date') or 'unknown'} — {visit.get('kind') or 'unknown'}",
        f"Selection: {selection_name}",
        "",
        "Image Plane is the master evidence cabinet. This PDF uses the named saved selection.",
        "Only confirmed captions and observations appear with the pictures.",
        "Machine suggestions are excluded.",
    ]
    if existing.get("filename"):
        header_lines.extend(
            [
                "",
                "Existing confirmed write-up (not rewritten):",
                existing["filename"],
                f"Source: {existing.get('source') or 'unknown'} {existing.get('sent_at') or ''}".strip(),
                existing.get("note") or "",
            ]
        )
    pages.append({"title": f"Diagnostic output — {job_ref}", "lines": header_lines})

    used_ids = []
    for item in items:
        if item.get("observation_machine") and not item.get("observation_confirmed"):
            continue
        caption = item.get("observation_confirmed")
        if not caption:
            # Keep the picture out of the customer/technical body if unconfirmed.
            continue
        used_ids.append(item["id"])
        lines = [
            f"Job {item.get('filed_job_ref') or item.get('staged_job_ref') or job_ref}",
            f"Site: {item.get('site_identity') or site}",
            f"Visit / phase: {item.get('phase') or visit.get('kind') or 'unknown'}",
            f"Location: {item.get('roof_area') or 'unknown'}",
            f"Component: {item.get('component') or 'unknown'}",
            f"Capture: {item.get('capture_date') or 'unknown'}",
            f"Source album: {item.get('source_album') or 'unknown'}",
            f"Source file: {item.get('source_path')}",
            f"Hash: {item.get('file_hash')}",
            f"Wording source: {item.get('observation_source') or 'unknown'}",
            f"Confirmation: {item.get('confirmation_state')}",
            "",
            caption,
        ]
        image = None
        if item.get("media_kind") == "image" and item.get("cabinet_path"):
            image = Path(item["cabinet_path"])
            if not image.is_file():
                image = None
        pages.append(
            {
                "title": Path(item.get("source_path") or "").name,
                "lines": lines,
                "image": image,
                "footer": f"Image Plane record {item['id']} · visibility {item.get('visibility')}",
            }
        )

    if len(pages) == 1:
        pages.append(
            {
                "title": "No confirmed image observations in this selection",
                "lines": [
                    "The selection exists, but no item has confirmed wording.",
                    "Machine suggestions were not promoted.",
                ],
            }
        )

    pdfutil.write_pdf(dest, pages)
    cabinet.record_publication(
        conn,
        job_ref=job_ref,
        selection_name=selection_name,
        kind="report",
        output_path=str(dest),
        item_ids=used_ids,
    )
    return dest
