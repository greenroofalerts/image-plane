"""Bounded Google-album routine. Named-folder ingest is the working path."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import cabinet
from . import identity
from . import paths


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_album(conn, album_id: str, title: str | None, source: str, evidence: dict | None = None) -> dict:
    now = _utcnow()
    conn.execute(
        """INSERT INTO cabinet_albums (album_id, title, discovered_at, identity_status, identity_evidence, source)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(album_id) DO UPDATE SET
             title = COALESCE(excluded.title, cabinet_albums.title),
             identity_status = COALESCE(excluded.identity_status, cabinet_albums.identity_status),
             identity_evidence = COALESCE(excluded.identity_evidence, cabinet_albums.identity_evidence)""",
        (
            album_id,
            title,
            now,
            (evidence or {}).get("identity_status"),
            json.dumps(evidence or {}),
            source,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM cabinet_albums WHERE album_id = ?", (album_id,)).fetchone()
    return {k: row[k] for k in row.keys()}


def unprocessed_albums(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM cabinet_albums WHERE processed_at IS NULL ORDER BY discovered_at"
    ).fetchall()
    return [{k: r[k] for k in r.keys()} for r in rows]


def mark_processed(conn, album_id: str) -> None:
    conn.execute(
        "UPDATE cabinet_albums SET processed_at = ? WHERE album_id = ?",
        (_utcnow(), album_id),
    )
    conn.commit()


def discover_google_albums(conn) -> dict:
    """List albums if credentials exist. Never invent a working Photos client."""
    token_paths = [
        Path(os.environ["GOOGLE_PHOTOS_TOKEN"]) if os.environ.get("GOOGLE_PHOTOS_TOKEN") else None,
        paths.root() / ".google-photos-token.json",
        paths.root() / "google_photos_token.json",
        Path.home() / ".config" / "image-plane" / "google-photos-token.json",
    ]
    found = [p for p in token_paths if p and p.is_file()]
    if not found:
        return {
            "ok": False,
            "blocker": (
                "Authenticated Google album discovery cannot operate unattended: "
                "no token at IMAGE_PLANE_ROOT/.google-photos-token.json "
                "or GOOGLE_PHOTOS_TOKEN. Named-folder ingest remains the working route."
            ),
            "working_route": "image-plane file ~/image-plane/incoming/google/<album-or-job>",
            "albums": [],
        }
    return {
        "ok": False,
        "blocker": (
            f"A token file exists at {found[0]}, but this process has no live "
            "Google Photos Library session in Mini A credential context. "
            "Named-folder ingest remains the working route."
        ),
        "working_route": "image-plane file ~/image-plane/incoming/google/<album-or-job>",
        "albums": [],
        "token_path": str(found[0]),
    }


def ingest_named_album(
    conn,
    folder: Path,
    *,
    stage_job: str | None = None,
    album_title: str | None = None,
    album_id: str | None = None,
) -> dict:
    folder = folder.expanduser().resolve()
    album_title = album_title or folder.name
    album_id = album_id or f"folder:{folder}"
    extracted = identity.extract_job_ref(album_title)
    # Album title is a ladder input, not a minted job.
    evidence = {
        "album_title": album_title,
        "extracted_ref": extracted,
        "minted_job": False,
        "identity_status": "pending",
    }
    if extracted and not stage_job:
        # Stage against the named ref so the job screen can show quarantine.
        # Filing still requires two ladder lanes.
        stage_job = extracted
        evidence["staged_from_title"] = True
    record_album(conn, album_id, album_title, "named-folder", evidence)
    counts = cabinet.file_folder(
        conn,
        folder,
        stage_job=stage_job,
        album_title=album_title,
        album_id=album_id,
    )
    mark_processed(conn, album_id)
    return {"album_id": album_id, "title": album_title, "stage_job": stage_job, "counts": counts}
