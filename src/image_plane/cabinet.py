"""File media into the Image Plane cabinet. Originals are preserved."""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from pathlib import Path

from PIL import Image, ImageOps

from . import db as dbmod
from . import identity
from . import ingest
from . import lock
from . import notes
from . import paths

log = logging.getLogger("image_plane.cabinet")

THUMB_MAX = 640


def _kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in paths.VIDEO_EXTS:
        return "video"
    return "image"


def _copy_original(src: Path, file_hash: str) -> Path:
    dest_dir = paths.media_dir() / file_hash[:2]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{file_hash}{src.suffix.lower()}"
    if dest.exists():
        return dest
    shutil.copy2(src, dest)
    return dest


def _make_thumb(src: Path, file_hash: str, kind: str) -> str | None:
    if kind != "image":
        return None
    dest_dir = paths.thumbs_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{file_hash}.jpg"
    if dest.exists():
        return str(dest)
    try:
        with Image.open(src) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            img.thumbnail((THUMB_MAX, THUMB_MAX), Image.Resampling.LANCZOS)
            img.save(dest, format="JPEG", quality=80)
        return str(dest)
    except Exception as e:
        log.warning("thumb failed for %s: %s", src.name, e)
        return None


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def list_source_files(folder: Path) -> list[Path]:
    folder = folder.expanduser().resolve()
    files = sorted(
        p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in paths.MEDIA_EXTS
    )
    return files


def file_one(
    conn: sqlite3.Connection,
    src: Path,
    *,
    stage_job: str | None = None,
    album_title: str | None = None,
    album_id: str | None = None,
    sources: dict | None = None,
    machine_caption: str | None = None,
) -> dict:
    src = src.expanduser().resolve()
    file_hash = ingest.sha256_file(src)
    existing = conn.execute(
        "SELECT * FROM cabinet_items WHERE original_path = ? AND file_hash = ?",
        (str(src), file_hash),
    ).fetchone()
    if existing:
        return {"status": "skipped", "item": _row_to_dict(existing)}

    kind = _kind(src)
    cabinet_path = _copy_original(src, file_hash)
    thumb = _make_thumb(src, file_hash, kind)

    capture_date = None
    gps_lat = gps_lon = None
    photo_id = None
    if kind == "image":
        try:
            with Image.open(src) as img:
                meta = ingest.parse_exif(img)
            sidecar = ingest.find_sidecar(src)
            if sidecar:
                meta.update(ingest.parse_sidecar(sidecar))
            capture_date = meta.get("taken_at")
            gps_lat, gps_lon = meta.get("gps_lat"), meta.get("gps_lon")
        except Exception as e:
            log.warning("metadata read failed for %s: %s", src.name, e)

    album_sidecar = src.parent / "album.json"
    if album_sidecar.is_file() and not album_title:
        try:
            data = json.loads(album_sidecar.read_text(encoding="utf-8"))
            album_title = data.get("title") or album_title
            album_id = data.get("id") or album_id
        except (OSError, json.JSONDecodeError):
            pass

    evidence = identity.call_ladder(
        {
            "path": str(src),
            "source_path": str(src),
            "absolute_path": str(src),
            "gps_lat": gps_lat,
            "gps_lon": gps_lon,
        },
        album_title=album_title,
        sources=sources,
    )
    status = evidence.get("identity_status") or "quarantined"
    filed = evidence.get("filed_job_ref") if evidence.get("may_file") else None
    if filed:
        status = "resolved"
    elif status != "ladder_blocked":
        status = "quarantined"

    site = paths.site_name(filed or stage_job)
    if site == "unknown":
        site = None

    note_job = filed or stage_job
    matched = notes.match_note(file_hash, str(src), note_job)
    confirmed = matched["text"] if matched else None
    confirmed_source = matched["source"] if matched else None
    confirmation_state = "confirmed" if confirmed else "unconfirmed"

    phase = roof_area = component = condition = work = before_after = None
    ctx = notes.job_context(note_job)
    visit = ctx.get("visit") or {}
    if confirmed and visit.get("kind"):
        phase = visit.get("kind")

    dup = conn.execute(
        "SELECT id FROM cabinet_items WHERE file_hash = ? ORDER BY id LIMIT 1",
        (file_hash,),
    ).fetchone()

    now = dbmod.utcnow()
    cur = conn.execute(
        """INSERT INTO cabinet_items (
            file_hash, media_kind, original_path, cabinet_path, thumb_path,
            source_album, source_album_id, source_path, staged_job_ref, filed_job_ref,
            site_identity, identity_status, identity_evidence, capture_date,
            phase, roof_area, component, condition_defect, work_action, before_after,
            observation_confirmed, observation_source, observation_machine,
            confirmation_state, visibility, duplicate_of, photo_id, ingested_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            file_hash,
            kind,
            str(src),
            str(cabinet_path),
            thumb,
            album_title,
            album_id,
            str(src),
            stage_job,
            filed,
            site,
            status,
            identity.dump_evidence(evidence),
            capture_date,
            phase,
            roof_area,
            component,
            condition,
            work,
            before_after,
            confirmed,
            confirmed_source,
            machine_caption,
            confirmation_state,
            "private",
            dup["id"] if dup else None,
            photo_id,
            now,
        ),
    )
    item_id = cur.lastrowid
    row = conn.execute("SELECT * FROM cabinet_items WHERE id = ?", (item_id,)).fetchone()
    return {"status": status, "item": _row_to_dict(row), "evidence": evidence}


def file_folder(
    conn: sqlite3.Connection,
    folder: Path,
    *,
    stage_job: str | None = None,
    album_title: str | None = None,
    album_id: str | None = None,
) -> dict:
    folder = folder.expanduser().resolve()
    if not folder.is_dir():
        raise NotADirectoryError(folder)
    files = list_source_files(folder)
    counts = {
        "found": len(files),
        "resolved": 0,
        "quarantined": 0,
        "ladder_blocked": 0,
        "skipped": 0,
        "images": 0,
        "videos": 0,
        "originals_unchanged": True,
    }
    with lock.writer_lock():
        sources = None
        engine = identity.load_engine()
        if engine is not None:
            try:
                sources = engine.load_ladder_sources(identity.ladder_base())
            except Exception as e:
                log.warning("ladder sources failed: %s", e)
        for src in files:
            before = src.stat().st_mtime_ns, src.stat().st_size
            result = file_one(
                conn,
                src,
                stage_job=stage_job,
                album_title=album_title or folder.name,
                album_id=album_id,
                sources=sources,
            )
            after = src.stat().st_mtime_ns, src.stat().st_size
            if before != after:
                counts["originals_unchanged"] = False
            status = result["status"]
            counts[status] = counts.get(status, 0) + 1
            if result.get("item", {}).get("media_kind") == "video":
                counts["videos"] += 1
            else:
                counts["images"] += 1
        conn.commit()
    return counts


def items_for_job(conn: sqlite3.Connection, job_ref: str) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM cabinet_items
           WHERE filed_job_ref = ? OR staged_job_ref = ?
           ORDER BY capture_date IS NULL, capture_date, id""",
        (job_ref, job_ref),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_item(conn: sqlite3.Connection, item_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM cabinet_items WHERE id = ?", (item_id,)).fetchone()
    return _row_to_dict(row) if row else None


def save_selection(conn: sqlite3.Connection, job_ref: str, name: str, item_ids: list[int]) -> dict:
    now = dbmod.utcnow()
    payload = json.dumps([int(i) for i in item_ids])
    with lock.writer_lock():
        conn.execute(
            """INSERT INTO cabinet_selections (name, job_ref, item_ids, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(job_ref, name) DO UPDATE SET
                 item_ids = excluded.item_ids,
                 updated_at = excluded.updated_at""",
            (name, job_ref, payload, now, now),
        )
        conn.commit()
    row = conn.execute(
        "SELECT * FROM cabinet_selections WHERE job_ref = ? AND name = ?",
        (job_ref, name),
    ).fetchone()
    return _row_to_dict(row)


def get_selection(conn: sqlite3.Connection, job_ref: str, name: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM cabinet_selections WHERE job_ref = ? AND name = ?",
        (job_ref, name),
    ).fetchone()
    if not row:
        return None
    data = _row_to_dict(row)
    data["item_ids"] = json.loads(data["item_ids"])
    data["items"] = [get_item(conn, i) for i in data["item_ids"] if get_item(conn, i)]
    return data


def list_selections(conn: sqlite3.Connection, job_ref: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM cabinet_selections WHERE job_ref = ? ORDER BY updated_at DESC",
        (job_ref,),
    ).fetchall()
    out = []
    for r in rows:
        d = _row_to_dict(r)
        d["item_ids"] = json.loads(d["item_ids"])
        out.append(d)
    return out


def set_visibility(conn: sqlite3.Connection, item_ids: list[int], visibility: str) -> int:
    if visibility not in {"private", "approved", "published"}:
        raise ValueError(visibility)
    with lock.writer_lock():
        conn.executemany(
            "UPDATE cabinet_items SET visibility = ? WHERE id = ?",
            [(visibility, int(i)) for i in item_ids],
        )
        conn.commit()
    return len(item_ids)


def set_fields(conn: sqlite3.Connection, item_id: int, fields: dict) -> dict | None:
    allowed = {
        "phase",
        "roof_area",
        "component",
        "condition_defect",
        "work_action",
        "before_after",
        "observation_confirmed",
        "observation_source",
        "confirmation_state",
        "visibility",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_item(conn, item_id)
    if "observation_confirmed" in updates and updates["observation_confirmed"]:
        updates.setdefault("observation_source", "confirmed_decision")
        updates.setdefault("confirmation_state", "confirmed")
    sets = ", ".join(f"{k} = ?" for k in updates)
    with lock.writer_lock():
        conn.execute(f"UPDATE cabinet_items SET {sets} WHERE id = ?", (*updates.values(), item_id))
        conn.commit()
    return get_item(conn, item_id)


def record_publication(
    conn: sqlite3.Connection,
    *,
    job_ref: str,
    selection_name: str,
    kind: str,
    output_path: str,
    item_ids: list[int],
    gra_event_ref: str | None = None,
    payload_path: str | None = None,
) -> dict:
    now = dbmod.utcnow()
    with lock.writer_lock():
        cur = conn.execute(
            """INSERT INTO cabinet_publications
               (selection_name, job_ref, kind, output_path, item_ids, created_at, gra_event_ref, payload_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                selection_name,
                job_ref,
                kind,
                output_path,
                json.dumps(item_ids),
                now,
                gra_event_ref,
                payload_path,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM cabinet_publications WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return _row_to_dict(row)


def latest_publication(conn: sqlite3.Connection, job_ref: str, kind: str) -> dict | None:
    row = conn.execute(
        """SELECT * FROM cabinet_publications
           WHERE job_ref = ? AND kind = ? ORDER BY id DESC LIMIT 1""",
        (job_ref, kind),
    ).fetchone()
    return _row_to_dict(row) if row else None


def item_matches(item: dict, query: str, filters: list[str]) -> bool:
    blob = " ".join(
        str(item.get(k) or "")
        for k in (
            "source_path",
            "source_album",
            "filed_job_ref",
            "staged_job_ref",
            "site_identity",
            "capture_date",
            "phase",
            "roof_area",
            "component",
            "condition_defect",
            "work_action",
            "before_after",
            "observation_confirmed",
            "observation_machine",
            "confirmation_state",
            "visibility",
            "identity_status",
            "media_kind",
        )
    ).lower()
    if query and query.lower() not in blob:
        return False
    for facet in filters:
        token = facet.lower().strip()
        if not token:
            continue
        aliases = FILTER_ALIASES.get(token, [token])
        if not any(a in blob for a in aliases):
            return False
    return True


FILTER_ALIASES = {
    "installation": ["install", "installation"],
    "waterproofing": ["waterproof", "membrane", "epdm", "single ply"],
    "drainage and outlets": ["drainage", "outlet", "gutter", "scupper"],
    "edges and penetrations": ["edge", "penetration", "upstand", "parapet", "skylight"],
    "protection and build-up": ["protection", "build-up", "buildup", "fleece", "geotex"],
    "substrate": ["substrate", "growing medium"],
    "planting and vegetation": ["plant", "vegetation", "sedum", "meadow"],
    "irrigation": ["irrigation", "porous pipe"],
    "maintenance": ["maintenance", "care"],
    "defect": ["defect", "fault", "leak", "failure"],
    "repair": ["repair"],
    "before": ["before"],
    "after": ["after"],
    "private": ["private"],
    "approved": ["approved"],
    "published": ["published"],
}


def filter_items(items: list[dict], query: str = "", filters: list[str] | None = None) -> list[dict]:
    filters = filters or []
    return [i for i in items if item_matches(i, query, filters)]
