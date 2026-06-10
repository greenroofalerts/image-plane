"""Captioning stage: run a local Ollama vision model over uncaptioned rows.

Resumable by construction — only rows WHERE caption IS NULL are
processed, and each result commits immediately, so a killed run loses
at most the in-flight image.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path

from . import db as dbmod
from . import ollama_client as oc

log = logging.getLogger("image_plane.caption")


def ensure_vision_model(auto_pull: bool = False) -> str | None:
    """Return the name of a usable local vision model, pulling if allowed.

    Returns None (with a clear log line, never a crash) when the Ollama
    server is down or no model is available and pulling is off.
    """
    if not oc.server_up():
        log.error(
            "Ollama server is not reachable at 127.0.0.1:11434. "
            "Start it with: ollama serve (or open the Ollama app), then re-run."
        )
        return None
    model = oc.pick_vision_model(oc.installed_models())
    if model:
        log.info("using installed vision model: %s", model)
        return model
    log.info(
        "no vision-capable model installed. Recommended: %s (~%.1f GB download).",
        oc.RECOMMENDED_MODEL, oc.RECOMMENDED_SIZE_GB,
    )
    if not auto_pull:
        log.info("re-run with --pull to download it.")
        return None
    log.info("pulling %s ...", oc.RECOMMENDED_MODEL)
    oc.pull(oc.RECOMMENDED_MODEL)
    return oc.RECOMMENDED_MODEL


def caption_pending(
    conn: sqlite3.Connection,
    model: str,
    limit: int | None = None,
    progress_every: int = 10,
) -> dict:
    """Caption all rows lacking a caption. Returns counts + timing stats."""
    q = "SELECT id, path FROM photos WHERE caption IS NULL ORDER BY id"
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = conn.execute(q).fetchall()
    if not rows:
        log.info("nothing to caption — all rows already done")
        return {"captioned": 0, "errors": 0, "seconds_per_image": None}

    done = errors = 0
    times: list[float] = []
    for i, row in enumerate(rows, 1):
        path = Path(row["path"])
        if not path.exists():
            log.warning("file moved or deleted, skipping: %s", path)
            errors += 1
            continue
        t0 = time.monotonic()
        try:
            result = oc.caption_image(model, path)
        except Exception as e:
            log.warning("caption failed for %s: %s", path.name, e)
            errors += 1
            continue
        elapsed = time.monotonic() - t0
        times.append(elapsed)
        conn.execute(
            "UPDATE photos SET caption=?, tags=?, caption_model=?, captioned_at=? WHERE id=?",
            (result["caption"], json.dumps(result["tags"]), model, dbmod.utcnow(), row["id"]),
        )
        conn.commit()
        done += 1
        if i % progress_every == 0 or i == len(rows):
            avg = sum(times) / len(times)
            log.info("progress: %d/%d captioned, avg %.1fs/image", i, len(rows), avg)

    stats = {
        "captioned": done,
        "errors": errors,
        "seconds_per_image": round(sum(times) / len(times), 2) if times else None,
        "min_s": round(min(times), 2) if times else None,
        "max_s": round(max(times), 2) if times else None,
    }
    log.info("caption run done: %s", stats)
    return stats
