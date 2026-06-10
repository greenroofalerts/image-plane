"""Ingest: walk a folder of images, normalise metadata, write rows.

Supports two source layouts:

- Google Takeout: images accompanied by JSON sidecars, either
  ``IMG_001.jpg.json`` or the newer
  ``IMG_001.jpg.supplemental-metadata.json``. Sidecar wins for
  taken-time and GPS (Takeout strips GPS from EXIF on some exports).
- iCloud / plain folder export: no sidecars; metadata comes from EXIF
  (DateTimeOriginal / DateTime, GPSInfo IFD).

Resumable: a file whose path is already in the DB with the same
content hash is skipped. Changed content under the same path is
re-ingested (row updated, caption cleared).
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
from PIL.ExifTags import IFD

from . import db as dbmod
from .phash import dhash_hex

log = logging.getLogger("image_plane.ingest")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".tiff", ".tif", ".bmp", ".webp", ".heic"}

try:  # HEIC support is optional; degrade to skipping HEIC if absent
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIC_OK = True
except ImportError:
    HEIC_OK = False

# EXIF tag ids
TAG_DATETIME = 0x0132            # IFD0 DateTime
TAG_DATETIME_ORIGINAL = 0x9003   # Exif IFD DateTimeOriginal


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_sidecar(path: Path) -> Path | None:
    """Locate a Google Takeout JSON sidecar for an image, if present."""
    candidates = [
        path.with_name(path.name + ".json"),
        path.with_name(path.name + ".supplemental-metadata.json"),
        # Takeout truncates long names; cover the common short form too
        path.with_name(path.name + ".suppl.json"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def parse_sidecar(sidecar: Path) -> dict:
    """Extract taken_at / GPS from a Takeout sidecar. Tolerant of junk."""
    out: dict = {}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.warning("unreadable sidecar %s: %s", sidecar.name, e)
        return out
    ts = (data.get("photoTakenTime") or {}).get("timestamp")
    if ts is not None:
        try:
            out["taken_at"] = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat(
                timespec="seconds"
            )
        except (ValueError, OverflowError, OSError):
            log.warning("bad timestamp %r in %s", ts, sidecar.name)
    geo = data.get("geoData") or {}
    lat, lon = geo.get("latitude"), geo.get("longitude")
    # Takeout writes 0.0/0.0 when there is no GPS — treat as absent
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and (lat, lon) != (0.0, 0.0):
        out["gps_lat"], out["gps_lon"] = float(lat), float(lon)
    return out


def _gps_to_decimal(dms, ref) -> float | None:
    """Convert EXIF GPS ((d, m, s), 'N'/'S'/'E'/'W') to signed decimal degrees."""
    try:
        d, m, s = (float(x) for x in dms)
        dec = d + m / 60.0 + s / 3600.0
        if ref in ("S", "W"):
            dec = -dec
        return dec
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def parse_exif(img: Image.Image) -> dict:
    """Extract taken_at / GPS from embedded EXIF. Returns {} when absent."""
    out: dict = {}
    try:
        exif = img.getexif()
    except Exception:  # corrupt EXIF blocks raise all sorts; never fatal
        return out
    if not exif:
        return out

    dt = None
    try:
        dt = exif.get_ifd(IFD.Exif).get(TAG_DATETIME_ORIGINAL)
    except Exception:
        pass
    dt = dt or exif.get(TAG_DATETIME)
    if isinstance(dt, str):
        try:
            out["taken_at"] = (
                datetime.strptime(dt.strip(), "%Y:%m:%d %H:%M:%S")
                .replace(tzinfo=timezone.utc)
                .isoformat(timespec="seconds")
            )
        except ValueError:
            log.debug("unparseable EXIF datetime %r", dt)

    try:
        gps = exif.get_ifd(IFD.GPSInfo)
    except Exception:
        gps = {}
    if gps:
        lat = _gps_to_decimal(gps.get(2), gps.get(1))   # GPSLatitude, GPSLatitudeRef
        lon = _gps_to_decimal(gps.get(4), gps.get(3))   # GPSLongitude, GPSLongitudeRef
        if lat is not None and lon is not None:
            out["gps_lat"], out["gps_lon"] = lat, lon
    return out


def ingest_file(conn: sqlite3.Connection, path: Path, source: str) -> str:
    """Ingest one image. Returns 'new', 'updated', 'skipped' or 'error'."""
    file_hash = sha256_file(path)
    row = conn.execute("SELECT id, file_hash FROM photos WHERE path = ?", (str(path),)).fetchone()
    if row and row["file_hash"] == file_hash:
        return "skipped"

    try:
        with Image.open(path) as img:
            width, height = img.size
            meta = parse_exif(img)
            phash = dhash_hex(img)
    except Exception as e:
        log.warning("cannot read %s: %s", path.name, e)
        return "error"

    sidecar = find_sidecar(path)
    if sidecar:
        meta.update(parse_sidecar(sidecar))  # sidecar wins over EXIF

    values = dict(
        path=str(path),
        file_hash=file_hash,
        phash=phash,
        source=source,
        taken_at=meta.get("taken_at"),
        gps_lat=meta.get("gps_lat"),
        gps_lon=meta.get("gps_lon"),
        width=width,
        height=height,
        bytes=path.stat().st_size,
        ingested_at=dbmod.utcnow(),
    )
    if row:
        conn.execute(
            """UPDATE photos SET file_hash=:file_hash, phash=:phash, source=:source,
               taken_at=:taken_at, gps_lat=:gps_lat, gps_lon=:gps_lon,
               width=:width, height=:height, bytes=:bytes,
               caption=NULL, tags=NULL, caption_model=NULL, captioned_at=NULL,
               ingested_at=:ingested_at WHERE path=:path""",
            values,
        )
        return "updated"
    conn.execute(
        """INSERT INTO photos (path, file_hash, phash, source, taken_at, gps_lat, gps_lon,
           width, height, bytes, ingested_at)
           VALUES (:path, :file_hash, :phash, :source, :taken_at, :gps_lat, :gps_lon,
           :width, :height, :bytes, :ingested_at)""",
        values,
    )
    return "new"


def detect_source(folder: Path) -> str:
    """Takeout folders carry JSON sidecars; everything else is a plain export."""
    for p in folder.rglob("*.json"):
        if p.name.lower() != "metadata.json":
            return "takeout"
    return "icloud"


def ingest_folder(
    conn: sqlite3.Connection, folder: Path, source: str = "auto", progress_every: int = 100
) -> dict:
    folder = folder.expanduser().resolve()
    if not folder.is_dir():
        raise NotADirectoryError(folder)
    if source == "auto":
        source = detect_source(folder)
        log.info("source auto-detected as %r", source)

    counts = {"new": 0, "updated": 0, "skipped": 0, "error": 0}
    files = sorted(p for p in folder.rglob("*") if p.suffix.lower() in IMAGE_EXTS and p.is_file())
    if not files:
        log.info("no images found under %s — nothing to do", folder)
        return counts
    skipping_heic = sum(1 for p in files if p.suffix.lower() == ".heic") if not HEIC_OK else 0
    if skipping_heic:
        log.warning("pillow-heif not installed: %d HEIC files will error", skipping_heic)

    for i, path in enumerate(files, 1):
        counts[ingest_file(conn, path, source)] += 1
        if i % progress_every == 0:
            conn.commit()
            log.info("progress: %d/%d (%s)", i, len(files), counts)
    conn.commit()
    log.info("done: %d files — %s", len(files), counts)
    return counts
