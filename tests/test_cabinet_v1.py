"""Image Plane V1 cabinet, screen and consumer contracts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from image_plane import albums
from image_plane import cabinet
from image_plane import gra
from image_plane import identity
from image_plane import notes
from image_plane import pack
from image_plane import paths
from image_plane import report
from image_plane import server
from image_plane.ingest import sha256_file


@pytest.fixture()
def plane(tmp_path, monkeypatch):
    root = tmp_path / "image-plane"
    incoming = root / "incoming" / "google" / "1892-26"
    incoming.mkdir(parents=True)
    (root / "grind").mkdir()
    (root / "grind" / "allocation_v2.jsonl").write_text("", encoding="utf-8")
    (root / "geolocations.jsonl").write_text("", encoding="utf-8")
    (root / "grind" / "job_coords.json").write_text(
        json.dumps({"1892-26": {"lat": 51.5336, "lon": -0.1257, "name": "6 Pancras Square"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("IMAGE_PLANE_ROOT", str(root))
    monkeypatch.setenv("IMAGE_PLANE_CABINET", str(root / "cabinet"))
    monkeypatch.setenv("IMAGE_PLANE_LADDER_BASE", str(root))
    identity._ENGINE = None
    identity._ENGINE_ERROR = None
    return root


def _copy_scene(fixtures: Path, dest: Path, name: str = "scene_00.jpg") -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fixtures / "takeout" / "scene_00.jpg", dest)
    return dest


def _write_gps_sidecar(image: Path, lat=51.5336, lon=-0.1257, ts=1755532800):
    sidecar = image.with_name(image.name + ".json")
    sidecar.write_text(
        json.dumps({"photoTakenTime": {"timestamp": str(ts)}, "geoData": {"latitude": lat, "longitude": lon}}),
        encoding="utf-8",
    )
    return sidecar


def test_date_alone_cannot_file(conn, fixtures, plane):
    src = _copy_scene(fixtures, plane / "incoming" / "google" / "1892-26" / "only-date.jpg")
    _write_gps_sidecar(src, lat=0.0, lon=0.0)
    result = cabinet.file_one(conn, src, album_title="Visit 18 August 2026")
    assert result["status"] == "quarantined"
    assert result["item"]["filed_job_ref"] is None
    ev = json.loads(result["item"]["identity_evidence"])
    assert ev["date_used_for_identity"] is False
    assert ev["may_file"] is False


def test_album_title_alone_cannot_file(conn, fixtures, plane):
    src = _copy_scene(fixtures, plane / "incoming" / "google" / "1892-26" / "title-only.jpg")
    result = cabinet.file_one(conn, src, album_title="1892-26 Greengage 6 Pancras Square")
    assert result["status"] == "quarantined"
    assert result["item"]["filed_job_ref"] is None
    ev = json.loads(result["item"]["identity_evidence"])
    names = [l["name"] for l in ev["lanes"]]
    assert names == ["album_title"]


def test_two_lanes_file_against_1892(conn, fixtures, plane):
    src = _copy_scene(fixtures, plane / "incoming" / "google" / "1892-26" / "roof.jpg")
    _write_gps_sidecar(src)
    result = cabinet.file_one(conn, src, album_title="1892-26 Greengage Pancras")
    assert result["status"] == "resolved"
    assert result["item"]["filed_job_ref"] == "1892-26"
    ev = json.loads(result["item"]["identity_evidence"])
    assert ev["may_file"] is True
    assert ev["date_used_for_identity"] is False
    names = {l["name"] for l in ev["lanes"]}
    assert "album_title" in names
    assert "lane2_gra_sites" in names
    assert Path(result["item"]["cabinet_path"]).is_file()
    assert Path(result["item"]["original_path"]).is_file()
    assert Path(result["item"]["cabinet_path"]) != Path(result["item"]["original_path"])


def test_original_bytes_unchanged_and_hash_stable(conn, fixtures, plane):
    src = _copy_scene(fixtures, plane / "incoming" / "google" / "1892-26" / "keep.jpg")
    before = src.read_bytes()
    digest = sha256_file(src)
    cabinet.file_one(conn, src, album_title="no-ref")
    assert src.read_bytes() == before
    assert sha256_file(src) == digest


def test_dedup_keeps_both_sources(conn, fixtures, plane):
    a = _copy_scene(fixtures, plane / "incoming" / "google" / "1892-26" / "a.jpg")
    b = plane / "incoming" / "google" / "1892-26" / "b.jpg"
    shutil.copy2(a, b)
    first = cabinet.file_one(conn, a, album_title="x")
    second = cabinet.file_one(conn, b, album_title="x")
    assert first["item"]["file_hash"] == second["item"]["file_hash"]
    assert second["item"]["duplicate_of"] == first["item"]["id"]
    assert Path(first["item"]["original_path"]).is_file()
    assert Path(second["item"]["original_path"]).is_file()


def test_lee_note_attaches_by_hash_not_date(conn, fixtures, plane):
    src = _copy_scene(fixtures, plane / "incoming" / "google" / "1892-26" / "noted.jpg")
    digest = sha256_file(src)
    notes_path = plane / "knowledge_notes.jsonl"
    notes_path.write_text(
        json.dumps({"sha256": digest, "job_ref": "1892-26", "note": "outlet blocked at north edge", "source": "lee_dictate"})
        + "\n",
        encoding="utf-8",
    )
    result = cabinet.file_one(conn, src, stage_job="1892-26", album_title="random album")
    assert result["item"]["observation_confirmed"] == "outlet blocked at north edge"
    assert result["item"]["observation_source"] == "lee_dictate"
    assert result["item"]["confirmation_state"] == "confirmed"


def test_date_cannot_attach_unrelated_note(conn, fixtures, plane):
    src = _copy_scene(fixtures, plane / "incoming" / "google" / "1892-26" / "other.jpg")
    (plane / "knowledge_notes.jsonl").write_text(
        json.dumps({"job_ref": "1892-26", "note": "some other roof note", "taken_at": "2026-08-18", "source": "lee_dictate"})
        + "\n",
        encoding="utf-8",
    )
    result = cabinet.file_one(conn, src, stage_job="1892-26", album_title="random")
    assert result["item"]["observation_confirmed"] is None


def test_saved_selection_survives_reopen(conn, fixtures, plane):
    src = _copy_scene(fixtures, plane / "incoming" / "google" / "1892-26" / "pick.jpg")
    item = cabinet.file_one(conn, src, stage_job="1892-26")["item"]
    cabinet.save_selection(conn, "1892-26", "pancras-diagnostic", [item["id"]])
    again = cabinet.get_selection(conn, "1892-26", "pancras-diagnostic")
    assert again["item_ids"] == [item["id"]]
    assert again["items"][0]["id"] == item["id"]


def test_report_excludes_machine_suggestion(conn, fixtures, plane):
    src = _copy_scene(fixtures, plane / "incoming" / "google" / "1892-26" / "cap.jpg")
    item = cabinet.file_one(conn, src, stage_job="1892-26", machine_caption="looks like moss")["item"]
    cabinet.save_selection(conn, "1892-26", "mix", [item["id"]])
    dest = report.build_report_pdf(conn, "1892-26", "mix", plane / "out.pdf")
    data = dest.read_bytes()
    assert data.startswith(b"%PDF")
    assert b"looks like moss" not in data
    assert b"Machine suggestions are excluded" in data


def test_report_includes_confirmed_caption_and_real_image(conn, fixtures, plane):
    src = _copy_scene(fixtures, plane / "incoming" / "google" / "1892-26" / "ok.jpg")
    digest = sha256_file(src)
    (plane / "knowledge_notes.jsonl").write_text(
        json.dumps({"sha256": digest, "note": "north outlet silted", "source": "lee_dictate"}) + "\n",
        encoding="utf-8",
    )
    item = cabinet.file_one(conn, src, stage_job="1892-26")["item"]
    cabinet.save_selection(conn, "1892-26", "confirmed-set", [item["id"]])
    dest = report.build_report_pdf(conn, "1892-26", "confirmed-set", plane / "report.pdf")
    data = dest.read_bytes()
    assert b"north outlet silted" in data
    assert b"1892-26" in data
    assert b"Greengage" in data


def test_gra_copies_only_approved(conn, fixtures, plane):
    a = _copy_scene(fixtures, plane / "incoming" / "google" / "1892-26" / "pub.jpg")
    b = plane / "incoming" / "google" / "1892-26" / "keep-private.jpg"
    shutil.copy2(fixtures / "takeout" / "scene_01.jpg", b)
    ia = cabinet.file_one(conn, a, stage_job="1892-26")["item"]
    ib = cabinet.file_one(conn, b, stage_job="1892-26")["item"]
    cabinet.set_visibility(conn, [ia["id"]], "approved")
    cabinet.save_selection(conn, "1892-26", "gra-try", [ia["id"], ib["id"]])
    payload = gra.prepare_publication(conn, "1892-26", "gra-try", dest_dir=plane / "gra")
    assert len(payload["approved_copied"]) == 1
    assert payload["approved_copied"][0]["cabinet_id"] == ia["id"]
    assert ib["file_hash"] not in gra.customer_visible_hashes(plane / "gra")
    assert payload["blocker"]


def test_installer_pack_keeps_order_and_provenance(conn, fixtures, plane):
    src = _copy_scene(fixtures, plane / "incoming" / "google" / "1892-26" / "pack.jpg")
    digest = sha256_file(src)
    (plane / "knowledge_notes.jsonl").write_text(
        json.dumps({"sha256": digest, "note": "keep outlet clear of fleece", "source": "existing_note"}) + "\n",
        encoding="utf-8",
    )
    item = cabinet.file_one(conn, src, stage_job="1892-26")["item"]
    cabinet.save_selection(conn, "1892-26", "phase-pack", [item["id"]])
    dest = pack.export_pack(conn, "1892-26", "phase-pack", plane / "pack")
    manifest = json.loads((dest / "manifest.json").read_text())
    assert manifest["items"][0]["file_hash"] == item["file_hash"]
    assert manifest["items"][0]["caption"] == "keep outlet clear of fleece"
    assert (dest / "pack.pdf").is_file()
    assert list((dest / "media").iterdir())


def test_album_discovery_without_token_preserves_named_route(conn, plane):
    result = albums.discover_google_albums(conn)
    assert result["ok"] is False
    assert "Named-folder ingest" in result["blocker"]
    src_dir = plane / "incoming" / "google" / "1892-26"
    # folder empty still records the album and does not mint
    out = albums.ingest_named_album(conn, src_dir)
    assert out["counts"]["found"] == 0
    assert out["stage_job"] == "1892-26"


def test_historic_job_without_evidence_is_plain(conn, plane):
    items = cabinet.items_for_job(conn, "1124-19")
    assert items == []
    html = server.render_job(conn, "1124-19", "waterproofing", ["installation"], None)
    assert "no evidenced records" in html.lower() or "best evidenced subset: 0" in html.lower()
    assert "1124-19" in html


def test_job_screen_lists_real_cabinet_rows(conn, fixtures, plane):
    src = _copy_scene(fixtures, plane / "incoming" / "google" / "1892-26" / "show.jpg")
    _write_gps_sidecar(src)
    item = cabinet.file_one(conn, src, album_title="1892-26 Greengage")["item"]
    html = server.render_job(conn, "1892-26", "", [], None)
    assert "show.jpg" in html
    assert item["file_hash"][:12] in html
    assert "Greengage" in html
    assert "/job/1892-26" in html


def test_filter_and_search_change_results(conn, fixtures, plane):
    src = _copy_scene(fixtures, plane / "incoming" / "google" / "1892-26" / "outlet.jpg")
    digest = sha256_file(src)
    (plane / "knowledge_notes.jsonl").write_text(
        json.dumps({"sha256": digest, "note": "waterproofing at outlet", "source": "lee_dictate"}) + "\n",
        encoding="utf-8",
    )
    item = cabinet.file_one(conn, src, stage_job="1892-26")["item"]
    cabinet.set_fields(conn, item["id"], {"phase": "diagnostic inspection", "component": "outlet"})
    rows = cabinet.items_for_job(conn, "1892-26")
    assert cabinet.filter_items(rows, "outlet", [])
    assert not cabinet.filter_items(rows, "skylight", [])
    assert cabinet.filter_items(rows, "", ["Waterproofing"])
    assert not cabinet.filter_items(rows, "", ["Irrigation"])


def test_never_serve_incoming_path_from_cabinet_record(conn, fixtures, plane):
    src = _copy_scene(fixtures, plane / "incoming" / "google" / "1892-26" / "served.jpg")
    item = cabinet.file_one(conn, src, stage_job="1892-26")["item"]
    assert Path(item["cabinet_path"]).is_file()
    assert Path(item["original_path"]) == src
    assert Path(item["cabinet_path"]).resolve() != src.resolve()
    assert (plane / "cabinet" / "media") in Path(item["cabinet_path"]).parents


def test_ladder_blocked_still_creates_visible_quarantine(conn, fixtures, plane, monkeypatch):
    monkeypatch.setenv("IMAGE_PLANE_LADDER_MODULE", str(plane / "missing-ladder.py"))
    identity._ENGINE = None
    identity._ENGINE_ERROR = None
    src = _copy_scene(fixtures, plane / "incoming" / "google" / "1892-26" / "blocked.jpg")
    result = cabinet.file_one(conn, src, stage_job="1892-26")
    assert result["status"] == "ladder_blocked"
    html = server.render_job(conn, "1892-26", "", [], None)
    assert "blocked.jpg" in html
    assert "quarantine" in html
