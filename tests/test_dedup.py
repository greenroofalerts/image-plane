from image_plane import dedup, ingest


def _ingest_all(conn, fixtures):
    ingest.ingest_folder(conn, fixtures / "takeout")
    ingest.ingest_folder(conn, fixtures / "icloud")
    ingest.ingest_folder(conn, fixtures / "variants", source="icloud")


def test_exact_duplicate_found(conn, fixtures):
    _ingest_all(conn, fixtures)
    stats = dedup.find_duplicates(conn)
    assert stats["exact"] == 1  # exact_copy.jpg is byte-identical to scene_00.jpg
    row = conn.execute(
        """SELECT p1.path dup, p2.path kept FROM duplicates d
           JOIN photos p1 ON p1.id=d.photo_id JOIN photos p2 ON p2.id=d.dup_of
           WHERE d.kind='exact'"""
    ).fetchone()
    assert "exact_copy" in row["dup"]
    assert "scene_00" in row["kept"]


def test_near_duplicates_found(conn, fixtures):
    _ingest_all(conn, fixtures)
    dedup.find_duplicates(conn)
    near = conn.execute(
        """SELECT p1.path dup FROM duplicates d
           JOIN photos p1 ON p1.id=d.photo_id WHERE d.kind='near'"""
    ).fetchall()
    near_names = {r["dup"].rsplit("/", 1)[-1] for r in near}
    # resized / re-encoded / brightness variants must near-match scene_00
    assert {"resized.jpg", "reencoded.jpg", "brighter.jpg"} <= near_names
    # the heavy crop must NOT match at the default threshold
    assert "heavy_crop.jpg" not in near_names


def test_distinct_scenes_not_flagged(conn, fixtures):
    ingest.ingest_folder(conn, fixtures / "takeout")
    ingest.ingest_folder(conn, fixtures / "icloud")
    stats = dedup.find_duplicates(conn)
    assert stats["exact"] == 0
    assert stats["near"] == 0  # 12 distinct synthetic scenes, no false positives


def test_dedup_idempotent(conn, fixtures):
    _ingest_all(conn, fixtures)
    first = dedup.find_duplicates(conn)
    second = dedup.find_duplicates(conn)
    assert first == second


def test_dedup_empty_db(conn):
    stats = dedup.find_duplicates(conn)
    assert stats == {"exact": 0, "near": 0, "photos": 0}
