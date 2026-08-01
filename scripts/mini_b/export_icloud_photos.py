#!/usr/bin/env python3
"""Export iCloud Photos items into checked local folders.

The export step does not read picture content. It records file names, sizes,
and SHA-256 values only.

The mirror step reads picture content for ONE purpose: to work out whether an
arriving picture is one Lee has already ruled out. It never reads picture
meaning. See "the second lane" below.
"""

from __future__ import annotations

import argparse
import contextlib
import errno
import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

IMAGE_EXTENSIONS = {".avif", ".dng", ".gif", ".heic", ".heif", ".jpeg", ".jpg", ".png", ".raw", ".tif", ".tiff", ".webp"}
VIDEO_EXTENSIONS = {".3gp", ".avi", ".m4v", ".mov", ".mp4", ".mpeg", ".mpg", ".mts", ".wmv"}

DEFAULT_ROOT = Path.home() / "icloud-originals" / "photos"
DEFAULT_DB = Path.home() / "Pictures" / "Photos Library.photoslibrary" / "database" / "Photos.sqlite"

ExportCallback = Callable[[str, Path], None]


def now_utc() -> str:
    """Return the current time in UTC."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_item_id(item_id: str) -> str:
    """Return a folder name that cannot contain path control characters."""
    return hashlib.sha256(item_id.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the SHA-256 value for one file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_role(path: Path) -> str:
    """Return the member role from its file extension."""
    extension = path.suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        return "photo"
    if extension in VIDEO_EXTENSIONS:
        return "live_photo_motion"
    return "sidecar"


def members_for(folder: Path) -> list[dict[str, Any]]:
    """Return checked member records for a folder."""
    members: list[dict[str, Any]] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size <= 0:
            raise ValueError(f"Empty file: {path.name}")
        members.append(
            {
                "relative_path": path.relative_to(folder).as_posix(),
                "role": file_role(path),
                "bytes": size,
                "sha256": sha256_file(path),
            }
        )
    if not members:
        raise ValueError("Export produced no files")
    return members


def validate_members(
    folder: Path,
    members: list[dict[str, Any]],
    ignore: set[str] | None = None,
) -> tuple[bool, str | None]:
    """Check that a folder still matches every recorded member.

    The ignore set names generated files this code wrote itself, such as the
    identity sidecar. It is used only when checking a copy this code made,
    never when checking what came off the Photos library.
    """
    if not members:
        return False, "Receipt has no members"
    recorded = {member.get("relative_path"): member for member in members}
    if None in recorded or len(recorded) != len(members):
        return False, "Receipt has repeated or invalid member paths"
    skip = ignore or set()
    found = {
        path.relative_to(folder).as_posix(): path
        for path in folder.rglob("*")
        if path.is_file() and path.relative_to(folder).as_posix() not in skip
    }
    if set(found) != set(recorded):
        return False, "Folder members do not match the receipt"
    for relative_path, path in found.items():
        member = recorded[relative_path]
        if path.stat().st_size != member.get("bytes"):
            return False, f"Byte count changed: {relative_path}"
        if sha256_file(path) != member.get("sha256"):
            return False, f"Hash changed: {relative_path}"
    return True, None


def eligible_items(database: Path, one: str | None = None, limit: int | None = None) -> list[str]:
    """Read stable IDs for visible, non-deleted photo assets."""
    query = """
        SELECT ZUUID
        FROM ZASSET
        WHERE ZKIND = 0
          AND COALESCE(ZTRASHEDSTATE, 0) = 0
          AND COALESCE(ZHIDDEN, 0) = 0
    """
    values: list[Any] = []
    if one:
        query += " AND ZUUID = ?"
        values.append(one)
    query += " ORDER BY ZUUID"
    if limit is not None:
        query += " LIMIT ?"
        values.append(limit)
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        return [row[0] for row in connection.execute(query, values)]


def item_identities(database: Path, item_ids: set[str]) -> dict[str, dict[str, Any]]:
    """Read the second identity for each item: capture date and original name.

    The folder name in the reader is an opaque hash. Without this, the only
    identity lives in the Mini B receipt, where the reader cannot see it.

    An older or newer Photos library may not carry these columns. When the
    read fails, the export still runs and the identity is simply absent.
    """
    query = """
        SELECT a.ZUUID,
               datetime(a.ZDATECREATED + 978307200, 'unixepoch'),
               COALESCE(b.ZORIGINALFILENAME, a.ZFILENAME)
        FROM ZASSET a
        LEFT JOIN ZADDITIONALASSETATTRIBUTES b ON b.ZASSET = a.Z_PK
    """
    identities: dict[str, dict[str, Any]] = {}
    try:
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
            rows = connection.execute(query).fetchall()
    except sqlite3.Error:
        return identities
    for item_id, capture_date, original_filename in rows:
        if item_id in item_ids:
            identities[item_id] = {
                "capture_date": capture_date,
                "original_filename": original_filename,
            }
    return identities


def _is_torn_final_line(raw: bytes) -> bool:
    """Return true only for a malformed final line without a new line."""
    if not raw or raw.endswith(b"\n"):
        return False
    final_line = raw.rsplit(b"\n", 1)[-1]
    if not final_line.strip():
        return False
    try:
        json.loads(final_line)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return True
    return False


def latest_records(manifest: Path) -> dict[str, dict[str, Any]]:
    """Return the final receipt record for every item."""
    records: dict[str, dict[str, Any]] = {}
    if not manifest.exists():
        return records
    raw = manifest.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    torn_final = _is_torn_final_line(raw)
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            if torn_final and line_number == len(lines):
                break
            raise ValueError(f"Invalid receipt line {line_number}") from error
        item_id = record.get("item_id")
        if not isinstance(item_id, str):
            raise ValueError(f"Receipt line {line_number} has no item ID")
        records[item_id] = record
    return records


def archive_torn_manifest(manifest: Path) -> None:
    """Archive a torn receipt, then rebuild it from complete receipt lines."""
    raw = manifest.read_bytes()
    if not _is_torn_final_line(raw):
        return
    final_line = raw.rsplit(b"\n", 1)[-1]
    complete_prefix = raw[: len(raw) - len(final_line)]
    archive_root = manifest.parent / "quarantine"
    archive_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = archive_root / f"{manifest.name}-{stamp}-torn"
    sequence = 1
    while archive.exists():
        archive = archive_root / f"{manifest.name}-{stamp}-torn-{sequence}"
        sequence += 1
    os.replace(manifest, archive)
    temporary = manifest.with_name(f".{manifest.name}.{stamp}.rebuild")
    with temporary.open("wb") as handle:
        handle.write(complete_prefix)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, manifest)


def append_record(manifest: Path, record: dict[str, Any]) -> None:
    """Append and save one receipt record."""
    manifest.parent.mkdir(parents=True, exist_ok=True)
    if manifest.exists():
        archive_torn_manifest(manifest)
    with manifest.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def move_to_quarantine(folder: Path, quarantine: Path, reason: str) -> Path | None:
    """Move an existing folder to a new quarantine folder."""
    if not folder.exists():
        return None
    quarantine.mkdir(parents=True, exist_ok=True)
    target = quarantine / f"{folder.name}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{reason}"
    suffix = 1
    while target.exists():
        target = quarantine / f"{folder.name}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{reason}-{suffix}"
        suffix += 1
    os.replace(folder, target)
    return target


@contextlib.contextmanager
def directory_lock(lock: Path) -> Iterator[None]:
    """Hold an operating-system file lock for one export run."""
    lock.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EAGAIN):
                raise RuntimeError(f"Another export holds lock: {lock}") from error
            raise
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def applescript_export(item_id: str, staging: Path, timeout: int = 120) -> None:
    """Ask Photos to export originals for one stable item ID."""
    photo_id = f"{item_id}/L0/001"
    script = f'''tell application "Photos"
    set targetItem to media item id {json.dumps(photo_id)}
    export {{targetItem}} to POSIX file {json.dumps(str(staging))} with using originals
end tell'''
    subprocess.run(["osascript", "-e", script], check=True, timeout=timeout, capture_output=True, text=True)


def export_items(
    database: Path,
    root: Path,
    one: str | None = None,
    limit: int | None = None,
    exporter: ExportCallback = applescript_export,
) -> dict[str, int]:
    """Export eligible items and append a receipt for each result."""
    paths = {
        "staging": root / ".staging",
        "assets": root / "assets",
        "quarantine": root / "quarantine",
        "manifest": root / "manifest.jsonl",
        "lock": root / ".lock",
    }
    for key in ("staging", "assets", "quarantine"):
        paths[key].mkdir(parents=True, exist_ok=True)
    items = eligible_items(database, one=one, limit=limit)
    identities = item_identities(database, set(items))
    latest = latest_records(paths["manifest"])
    result = {"eligible": len(items), "checked": 0, "skipped": 0, "failed": 0}

    with directory_lock(paths["lock"]):
        for item_id in items:
            safe_id = safe_item_id(item_id)
            asset_folder = paths["assets"] / safe_id
            previous = latest.get(item_id)
            attempt = int(previous.get("attempt", 0)) + 1 if previous else 1
            if previous and previous.get("state") == "checked":
                valid, _ = validate_members(asset_folder, previous.get("members", []))
                if valid:
                    result["skipped"] += 1
                    continue
                move_to_quarantine(asset_folder, paths["quarantine"], "hash-conflict")
            elif asset_folder.exists():
                move_to_quarantine(asset_folder, paths["quarantine"], "conflict")

            staging_folder = paths["staging"] / safe_id
            if staging_folder.exists():
                move_to_quarantine(staging_folder, paths["quarantine"], "incomplete")
            staging_folder.mkdir(parents=True, exist_ok=False)
            started_at = now_utc()
            record: dict[str, Any] = {
                "item_id": item_id,
                "safe_id": safe_id,
                "attempt": attempt,
                "started_at": started_at,
                "finished_at": now_utc(),
                "state": "failed",
                "error": None,
                "members": [],
                "capture_date": identities.get(item_id, {}).get("capture_date"),
                "original_filename": identities.get(item_id, {}).get("original_filename"),
            }
            try:
                exporter(item_id, staging_folder)
                record["members"] = members_for(staging_folder)
                os.replace(staging_folder, asset_folder)
                record["state"] = "checked"
                result["checked"] += 1
            except Exception as error:  # One asset must not stop later assets.
                record["error"] = str(error)
                result["failed"] += 1
            record["finished_at"] = now_utc()
            append_record(paths["manifest"], record)
            latest[item_id] = record
    return result


def excluded_hashes(path: Path) -> set[str]:
    """Read SHA-256 values from the recorded exclusion list."""
    values: set[str] = set()
    if not path.exists():
        return values
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            data = json.loads(line)
            for key in ("sha256", "sha", "file_sha256"):
                value = data.get(key)
                if isinstance(value, str) and len(value) == 64:
                    values.add(value)
    return values


# --- the second lane: the picture hash ------------------------------------
#
# Why this exists. The file fingerprint (SHA-256) catches a picture only when
# the bytes are identical. A picture that came in through Google Takeout was
# re-encoded, so its bytes differ from the copy iCloud holds. Measured 1 Aug
# 2026: at least 1,189 pictures Lee had already ruled out would have walked
# back in through that hole (window finding ref 59).
#
# The method is the recorded one, not a new one. It is the dHash used by
# src/image_plane/phash.py and by dedupe_global_v2.py line 50: make a small
# JPEG copy, turn it grey, shrink it to 9 by 8, then compare each pixel with
# the one to its right. The recorded distance limit is 8 (dedup.py line 27).
#
# It is copied into this file rather than imported because Mini A holds no
# copy of this repository. tests/test_icloud_intake.py checks this copy still
# agrees with src/image_plane/phash.py, so the two can never drift apart.
#
# Two things are always required before a picture is held back, never one
# (the riding law: never a single field):
#   1. the picture hash is within the limit, allowing for rotation, AND
#   2. the file name or the byte size agrees.
# Requiring the second field is also what makes this fast: only excluded
# pictures sharing a name or a size are ever compared.

PICTURE_HASH_LIMIT = 8
PICTURE_THUMBNAIL_EDGE = 480


def _dhash_hex(image: Any) -> str:
    """64-bit dHash as 16 hex characters. Same method as src/image_plane/phash.py."""
    grey = image.convert("L").resize((9, 8), _lanczos())
    px = grey.tobytes()  # L mode: one byte per pixel, row-major
    bits = 0
    for row in range(8):
        for col in range(8):
            left = px[row * 9 + col]
            right = px[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}"


def _lanczos():
    from PIL import Image as _Image

    return getattr(_Image, "Resampling", _Image).LANCZOS


def hamming_hex(hex_a: str, hex_b: str) -> int:
    """Count the differing bits. Written to run on Python 3.9 on Mini A."""
    return bin(int(hex_a, 16) ^ int(hex_b, 16)).count("1")


def picture_hashes(path: Path, rotations: bool = True) -> list[str]:
    """Picture hashes for one file, or an empty list when it cannot be read.

    A small JPEG copy is made with sips first, because Pillow on Mini A cannot
    open HEIC and every iCloud original is HEIC. This is the recorded route.

    With rotations, the upright hash comes first and the three turned copies
    follow. Two copies of one picture stored at different rotations produce
    completely different hashes, so the turned copies are what make the lane
    work: measured 1 Aug 2026, a plain compare caught 0 of 40 rotated pairs
    and a rotation-aware compare caught 40 of 40 (window finding ref 60).
    """
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        return []
    try:
        from PIL import Image
    except Exception:
        return []
    with contextlib.ExitStack() as stack:
        workdir = stack.enter_context(_temporary_directory())
        thumbnail = Path(workdir) / "thumb.jpg"
        try:
            subprocess.run(
                ["sips", "-s", "format", "jpeg", "-Z", str(PICTURE_THUMBNAIL_EDGE),
                 str(path), "--out", str(thumbnail)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120, check=False,
            )
        except Exception:
            return []
        if not thumbnail.exists() or thumbnail.stat().st_size == 0:
            return []
        try:
            with Image.open(thumbnail) as image:
                image.load()
                values = [_dhash_hex(image)]
                if rotations:
                    values += [_dhash_hex(image.rotate(angle, expand=True)) for angle in (90, 180, 270)]
                return values
        except Exception:
            return []


def _temporary_directory():
    import tempfile

    return tempfile.TemporaryDirectory()


def excluded_pictures(path: Path | None) -> dict[str, dict[Any, list[dict[str, Any]]]]:
    """Read the recorded excluded picture hashes, indexed by name and by size.

    The file is built by scripts/mini_a/build_excluded_picture_hashes.py. It
    sits beside the exclusion list and never replaces it.
    """
    by_name: dict[Any, list[dict[str, Any]]] = {}
    by_size: dict[Any, list[dict[str, Any]]] = {}
    index = {"by_name": by_name, "by_size": by_size}
    if path is None or not path.exists():
        return index
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            values = data.get("phash") or []
            if not isinstance(values, list) or not values:
                continue
            row = {"phash": values, "name": data.get("name"), "size": data.get("size")}
            name = row["name"]
            if isinstance(name, str) and name:
                by_name.setdefault(name.lower(), []).append(row)
            size = row["size"]
            if isinstance(size, int):
                by_size.setdefault(size, []).append(row)
    return index


def picture_is_excluded(
    folder: Path,
    members: list[dict[str, Any]],
    index: dict[str, dict[Any, list[dict[str, Any]]]],
    limit: int = PICTURE_HASH_LIMIT,
) -> bool:
    """True when an arriving picture is one already ruled out, re-encoded."""
    if not index["by_name"] and not index["by_size"]:
        return False
    for member in members:
        if member.get("role") != "photo":
            continue
        relative_path = member.get("relative_path")
        if not isinstance(relative_path, str):
            continue
        path = folder / relative_path
        name = Path(relative_path).name
        candidates = list(index["by_name"].get(name.lower(), []))
        candidates += index["by_size"].get(member.get("bytes"), [])
        if not candidates:
            continue
        values = picture_hashes(path, rotations=False)
        if not values:
            continue
        incoming = values[0]
        for candidate in candidates:
            for recorded in candidate["phash"]:
                if hamming_hex(incoming, recorded) <= limit:
                    return True
    return False


IDENTITY_SIDECAR = "identity.json"


def write_identity_sidecar(folder: Path, item_id: str, record: dict[str, Any]) -> None:
    """Write the second identity into the folder the reader opens.

    The folder name is an opaque hash, so without this the reader cannot say
    which photo it is holding. The sidecar carries the Photos item ID, the
    original file name and the capture date.
    """
    sidecar = {
        "item_id": item_id,
        "safe_id": record.get("safe_id"),
        "original_filename": record.get("original_filename"),
        "capture_date": record.get("capture_date"),
        "members": [
            {"relative_path": member.get("relative_path"), "role": member.get("role"), "sha256": member.get("sha256")}
            for member in record.get("members", [])
        ],
        "written_at": now_utc(),
    }
    path = folder / IDENTITY_SIDECAR
    path.write_text(json.dumps(sidecar, sort_keys=True) + "\n", encoding="utf-8")


def copy_folder(source: Path, destination: Path) -> None:
    """Copy one item folder without changing the source."""
    shutil.copytree(source, destination, copy_function=shutil.copy2)


def archive_generated_folder(folder: Path, quarantine: Path, reason: str) -> Path | None:
    """Archive one generated mirror folder before replacing it."""
    return move_to_quarantine(folder, quarantine, reason)


def archive_complete_marker(destination_root: Path, quarantine: Path) -> Path | None:
    """Archive a current completion marker before an unresolved result."""
    marker = destination_root / "COMPLETE"
    if not marker.exists():
        return None
    quarantine.mkdir(parents=True, exist_ok=True)
    target = quarantine / f"COMPLETE-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-stale"
    suffix = 1
    while target.exists():
        target = quarantine / f"COMPLETE-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-stale-{suffix}"
        suffix += 1
    os.replace(marker, target)
    return target


def mirror_receipt(
    source_root: Path,
    destination_root: Path,
    exclusion_file: Path | None = None,
    expected_item_ids: set[str] | None = None,
    check_only: bool = False,
    write_complete: bool = False,
    picture_hash_file: Path | None = None,
) -> dict[str, int]:
    """Validate and place receipt items in accepted or suppressed folders.

    A photo is held back when EITHER lane says it is one Lee has already
    ruled out: lane 1 is the file fingerprint, lane 2 is the picture hash.
    The two lanes are counted separately.
    """
    manifest = source_root / "manifest.jsonl"
    records = latest_records(manifest)
    excluded = excluded_hashes(exclusion_file) if exclusion_file else set()
    picture_index = excluded_pictures(picture_hash_file)
    accepted = destination_root / "accepted"
    suppressed = destination_root / "suppressed"
    quarantine = destination_root / "quarantine"
    staging = destination_root / ".mirror-staging"
    for path in (accepted, suppressed, quarantine, staging):
        path.mkdir(parents=True, exist_ok=True)
    if expected_item_ids is None:
        expected_item_ids = set(records)
    missing_expected = expected_item_ids - set(records)
    ineligible_record_ids = set(records) - expected_item_ids
    result = {
        "items": len(expected_item_ids),
        "accepted": 0,
        "suppressed": 0,
        "quarantined": 0,
        "skipped": 0,
        "unresolved": len(missing_expected),
        "ineligible": 0,
        "suppressed_file_hash": 0,
        "suppressed_picture_hash": 0,
    }

    for item_id in ineligible_record_ids:
        safe_id = records[item_id].get("safe_id") or safe_item_id(item_id)
        for current in (accepted / safe_id, suppressed / safe_id):
            if current.exists() and not check_only:
                archive_generated_folder(current, quarantine, "ineligible")
                result["ineligible"] += 1

    for item_id in expected_item_ids:
        record = records.get(item_id)
        if record is None:
            continue
        safe_id = record.get("safe_id") or safe_item_id(item_id)
        members = record.get("members", [])
        source_folder = source_root / "assets" / safe_id
        if record.get("state") != "checked":
            result["unresolved"] += 1
            continue
        valid, _ = validate_members(source_folder, members)
        if not valid:
            result["unresolved"] += 1
            result["quarantined"] += 1
            if source_folder.exists() and not check_only:
                target = quarantine / safe_id
                if target.exists():
                    move_to_quarantine(target, quarantine, "conflict")
                copy_folder(source_folder, target)
            continue
        if any(member.get("relative_path") == IDENTITY_SIDECAR for member in members):
            # A real exported file of this name would be mixed up with the
            # sidecar this code writes. Hold the item instead of guessing.
            result["unresolved"] += 1
            result["quarantined"] += 1
            if source_folder.exists() and not check_only:
                conflict = quarantine / safe_id
                if conflict.exists():
                    move_to_quarantine(conflict, quarantine, "conflict")
                copy_folder(source_folder, conflict)
            continue
        by_file_hash = any(member["sha256"] in excluded for member in members)
        by_picture_hash = False
        if not by_file_hash:
            by_picture_hash = picture_is_excluded(source_folder, members, picture_index)
        target_root = suppressed if (by_file_hash or by_picture_hash) else accepted
        other_root = accepted if target_root == suppressed else suppressed

        def count_suppressed() -> None:
            """Record one held-back photo under the lane that caught it."""
            result["suppressed"] += 1
            if by_file_hash:
                result["suppressed_file_hash"] += 1
            else:
                result["suppressed_picture_hash"] += 1

        target = target_root / safe_id
        other_target = other_root / safe_id
        if other_target.exists() and not check_only:
            archive_generated_folder(other_target, quarantine, "route-changed")
        if target.exists():
            matches, _ = validate_members(target, members, ignore={IDENTITY_SIDECAR})
            if matches:
                result["skipped"] += 1
                continue
            result["quarantined"] += 1
            if not check_only:
                move_to_quarantine(target, quarantine, "conflict")
        if check_only:
            if target_root == suppressed:
                count_suppressed()
            else:
                result["accepted"] += 1
            continue
        stage = staging / safe_id
        if stage.exists():
            move_to_quarantine(stage, quarantine, "stale")
        copy_folder(source_folder, stage)
        copied, _ = validate_members(stage, members)
        if not copied:
            move_to_quarantine(stage, quarantine, "invalid")
            result["quarantined"] += 1
            result["unresolved"] += 1
            continue
        write_identity_sidecar(stage, item_id, record)
        os.replace(stage, target)
        if target_root == suppressed:
            count_suppressed()
        else:
            result["accepted"] += 1

    if not check_only:
        if result["unresolved"]:
            archive_complete_marker(destination_root, quarantine)
        summary = destination_root / f"summary-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        summary.write_text(json.dumps({"created_at": now_utc(), **result}, sort_keys=True) + "\n", encoding="utf-8")
        complete = destination_root / "COMPLETE"
        if write_complete and result["unresolved"] == 0:
            complete.write_text(now_utc() + "\n", encoding="utf-8")
    return result


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser."""
    parser = argparse.ArgumentParser(description="Export checked iCloud photo originals.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    export = subparsers.add_parser("export")
    export.add_argument("--database", type=Path, default=DEFAULT_DB)
    export.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    export.add_argument("--one")
    export.add_argument("--limit", type=int)
    mirror = subparsers.add_parser("mirror")
    mirror.add_argument("--source-root", type=Path, required=True)
    mirror.add_argument("--destination-root", type=Path, required=True)
    mirror.add_argument("--exclusion-file", type=Path)
    mirror.add_argument("--picture-hash-file", type=Path)
    mirror.add_argument("--expected-items-file", type=Path)
    mirror.add_argument("--check-only", action="store_true")
    mirror.add_argument("--write-complete", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one safe export or mirror action."""
    args = build_parser().parse_args(argv)
    if args.command == "export":
        result = export_items(args.database, args.root, one=args.one, limit=args.limit)
        print(json.dumps(result, sort_keys=True))
        print(f"Counted by: SELECT ZUUID FROM ZASSET in {args.database}")
    else:
        expected_item_ids = None
        if args.expected_items_file:
            expected_item_ids = {
                line.strip() for line in args.expected_items_file.read_text(encoding="utf-8").splitlines() if line.strip()
            }
        result = mirror_receipt(
            args.source_root,
            args.destination_root,
            exclusion_file=args.exclusion_file,
            expected_item_ids=expected_item_ids,
            check_only=args.check_only,
            write_complete=args.write_complete,
            picture_hash_file=args.picture_hash_file,
        )
        print(json.dumps(result, sort_keys=True))
        print(f"Counted by: latest receipt records in {args.source_root / 'manifest.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
