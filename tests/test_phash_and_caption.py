import json

from image_plane import ollama_client as oc
from image_plane.phash import dhash_hex, hamming

from PIL import Image


def test_dhash_stable_and_format():
    img = Image.new("RGB", (100, 80), (200, 30, 30))
    h1, h2 = dhash_hex(img), dhash_hex(img)
    assert h1 == h2
    assert len(h1) == 16
    int(h1, 16)  # valid hex


def test_hamming():
    assert hamming("0" * 16, "0" * 16) == 0
    assert hamming("0" * 16, "f" * 16) == 64
    assert hamming("0000000000000001", "0000000000000000") == 1


def test_pick_vision_model_prefers_best_family():
    models = ["llama3:8b", "llava:7b", "qwen2.5vl:3b", "nomic-embed-text:latest"]
    assert oc.pick_vision_model(models) == "qwen2.5vl:3b"


def test_pick_vision_model_none_installed():
    assert oc.pick_vision_model(["llama3:8b", "mistral:7b"]) is None
    assert oc.pick_vision_model([]) is None


def test_parse_caption_response_good_json():
    raw = json.dumps({"caption": "A red circle on yellow.", "tags": ["Red", " circle ", ""]})
    out = oc.parse_caption_response(raw)
    assert out["caption"] == "A red circle on yellow."
    assert out["tags"] == ["red", "circle"]


def test_parse_caption_response_malformed_json_falls_back():
    out = oc.parse_caption_response("A plain text answer, no JSON here")
    assert out["caption"].startswith("A plain text answer")
    assert out["tags"] == []


def test_parse_caption_response_json_missing_caption():
    out = oc.parse_caption_response('{"tags": ["x"]}')
    assert out["tags"] == []  # falls back to raw-text path


def test_all_fail_caption_run_exits_nonzero(conn, tmp_path, fixtures, monkeypatch):
    """LEE-559 R3: a caption run where every image fails must be loud —
    nonzero exit from the CLI, never a clean-looking 0."""
    from image_plane import cli as climod
    from image_plane import db as dbmod
    from image_plane import ingest

    db_path = tmp_path / "cap.db"
    c = dbmod.connect(db_path)
    ingest.ingest_folder(c, fixtures / "icloud")
    c.close()

    def boom(model, path):  # no network, hard rule: nothing leaves the machine
        raise RuntimeError("synthetic caption failure")

    monkeypatch.setattr(oc, "caption_image", boom)
    rc = climod.main(["--db", str(db_path), "caption", "--model", "fake-vision:0b"])
    assert rc == 2


def test_caption_failures_under_threshold_exit_zero(conn, tmp_path, fixtures, monkeypatch):
    """Counts always print; below --max-fail-pct the run still succeeds."""
    from image_plane import cli as climod
    from image_plane import db as dbmod
    from image_plane import ingest

    db_path = tmp_path / "cap2.db"
    c = dbmod.connect(db_path)
    ingest.ingest_folder(c, fixtures / "icloud")
    c.close()

    def fine(model, path):
        return {"caption": "a synthetic test image", "tags": ["test"]}

    monkeypatch.setattr(oc, "caption_image", fine)
    rc = climod.main(["--db", str(db_path), "caption", "--model", "fake-vision:0b"])
    assert rc == 0
