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
