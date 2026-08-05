#!/usr/bin/env python3
from __future__ import annotations
"""Judge one named few-shot run with the local text model."""

import argparse
import json
import re
import signal
import sys
import urllib.request
from pathlib import Path

MODEL = "qwen3:32b"
OLLAMA = "http://localhost:11434/api/generate"
PER_ROW_CAP = 90


class JudgeTimeout(Exception):
    pass


def alarm_handler(_signum, _frame):
    raise JudgeTimeout()


def load_run(run: Path) -> tuple[dict, list[dict], Path]:
    manifest_path = run / "manifest.json"
    results_path = run / "heldout_results.json"
    if not manifest_path.exists() or not results_path.exists():
        raise ValueError("The run folder needs manifest.json and heldout_results.json")
    manifest = json.loads(manifest_path.read_text())
    results = json.loads(results_path.read_text())
    if manifest.get("run_id") != run.name or results.get("run_id") != run.name:
        raise ValueError("The result file does not belong to this run folder")
    judge_path = run / "note_judge.json"
    if judge_path.exists() and json.loads(judge_path.read_text()).get("run_id") != run.name:
        raise ValueError("The judge file belongs to another run")
    return manifest, results.get("results", []), judge_path


def judge_one(note_text: str, engine_labels: list[str]) -> dict | None:
    prompt = (
        f'A roof surveyor wrote this note about a green-roof photo:\n"{note_text}"\n\n'
        f"A photo reader returned these labels:\n{json.dumps(engine_labels)}\n\n"
        "Judge labels against the note only. Reply with JSON using supported, unsupported, and missed lists."
    )
    request = urllib.request.Request(
        OLLAMA,
        data=json.dumps({"model": MODEL, "prompt": prompt, "stream": False, "think": False, "options": {"num_ctx": 4096, "temperature": 0.0}}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            text = json.loads(response.read()).get("response", "")
    except Exception:
        return None
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        verdict = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return {key: verdict.get(key, []) if isinstance(verdict.get(key), list) else [] for key in ("supported", "unsupported", "missed")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    _manifest, rows, output = load_run(args.run)
    judged = []
    for index, row in enumerate(rows, 1):
        note = (row.get("lee_note") or "").strip()
        if not note:
            continue
        signal.signal(signal.SIGALRM, alarm_handler)
        signal.alarm(PER_ROW_CAP)
        try:
            verdict = judge_one(note, row.get("engine_labels", []))
        finally:
            signal.alarm(0)
        if verdict is None:
            continue
        labels = row.get("engine_labels", [])
        supported = verdict["supported"]
        missed = verdict["missed"]
        judged.append({
            "case_id": row["case_id"], "engine_labels": labels, **verdict,
            "precision": len(supported) / len(labels) if labels else 0.0,
            "recall_proxy": len(supported) / (len(supported) + len(missed)) if supported or missed else 0.0,
        })
    output.write_text(json.dumps({"run_id": args.run.name, "judged": judged}, indent=2))
    print(f"Wrote {len(judged)} judge rows to {output}")


if __name__ == "__main__":
    main()
