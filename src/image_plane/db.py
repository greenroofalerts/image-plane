"""SQLite metadata store for image-plane.

One row per ingested file. Captioning and dedup write back into the same
table / a companion duplicates table, so every stage is resumable by
querying for rows it has not touched yet.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path.home() / "image-plane" / "image_plane.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    file_hash TEXT NOT NULL,
    phash TEXT,
    source TEXT NOT NULL,
    taken_at TEXT,
    gps_lat REAL,
    gps_lon REAL,
    width INTEGER,
    height INTEGER,
    bytes INTEGER,
    caption TEXT,
    tags TEXT,
    caption_model TEXT,
    captioned_at TEXT,
    ingested_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_photos_file_hash ON photos(file_hash);
CREATE INDEX IF NOT EXISTS idx_photos_phash ON photos(phash);

-- LEE-559: poison-file log. A path lands here when ingest cannot read it
-- (permissions, truncation, corrupt container). Reruns skip these paths
-- unless --retry-errors is passed, so one bad file can never wedge the
-- batch into a crash loop.
CREATE TABLE IF NOT EXISTS ingest_errors (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    error TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS duplicates (
    id INTEGER PRIMARY KEY,
    photo_id INTEGER NOT NULL REFERENCES photos(id),
    dup_of INTEGER NOT NULL REFERENCES photos(id),
    kind TEXT NOT NULL CHECK (kind IN ('exact', 'near')),
    distance INTEGER,
    detected_at TEXT NOT NULL,
    UNIQUE (photo_id, dup_of, kind)
);

-- Image Plane V1 cabinet: master evidence records. Originals are copied
-- into the cabinet store; incoming/Google files are never deleted.
CREATE TABLE IF NOT EXISTS cabinet_items (
    id INTEGER PRIMARY KEY,
    file_hash TEXT NOT NULL,
    media_kind TEXT NOT NULL CHECK (media_kind IN ('image', 'video')),
    original_path TEXT NOT NULL,
    cabinet_path TEXT NOT NULL,
    thumb_path TEXT,
    source_album TEXT,
    source_album_id TEXT,
    source_path TEXT NOT NULL,
    staged_job_ref TEXT,
    filed_job_ref TEXT,
    site_identity TEXT,
    identity_status TEXT NOT NULL CHECK (
        identity_status IN ('resolved', 'quarantined', 'ladder_blocked')
    ),
    identity_evidence TEXT NOT NULL,
    capture_date TEXT,
    phase TEXT,
    roof_area TEXT,
    component TEXT,
    condition_defect TEXT,
    work_action TEXT,
    before_after TEXT,
    observation_confirmed TEXT,
    observation_source TEXT,
    observation_machine TEXT,
    confirmation_state TEXT NOT NULL DEFAULT 'unconfirmed',
    visibility TEXT NOT NULL DEFAULT 'private' CHECK (
        visibility IN ('private', 'approved', 'published')
    ),
    duplicate_of INTEGER REFERENCES cabinet_items(id),
    photo_id INTEGER,
    ingested_at TEXT NOT NULL,
    UNIQUE (original_path, file_hash)
);
CREATE INDEX IF NOT EXISTS idx_cabinet_hash ON cabinet_items(file_hash);
CREATE INDEX IF NOT EXISTS idx_cabinet_filed ON cabinet_items(filed_job_ref);
CREATE INDEX IF NOT EXISTS idx_cabinet_staged ON cabinet_items(staged_job_ref);
CREATE INDEX IF NOT EXISTS idx_cabinet_status ON cabinet_items(identity_status);

CREATE TABLE IF NOT EXISTS cabinet_selections (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    job_ref TEXT NOT NULL,
    item_ids TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (job_ref, name)
);

CREATE TABLE IF NOT EXISTS cabinet_albums (
    id INTEGER PRIMARY KEY,
    album_id TEXT UNIQUE NOT NULL,
    title TEXT,
    discovered_at TEXT NOT NULL,
    processed_at TEXT,
    identity_status TEXT,
    identity_evidence TEXT,
    source TEXT
);

CREATE TABLE IF NOT EXISTS cabinet_publications (
    id INTEGER PRIMARY KEY,
    selection_name TEXT NOT NULL,
    job_ref TEXT NOT NULL,
    kind TEXT NOT NULL,
    output_path TEXT NOT NULL,
    item_ids TEXT NOT NULL,
    created_at TEXT NOT NULL,
    gra_event_ref TEXT,
    payload_path TEXT
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
