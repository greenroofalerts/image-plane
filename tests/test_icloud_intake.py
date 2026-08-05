import fcntl
import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mini_b" / "export_icloud_photos.py"
SPEC = importlib.util.spec_from_file_location("icloud_intake", MODULE_PATH)
assert SPEC and SPEC.loader
intake = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(intake)


def make_database(path, rows):
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE ZASSET (ZUUID TEXT, ZKIND INTEGER, ZTRASHEDSTATE INTEGER, ZHIDDEN INTEGER)"
        )
        connection.executemany("INSERT INTO ZASSET VALUES (?, ?, ?, ?)", rows)


def write_export(item_id, folder):
    (folder / "photo.jpg").write_bytes(f"image-{item_id}".encode())
    if item_id == "live":
        (folder / "motion.mov").write_bytes(b"motion")


def test_hidden_and_deleted_items_stay_out(tmp_path):
    database = tmp_path / "Photos.sqlite"
    make_database(database, [("keep", 0, 0, 0), ("hidden", 0, 0, 1), ("deleted", 0, 1, 0), ("not-photo", 1, 0, 0)])
    assert intake.eligible_items(database) == ["keep"]


def test_duplicate_names_stay_in_item_folders(tmp_path):
    database = tmp_path / "Photos.sqlite"
    make_database(database, [("first", 0, 0, 0), ("second", 0, 0, 0)])
    root = tmp_path / "export"
    result = intake.export_items(database, root, exporter=write_export)
    assert result == {"eligible": 2, "checked": 2, "skipped": 0, "failed": 0}
    folders = list((root / "assets").iterdir())
    assert len(folders) == 2
    assert all((folder / "photo.jpg").exists() for folder in folders)


def test_photo_and_motion_members_are_recorded(tmp_path):
    database = tmp_path / "Photos.sqlite"
    make_database(database, [("live", 0, 0, 0)])
    root = tmp_path / "export"
    intake.export_items(database, root, exporter=write_export)
    record = intake.latest_records(root / "manifest.jsonl")["live"]
    assert {member["role"] for member in record["members"]} == {"photo", "live_photo_motion"}


def test_incomplete_staging_reexports_item(tmp_path):
    database = tmp_path / "Photos.sqlite"
    make_database(database, [("keep", 0, 0, 0)])
    root = tmp_path / "export"
    staging = root / ".staging" / intake.safe_item_id("keep")
    staging.mkdir(parents=True)
    (staging / "old.jpg").write_bytes(b"old")
    result = intake.export_items(database, root, exporter=write_export)
    assert result["checked"] == 1
    assert not staging.exists()
    assert (root / "assets" / intake.safe_item_id("keep") / "photo.jpg").exists()


def test_one_failure_does_not_stop_later_items(tmp_path):
    database = tmp_path / "Photos.sqlite"
    make_database(database, [("bad", 0, 0, 0), ("good", 0, 0, 0)])

    def export(item_id, folder):
        if item_id == "bad":
            raise RuntimeError("test failure")
        write_export(item_id, folder)

    result = intake.export_items(database, tmp_path / "export", exporter=export)
    assert result == {"eligible": 2, "checked": 1, "skipped": 0, "failed": 1}


def test_hash_conflict_quarantines_and_reexports(tmp_path):
    database = tmp_path / "Photos.sqlite"
    make_database(database, [("keep", 0, 0, 0)])
    root = tmp_path / "export"
    intake.export_items(database, root, exporter=write_export)
    asset = root / "assets" / intake.safe_item_id("keep") / "photo.jpg"
    asset.write_bytes(b"changed")
    result = intake.export_items(database, root, exporter=write_export)
    assert result["checked"] == 1
    assert any((root / "quarantine").iterdir())


def test_checked_item_skips_only_after_hash_recheck(tmp_path):
    database = tmp_path / "Photos.sqlite"
    make_database(database, [("keep", 0, 0, 0)])
    root = tmp_path / "export"
    intake.export_items(database, root, exporter=write_export)
    result = intake.export_items(database, root, exporter=write_export)
    assert result == {"eligible": 1, "checked": 0, "skipped": 1, "failed": 0}


def build_checked_source(tmp_path, item_id="keep"):
    database = tmp_path / "Photos.sqlite"
    make_database(database, [(item_id, 0, 0, 0)])
    source = tmp_path / "source"
    intake.export_items(database, source, exporter=write_export)
    return source


def test_excluded_hashes_stay_suppressed(tmp_path):
    source = build_checked_source(tmp_path)
    record = intake.latest_records(source / "manifest.jsonl")["keep"]
    exclusion = tmp_path / "excluded.jsonl"
    exclusion.write_text(json.dumps({"sha256": record["members"][0]["sha256"]}) + "\n")
    result = intake.mirror_receipt(source, tmp_path / "incoming", exclusion)
    assert result["suppressed"] == 1
    assert not list((tmp_path / "incoming" / "accepted").iterdir())


def test_receipt_fails_when_member_is_missing(tmp_path):
    source = build_checked_source(tmp_path)
    record = intake.latest_records(source / "manifest.jsonl")["keep"]
    asset = source / "assets" / record["safe_id"] / "photo.jpg"
    asset.unlink()
    result = intake.mirror_receipt(source, tmp_path / "incoming")
    assert result["unresolved"] == 1
    assert not (tmp_path / "incoming" / "COMPLETE").exists()


def test_repeated_mirror_creates_no_duplicate(tmp_path):
    source = build_checked_source(tmp_path)
    destination = tmp_path / "incoming"
    first = intake.mirror_receipt(source, destination)
    second = intake.mirror_receipt(source, destination)
    assert first["accepted"] == 1
    assert second["skipped"] == 1
    assert len(list((destination / "accepted").iterdir())) == 1


def test_complete_cannot_exist_with_unresolved_work(tmp_path):
    source = build_checked_source(tmp_path)
    destination = tmp_path / "incoming"
    (destination / "COMPLETE").parent.mkdir(parents=True)
    (destination / "COMPLETE").write_text("old\n")
    result = intake.mirror_receipt(
        source,
        destination,
        expected_item_ids={"keep", "unexported"},
        write_complete=True,
    )
    assert result["unresolved"] == 1
    assert not (destination / "COMPLETE").exists()
    assert any(path.name.startswith("COMPLETE-") for path in (destination / "quarantine").iterdir())


def test_lock_file_recovers_after_process_exit(tmp_path):
    lock = tmp_path / ".lock"
    lock.write_text("stale")
    with intake.directory_lock(lock):
        assert lock.exists()
    descriptor = lock.open("r+")
    fcntl.flock(descriptor.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    fcntl.flock(descriptor.fileno(), fcntl.LOCK_UN)
    descriptor.close()


def test_torn_final_receipt_line_is_ignored_and_archived_before_append(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"item_id": "keep"}) + "\n" + '{"item_id":')
    assert intake.latest_records(manifest) == {"keep": {"item_id": "keep"}}
    intake.append_record(manifest, {"item_id": "next"})
    assert intake.latest_records(manifest) == {
        "keep": {"item_id": "keep"},
        "next": {"item_id": "next"},
    }
    assert any("-torn" in path.name for path in (tmp_path / "quarantine").iterdir())


def test_malformed_earlier_receipt_line_fails(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text('{"item_id":\n' + json.dumps({"item_id": "keep"}) + "\n")
    try:
        intake.latest_records(manifest)
    except ValueError as error:
        assert "line 1" in str(error)
    else:
        raise AssertionError("A malformed earlier receipt line must fail")


def test_append_record_flushes_and_syncs(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(intake.os, "fsync", lambda descriptor: called.append(descriptor))
    intake.append_record(tmp_path / "manifest.jsonl", {"item_id": "keep"})
    assert called


def test_route_change_archives_old_generated_copy(tmp_path):
    source = build_checked_source(tmp_path)
    destination = tmp_path / "incoming"
    intake.mirror_receipt(source, destination)
    record = intake.latest_records(source / "manifest.jsonl")["keep"]
    exclusion = tmp_path / "excluded.jsonl"
    exclusion.write_text(json.dumps({"sha256": record["members"][0]["sha256"]}) + "\n")
    intake.mirror_receipt(source, destination, exclusion)
    safe_id = record["safe_id"]
    assert not (destination / "accepted" / safe_id).exists()
    assert (destination / "suppressed" / safe_id).exists()
    assert any("route-changed" in path.name for path in (destination / "quarantine").iterdir())


def test_ineligible_item_leaves_no_generated_reader_copy(tmp_path):
    source = build_checked_source(tmp_path)
    destination = tmp_path / "incoming"
    intake.mirror_receipt(source, destination, expected_item_ids={"keep"}, write_complete=True)
    assert (destination / "COMPLETE").exists()
    result = intake.mirror_receipt(source, destination, expected_item_ids=set(), write_complete=True)
    safe_id = intake.latest_records(source / "manifest.jsonl")["keep"]["safe_id"]
    assert result["ineligible"] == 1
    assert not (destination / "accepted" / safe_id).exists()
    assert not (destination / "suppressed" / safe_id).exists()
    assert (destination / "COMPLETE").exists()
    assert any("ineligible" in path.name for path in (destination / "quarantine").iterdir())


def test_applescript_text_uses_stable_media_identifier(monkeypatch, tmp_path):
    command = {}

    def fake_run(arguments, **kwargs):
        command["arguments"] = arguments

    monkeypatch.setattr(intake.subprocess, "run", fake_run)
    intake.applescript_export("ABC-123", tmp_path)
    script = command["arguments"][2]
    assert 'media item id "ABC-123/L0/001"' in script
    assert "with using originals" in script


# --- the second identity: the sidecar ---------------------------------------


def test_accepted_folder_carries_the_second_identity(tmp_path):
    database = tmp_path / "Photos.sqlite"
    make_database(database, [("keep", 0, 0, 0)])
    source = tmp_path / "source"
    intake.export_items(database, source, exporter=write_export)
    destination = tmp_path / "incoming"
    intake.mirror_receipt(source, destination)
    safe_id = intake.latest_records(source / "manifest.jsonl")["keep"]["safe_id"]
    sidecar = json.loads((destination / "accepted" / safe_id / "identity.json").read_text())
    assert sidecar["item_id"] == "keep"
    assert sidecar["safe_id"] == safe_id
    assert [member["relative_path"] for member in sidecar["members"]] == ["photo.jpg"]


def test_sidecar_does_not_make_the_next_run_repeat_the_work(tmp_path):
    source = build_checked_source(tmp_path)
    destination = tmp_path / "incoming"
    first = intake.mirror_receipt(source, destination)
    second = intake.mirror_receipt(source, destination)
    assert first["accepted"] == 1
    assert second["skipped"] == 1
    assert second["quarantined"] == 0
    assert (destination / "accepted" / intake.latest_records(source / "manifest.jsonl")["keep"]["safe_id"] / "identity.json").exists()


def test_a_missing_member_is_still_caught_beside_the_sidecar(tmp_path):
    source = build_checked_source(tmp_path)
    destination = tmp_path / "incoming"
    intake.mirror_receipt(source, destination)
    safe_id = intake.latest_records(source / "manifest.jsonl")["keep"]["safe_id"]
    (destination / "accepted" / safe_id / "photo.jpg").rename(destination / "accepted" / safe_id / "moved.jpg")
    result = intake.mirror_receipt(source, destination)
    assert result["skipped"] == 0
    assert result["quarantined"] == 1


def test_an_exported_file_named_like_the_sidecar_is_held(tmp_path):
    database = tmp_path / "Photos.sqlite"
    make_database(database, [("keep", 0, 0, 0)])

    def export(item_id, folder):
        (folder / "identity.json").write_bytes(b"not-the-sidecar")

    source = tmp_path / "source"
    intake.export_items(database, source, exporter=export)
    destination = tmp_path / "incoming"
    result = intake.mirror_receipt(source, destination)
    assert result["unresolved"] == 1
    assert result["accepted"] == 0
    assert not list((destination / "accepted").iterdir())


def test_capture_date_and_original_name_reach_the_receipt(tmp_path):
    database = tmp_path / "Photos.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE ZASSET (Z_PK INTEGER, ZUUID TEXT, ZKIND INTEGER, ZTRASHEDSTATE INTEGER, ZHIDDEN INTEGER, ZDATECREATED REAL, ZFILENAME TEXT)")
        connection.execute("CREATE TABLE ZADDITIONALASSETATTRIBUTES (ZASSET INTEGER, ZORIGINALFILENAME TEXT)")
        connection.execute("INSERT INTO ZASSET VALUES (1, 'keep', 0, 0, 0, 700000000.0, 'IMG_0001.HEIC')")
        connection.execute("INSERT INTO ZADDITIONALASSETATTRIBUTES VALUES (1, 'IMG_0001.HEIC')")
    source = tmp_path / "source"
    intake.export_items(database, source, exporter=write_export)
    record = intake.latest_records(source / "manifest.jsonl")["keep"]
    assert record["original_filename"] == "IMG_0001.HEIC"
    # Photos counts seconds from 1 Jan 2001, so 700000000 is 8 Mar 2023.
    assert record["capture_date"] == "2023-03-08 20:26:40"


def test_export_still_runs_when_the_identity_columns_are_absent(tmp_path):
    database = tmp_path / "Photos.sqlite"
    make_database(database, [("keep", 0, 0, 0)])
    result = intake.export_items(database, tmp_path / "source", exporter=write_export)
    assert result["checked"] == 1
    record = intake.latest_records(tmp_path / "source" / "manifest.jsonl")["keep"]
    assert record["capture_date"] is None
    assert record["original_filename"] is None


# --- the second lane: the picture hash -------------------------------------
#
# These tests use real pictures, because the lane reads picture content. The
# other tests above write fake bytes named photo.jpg on purpose; picture_hashes
# must keep returning an empty list for those, so those tests keep passing.


def make_picture(path, seed=1, size=(800, 600), quality=95, rotate=0):
    """Write one real JPEG built from a fixed pattern, so runs agree."""
    import random

    from PIL import Image

    generator = random.Random(seed)
    blocks = Image.new("RGB", (16, 12))
    blocks.putdata(
        [
            (generator.randrange(256), generator.randrange(256), generator.randrange(256))
            for _ in range(16 * 12)
        ]
    )
    image = blocks.resize(size, Image.Resampling.BILINEAR)
    if rotate:
        image = image.rotate(rotate, expand=True)
    image.save(path, "JPEG", quality=quality)
    return path


def picture_exporter(path):
    """Return an exporter that places one real picture as photo.jpg."""

    def export(item_id, folder):
        import shutil

        shutil.copyfile(path, folder / "photo.jpg")

    return export


def hash_row(path, name="photo.jpg", size=None):
    """Build one excluded-picture row the way the Mini A builder writes it."""
    return {
        "sha256": "0" * 64,
        "name": name,
        "size": path.stat().st_size if size is None else size,
        "phash": intake.picture_hashes(path, rotations=True),
    }


def mirror_with_picture_hashes(tmp_path, arriving, rows):
    """Export one arriving picture and mirror it against recorded hashes."""
    database = tmp_path / "Photos.sqlite"
    make_database(database, [("keep", 0, 0, 0)])
    source = tmp_path / "source"
    intake.export_items(database, source, exporter=picture_exporter(arriving))
    hash_file = tmp_path / "excluded_picture_hashes.jsonl"
    hash_file.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return intake.mirror_receipt(source, tmp_path / "incoming", picture_hash_file=hash_file)


def test_reencoded_copy_of_an_excluded_picture_is_suppressed(tmp_path):
    original = make_picture(tmp_path / "original.jpg", seed=1, quality=95)
    arriving = make_picture(tmp_path / "arriving.jpg", seed=1, quality=25)
    assert original.read_bytes() != arriving.read_bytes()
    result = mirror_with_picture_hashes(tmp_path, arriving, [hash_row(original)])
    assert result["suppressed"] == 1
    assert result["suppressed_picture_hash"] == 1
    assert result["suppressed_file_hash"] == 0
    assert not list((tmp_path / "incoming" / "accepted").iterdir())


def test_rotated_copy_of_an_excluded_picture_is_suppressed(tmp_path):
    original = make_picture(tmp_path / "original.jpg", seed=2, quality=95)
    arriving = make_picture(tmp_path / "arriving.jpg", seed=2, quality=90, rotate=90)
    result = mirror_with_picture_hashes(tmp_path, arriving, [hash_row(original)])
    assert result["suppressed_picture_hash"] == 1
    assert not list((tmp_path / "incoming" / "accepted").iterdir())


def test_unrelated_picture_of_the_same_size_is_not_suppressed(tmp_path):
    other = make_picture(tmp_path / "other.jpg", seed=3, quality=95)
    arriving = make_picture(tmp_path / "arriving.jpg", seed=99, quality=95)
    row = hash_row(other, name="not-the-same-name.jpg", size=arriving.stat().st_size)
    result = mirror_with_picture_hashes(tmp_path, arriving, [row])
    assert result["suppressed"] == 0
    assert result["accepted"] == 1


def test_fake_bytes_are_never_read_as_a_picture(tmp_path):
    fake = tmp_path / "photo.jpg"
    fake.write_bytes(b"image-keep")
    assert intake.picture_hashes(fake) == []


def test_exporter_picture_hash_still_agrees_with_the_recorded_method(tmp_path):
    """Drift guard. The exporter holds a copy because Mini A has no checkout."""
    from PIL import Image

    from image_plane import phash

    picture = make_picture(tmp_path / "drift.jpg", seed=4, quality=92)
    with Image.open(picture) as image:
        image.load()
        assert intake._dhash_hex(image) == phash.dhash_hex(image)


def test_exporter_hamming_agrees_with_the_recorded_method():
    """Mini A runs Python 3.9, where int.bit_count does not exist."""
    from image_plane import phash

    pairs = [("0000000000000000", "ffffffffffffffff"), ("0123456789abcdef", "0123456789abcdef"), ("00ff00ff00ff00ff", "0f0f0f0f0f0f0f0f")]
    for hex_a, hex_b in pairs:
        assert intake.hamming_hex(hex_a, hex_b) == phash.hamming(hex_a, hex_b)


def test_intake_source_contains_no_delete_call():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert ".unlink(" not in source
    assert "rmtree(" not in source
    assert "rm -" not in source
