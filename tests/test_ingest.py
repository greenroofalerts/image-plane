from datetime import datetime, timezone
from pathlib import Path

from image_plane import ingest


def test_ingest_takeout_folder(conn, fixtures):
    counts = ingest.ingest_folder(conn, fixtures / "takeout")
    assert counts["new"] == 8
    assert counts["error"] == 0

    rows = conn.execute("SELECT * FROM photos ORDER BY path").fetchall()
    assert len(rows) == 8
    assert all(r["source"] == "takeout" for r in rows)
    assert all(r["file_hash"] and len(r["file_hash"]) == 64 for r in rows)
    assert all(r["phash"] and len(r["phash"]) == 16 for r in rows)
    assert all(r["width"] == 640 and r["height"] == 480 for r in rows)

    # sidecar timestamp mapped to ISO8601 UTC
    first = conn.execute("SELECT * FROM photos WHERE path LIKE '%scene_00%'").fetchone()
    assert first["taken_at"] == datetime.fromtimestamp(
        1700000000, tz=timezone.utc).isoformat(timespec="seconds")
    # even scenes have GPS, odd scenes have 0.0/0.0 which must be treated as absent
    assert abs(first["gps_lat"] - 51.5) < 1e-6
    second = conn.execute("SELECT * FROM photos WHERE path LIKE '%scene_01%'").fetchone()
    assert second["gps_lat"] is None and second["gps_lon"] is None


def test_ingest_icloud_exif(conn, fixtures):
    counts = ingest.ingest_folder(conn, fixtures / "icloud")
    assert counts["new"] == 4
    rows = conn.execute("SELECT * FROM photos").fetchall()
    assert all(r["source"] == "icloud" for r in rows)
    assert all(r["taken_at"] and r["taken_at"].startswith("2024-03-") for r in rows)


def test_ingest_is_resumable(conn, fixtures):
    ingest.ingest_folder(conn, fixtures / "takeout")
    counts = ingest.ingest_folder(conn, fixtures / "takeout")
    assert counts == {"new": 0, "updated": 0, "skipped": 8, "error": 0}


def test_ingest_detects_changed_file(conn, fixtures, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    src = fixtures / "takeout" / "scene_00.jpg"
    dst = work / "photo.jpg"
    dst.write_bytes(src.read_bytes())
    ingest.ingest_folder(conn, work, source="icloud")
    # replace content under the same path
    dst.write_bytes((fixtures / "takeout" / "scene_01.jpg").read_bytes())
    counts = ingest.ingest_folder(conn, work, source="icloud")
    assert counts["updated"] == 1


def test_ingest_empty_folder(conn, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    counts = ingest.ingest_folder(conn, empty)
    assert counts == {"new": 0, "updated": 0, "skipped": 0, "error": 0}


def test_corrupt_image_is_error_not_crash(conn, tmp_path):
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "notanimage.jpg").write_bytes(b"this is not a jpeg")
    counts = ingest.ingest_folder(conn, bad, source="icloud")
    assert counts["error"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM photos").fetchone()["c"] == 0


def test_corrupt_sidecar_tolerated(conn, tmp_path, fixtures):
    work = tmp_path / "work"
    work.mkdir()
    img = work / "x.jpg"
    img.write_bytes((fixtures / "takeout" / "scene_02.jpg").read_bytes())
    img.with_name("x.jpg.json").write_text("{not valid json")
    counts = ingest.ingest_folder(conn, work)
    assert counts["new"] == 1  # image still ingested, sidecar ignored


def test_gps_dms_conversion():
    assert abs(ingest._gps_to_decimal((51.0, 30.0, 0.0), "N") - 51.5) < 1e-9
    assert ingest._gps_to_decimal((0.0, 7.0, 12.0), "W") < 0
    assert ingest._gps_to_decimal(None, "N") is None
    assert ingest._gps_to_decimal(("a", "b", "c"), "N") is None


def test_source_autodetect(fixtures):
    assert ingest.detect_source(fixtures / "takeout") == "takeout"
    assert ingest.detect_source(fixtures / "icloud") == "icloud"
