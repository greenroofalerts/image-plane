"""Attach existing Lee dictate / confirmed notes. Never invent wording."""

from __future__ import annotations

import json
from pathlib import Path

from . import paths

PACKAGE_NOTE = Path(__file__).resolve().parent / "data" / "1892-26.json"


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def job_context(job_ref: str | None) -> dict:
    if job_ref == paths.PANCRAS_JOB and PACKAGE_NOTE.is_file():
        try:
            return json.loads(PACKAGE_NOTE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _text_of(row: dict) -> str:
    for key in ("note", "text", "lee_note", "observation", "caption", "body"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _source_of(row: dict) -> str:
    raw = str(row.get("source") or row.get("kind") or "").lower()
    if "dictate" in raw or raw in {"lee", "lee_dictate", "lee_verdict", "lee_answer"}:
        return "lee_dictate"
    if raw in {"confirmed", "confirmed_decision", "decision"}:
        return "confirmed_decision"
    return "existing_note"


def match_note(file_hash: str, original_path: str, job_ref: str | None, base: Path | None = None) -> dict | None:
    """Return a legally matchable note, or None.

    A match requires the file hash, the exact original path, or an explicit
    filename mention on a row that already names the same job. Date alone
    never matches.
    """
    base = base or paths.root()
    candidates = [
        base / "knowledge_notes.jsonl",
        base / "grind" / "knowledge_notes.jsonl",
        paths.cabinet_dir() / "notes.jsonl",
    ]
    name = Path(original_path).name.lower()
    for path in candidates:
        for row in load_jsonl(path):
            text = _text_of(row)
            if not text:
                continue
            row_hash = str(row.get("sha256") or row.get("file_hash") or "").lower()
            row_path = str(row.get("path") or row.get("original_path") or "")
            row_job = str(row.get("job_ref") or row.get("job") or "")
            if row_hash and row_hash == file_hash.lower():
                return {"text": text, "source": _source_of(row), "matched_on": "file_hash"}
            if row_path and Path(row_path).as_posix() == Path(original_path).as_posix():
                return {"text": text, "source": _source_of(row), "matched_on": "path"}
            if job_ref and row_job == job_ref and name and name in text.lower():
                return {"text": text, "source": _source_of(row), "matched_on": "filename_in_job_note"}
    return None
