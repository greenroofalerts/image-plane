#!/usr/bin/env python3
from __future__ import annotations
"""Render one named few-shot run as a large-photo contact sheet."""

import argparse
import base64
import html
import json
import subprocess
from pathlib import Path

MAX_W = 1100


def load_run_data(run: Path) -> tuple[dict, list[dict], dict]:
    manifest_path = run / "manifest.json"
    results_path = run / "heldout_results.json"
    if not manifest_path.exists() or not results_path.exists():
        raise ValueError("The run folder needs manifest.json and heldout_results.json")
    manifest = json.loads(manifest_path.read_text())
    data = json.loads(results_path.read_text())
    if manifest.get("run_id") != run.name or data.get("run_id") != run.name:
        raise ValueError("The result file does not belong to this run folder")
    judge = {}
    judge_path = run / "note_judge.json"
    if judge_path.exists():
        judge_data = json.loads(judge_path.read_text())
        if judge_data.get("run_id") != run.name:
            raise ValueError("The judge file belongs to another run")
        judge = {row["case_id"]: row for row in judge_data.get("judged", [])}
    return manifest, data.get("results", []), judge


def image_b64(path: str, index: int) -> str:
    temporary = f"/tmp/_fewshot_sheet_{index}.jpg"
    try:
        subprocess.run(["sips", "-Z", str(MAX_W), "-s", "format", "jpeg", "-s", "formatOptions", "82", path, "--out", temporary], check=True, capture_output=True)
        return base64.b64encode(Path(temporary).read_bytes()).decode()
    except Exception:
        return ""


def esc(value: object) -> str:
    return html.escape(str(value))


CSS = """
body{font-family:-apple-system,system-ui,sans-serif;background:#1b1b1b;color:#eee;margin:0;padding:24px;}
.summary,.card{background:#262626;border:1px solid #3a3a3a;border-radius:10px;margin-bottom:24px;overflow:hidden;}
.summary,.meta{padding:16px 20px;line-height:1.5;}.card img{display:block;width:100%;min-width:1100px;}.row{margin:9px 0;}.label{color:#aaa;display:inline-block;width:140px;vertical-align:top}.value{display:inline-block;max-width:calc(100% - 150px)}.job{color:#8ab4f8;font-weight:600}.engine{color:#7ee78b}.judge{color:#ffd479}.warn{color:#ff9d7a;font-weight:600}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    manifest, rows, judge = load_run_data(args.run)
    parts = [f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"]
    judge_line = "No automatic judge ran." if not judge else "Automatic judge results appear where available."
    taught = sum(1 for row in rows if row.get("example_ids"))
    parts.append(
        f"<h1>Few-shot unseen-photo review</h1><div class='summary'>"
        f"This sheet shows {len(rows)} photos from run {esc(manifest['run_id'])}.<br>"
        f"Approved-review photos and excluded photos were withheld.<br>{judge_line}<br>"
        f"{taught} of the {len(rows)} photos got an approved example. "
        f"The other {len(rows) - taught} got none, so this sheet cannot show whether the "
        f"approved words help.<br>"
        f"<span class='warn'>Warning: photos you ruled out were kept out by their file bytes "
        f"only. A re-saved copy of a ruled-out photo would not be caught.</span></div>"
    )
    for index, row in enumerate(rows, 1):
        image = image_b64(row.get("absolute_path") or row.get("source_path", ""), index)
        image_html = f"<img src='data:image/jpeg;base64,{image}' alt='photo'>" if image else "<div class='meta'>Image unavailable.</div>"
        verdict = judge.get(row.get("case_id"), {})
        judge_text = "No automatic judge ran." if not verdict else f"Supported: {', '.join(verdict.get('supported', [])) or '—'}; Unsupported: {', '.join(verdict.get('unsupported', [])) or '—'}; Missed: {', '.join(verdict.get('missed', [])) or '—'}"
        parts.append(
            f"<div class='card'>{image_html}<div class='meta'>"
            f"<div class='job'>{esc(row.get('case_id', 'unknown'))} · {esc(row.get('job_ref') or 'No job reference')}</div>"
            f"<div class='row'><span class='label'>Example IDs:</span><span class='value'>{esc(', '.join(row.get('example_ids', [])) or 'None')}</span></div>"
            f"<div class='row'><span class='label'>Lee note:</span><span class='value'>{esc(row.get('lee_note') or '—')}</span></div>"
            f"<div class='row'><span class='label'>Lee tags:</span><span class='value'>{esc(', '.join(row.get('lee_tags', [])) or '—')}</span></div>"
            f"<div class='row engine'><span class='label'>Reader labels:</span><span class='value'>{esc(', '.join(row.get('engine_labels', [])) or '—')}</span></div>"
            f"<div class='row judge'><span class='label'>Judge:</span><span class='value'>{esc(judge_text)}</span></div></div></div>"
        )
    parts.append("</body></html>")
    output = args.run / "contact_sheet.html"
    output.write_text("".join(parts))
    print(f"Contact sheet written to {output}")


if __name__ == "__main__":
    main()
