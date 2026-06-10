"""Duplicate detection over already-ingested rows.

Exact dupes: identical sha256 file hash — byte-for-byte copies.
Near dupes: dHash hamming distance <= threshold (default 8) between
files that are NOT exact copies — re-encodes, resizes, mild edits.

Idempotent/resumable: rebuilds the duplicates table from current
photos rows on every run; re-running after new ingests just extends
the result. Within a duplicate group the earliest-ingested row (lowest
id) is kept as canonical and the rest point at it via dup_of.

Near-dupe pass is O(n^2/2) on hashes only (no image reads) — fine into
the hundreds of thousands; we bucket by hash prefix if that ever hurts.
"""

from __future__ import annotations

import logging
import sqlite3
from itertools import combinations

from . import db as dbmod
from .phash import hamming

log = logging.getLogger("image_plane.dedup")

DEFAULT_THRESHOLD = 8


def find_duplicates(conn: sqlite3.Connection, threshold: int = DEFAULT_THRESHOLD) -> dict:
    conn.execute("DELETE FROM duplicates")
    now = dbmod.utcnow()
    rows = conn.execute("SELECT id, file_hash, phash FROM photos ORDER BY id").fetchall()
    if not rows:
        log.info("no photos ingested yet — nothing to dedup")
        return {"exact": 0, "near": 0, "photos": 0}

    # --- exact: group by sha256, first id is canonical
    by_hash: dict[str, list[int]] = {}
    for r in rows:
        by_hash.setdefault(r["file_hash"], []).append(r["id"])
    exact = 0
    exact_member_ids: set[int] = set()
    for ids in by_hash.values():
        canonical, *dupes = ids
        for d in dupes:
            conn.execute(
                "INSERT OR IGNORE INTO duplicates (photo_id, dup_of, kind, distance, detected_at)"
                " VALUES (?, ?, 'exact', 0, ?)",
                (d, canonical, now),
            )
            exact += 1
            exact_member_ids.add(d)

    # --- near: pairwise dHash over one representative per exact group
    reps = [r for r in rows if r["id"] not in exact_member_ids and r["phash"]]
    near = 0
    for a, b in combinations(reps, 2):
        dist = hamming(a["phash"], b["phash"])
        if dist <= threshold:
            conn.execute(
                "INSERT OR IGNORE INTO duplicates (photo_id, dup_of, kind, distance, detected_at)"
                " VALUES (?, ?, 'near', ?, ?)",
                (b["id"], a["id"], dist, now),
            )
            near += 1
    conn.commit()
    log.info("dedup: %d photos, %d exact dupes, %d near dupes (threshold %d)",
             len(rows), exact, near, threshold)
    return {"exact": exact, "near": near, "photos": len(rows)}


def report(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT d.kind, d.distance, p1.path AS dup_path, p2.path AS kept_path
           FROM duplicates d
           JOIN photos p1 ON p1.id = d.photo_id
           JOIN photos p2 ON p2.id = d.dup_of
           ORDER BY d.kind, d.distance"""
    ).fetchall()
