"""Minimal Ollama client over localhost HTTP. Stdlib only — no cloud,
no third-party HTTP libs. Talks exclusively to 127.0.0.1.
"""

from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger("image_plane.ollama")

BASE = "http://127.0.0.1:11434"

# Model families on Ollama that accept image input, best-first for a
# 24GB Apple Silicon machine. Used both to detect an already-installed
# vision model and to pick what to pull.
VISION_FAMILIES = [
    "qwen3-vl", "qwen2.5vl", "gemma3", "llama3.2-vision",
    "minicpm-v", "llava", "moondream", "bakllava",
]

# Recommended pull given ~12GB free disk on this machine (sizes are the
# Ollama registry download sizes).
RECOMMENDED_MODEL = "qwen2.5vl:3b"
RECOMMENDED_SIZE_GB = 3.2


def _post(path: str, payload: dict, timeout: int = 600) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def server_up() -> bool:
    try:
        with urllib.request.urlopen(BASE + "/api/tags", timeout=3):
            return True
    except (urllib.error.URLError, OSError):
        return False


def installed_models() -> list[str]:
    try:
        with urllib.request.urlopen(BASE + "/api/tags", timeout=5) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError):
        return []
    return [m["name"] for m in data.get("models", [])]


def pick_vision_model(models: list[str]) -> str | None:
    """Return the best installed vision-capable model, or None."""
    for family in VISION_FAMILIES:
        for m in models:
            if m.split(":")[0].lower() == family:
                return m
    return None


def pull(model: str) -> None:
    """Pull a model, streaming progress to the log."""
    req = urllib.request.Request(
        BASE + "/api/pull",
        data=json.dumps({"model": model}).encode(),
        headers={"Content-Type": "application/json"},
    )
    last_pct = -10
    with urllib.request.urlopen(req, timeout=7200) as resp:
        for line in resp:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "error" in msg:
                raise RuntimeError(f"ollama pull failed: {msg['error']}")
            total, done = msg.get("total"), msg.get("completed")
            if total and done:
                pct = int(done / total * 100)
                if pct >= last_pct + 10:
                    log.info("pull %s: %d%% of %.1f GB", model, pct, total / 1e9)
                    last_pct = pct
            elif msg.get("status") == "success":
                log.info("pull %s: complete", model)


def caption_image(model: str, image_path: Path, timeout: int = 300) -> dict:
    """Caption + tag one image. Returns {'caption': str, 'tags': [str], ...}.

    Asks for JSON output; falls back to wrapping raw text as the caption
    if the model returns malformed JSON (logged, never fatal).
    """
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    payload = {
        "model": model,
        "prompt": (
            "Describe this photo for a personal photo library. Respond as JSON with "
            'two keys: "caption" (one plain sentence) and "tags" (3 to 6 short '
            "lowercase keywords)."
        ),
        "images": [b64],
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 200},
    }
    data = _post("/api/generate", payload, timeout=timeout)
    raw = data.get("response", "")
    parsed = parse_caption_response(raw)
    parsed["eval_count"] = data.get("eval_count")
    parsed["total_duration_s"] = (data.get("total_duration") or 0) / 1e9
    return parsed


def parse_caption_response(raw: str) -> dict:
    try:
        obj = json.loads(raw)
        caption = str(obj.get("caption") or "").strip()
        tags = obj.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]
        tags = [str(t).strip().lower() for t in tags if str(t).strip()]
        if caption:
            return {"caption": caption, "tags": tags}
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass
    log.warning("model returned non-JSON caption; storing raw text. raw=%r", raw[:200])
    return {"caption": raw.strip()[:500], "tags": []}
