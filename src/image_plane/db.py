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
