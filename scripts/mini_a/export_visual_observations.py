#!/usr/bin/env python3
"""
F5 backfill export — visual_observations from allocation_v2.

Spec: docs/F5-VISUAL-OBSERVATIONS-ROOF-TIMELINE-2026-07-11.md
Runs on Mini A (~/image-plane/). Reads:
  grind/allocation_v2.jsonl        (9,024 rows)
  grind/allocation_v2_flags.jsonl  (first row is _meta; skip it; rest = exclude by path)
  knowledge_notes.jsonl            (Lee's voice ground truth)
  geolocations.jsonl               (path -> GPS)

Export set = allocation_v2 rows whose path is NOT flagged. Matches counts.py's
`allocated_keeps` metric exactly (verify against `python3 counts.py --json`
before trusting output row count).

Writes:
  grind/visual_observations_backfill_20260711.jsonl          (exported rows)
  grind/visual_observations_backfill_residue_20260711.jsonl  (rows dropped for missing/empty date, with reason)

Read-only on all input files. Does not touch allocation_v2.jsonl, flags,
knowledge_notes.jsonl, counts.py, or guards.py.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path.home() / "image-plane"
ALLOC_PATH = BASE / "grind" / "allocation_v2.jsonl"
FLAGS_PATH = BASE / "grind" / "allocation_v2_flags.jsonl"
NOTES_PATH = BASE / "knowledge_notes.jsonl"
GEO_PATH = BASE / "geolocations.jsonl"

OUT_PATH = BASE / "grind" / "visual_observations_backfill_20260711.jsonl"
RESIDUE_PATH = BASE / "grind" / "visual_observations_backfill_residue_20260711.jsonl"


def load_jsonl(path):
    rows = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def main():
    alloc_rows = load_jsonl(ALLOC_PATH)

    flag_rows = load_jsonl(FLAGS_PATH)
    if not flag_rows or not flag_rows[0].get("_meta"):
        print("ERROR: expected first row of flags file to be _meta row", file=sys.stderr)
        sys.exit(1)
    flagged_paths = {r["path"] for r in flag_rows[1:] if "path" in r}

    # knowledge_notes.jsonl: group note/tags by exact path
    notes_by_path = defaultdict(lambda: {"notes": [], "tags": set()})
    for r in load_jsonl(NOTES_PATH):
        p = r.get("path")
        if not p:
            continue
        note = r.get("note")
        if note:
            notes_by_path[p]["notes"].append(note)
        for t in r.get("tags") or []:
            notes_by_path[p]["tags"].add(t)

    # geolocations.jsonl: path -> (lat, lon)
    geo_by_path = {}
    for r in load_jsonl(GEO_PATH):
        p = r.get("path")
        if not p:
            continue
        geo_by_path[p] = (r.get("lat"), r.get("lon"))

    exported = []
    residue = []

    for row in alloc_rows:
        path = row.get("path")
        if path is None or path in flagged_paths:
            continue

        date = row.get("date")
        if not date:
            residue.append({
                "path": path,
                "job_ref": row.get("job_ref"),
                "reason": "missing_or_empty_date",
            })
            continue

        lat, lon = geo_by_path.get(path, (None, None))

        note_info = notes_by_path.get(path)
        if note_info and note_info["notes"]:
            lee_note = "\n".join(note_info["notes"])
            tags = sorted(note_info["tags"])
            tags_source = "lee_voice"
        else:
            lee_note = None
            tags = []
            tags_source = None

        out_row = {
            "original_path": path,
            "job_ref": row.get("job_ref"),
            "visit_date": date,
            "building": row.get("building"),
            "activity": row.get("activity"),
            "match_method": row.get("method"),
            "allocation_confidence": row.get("confidence"),
            "allocation_batch": row.get("batch"),
            "gps_lat": lat,
            "gps_lon": lon,
            "lee_note": lee_note,
            "tags": tags,
            "tags_source": tags_source,
            "source": "allocation_v2",
            "kept": True,
            "match_status": "tied",
        }
        exported.append(out_row)

    with open(OUT_PATH, "w") as f:
        for r in exported:
            f.write(json.dumps(r) + "\n")

    with open(RESIDUE_PATH, "w") as f:
        for r in residue:
            f.write(json.dumps(r) + "\n")

    distinct_job_refs = {r["job_ref"] for r in exported if r["job_ref"]}

    summary = {
        "exported_rows": len(exported),
        "distinct_job_refs": len(distinct_job_refs),
        "residue_rows": len(residue),
        "out_path": str(OUT_PATH),
        "residue_path": str(RESIDUE_PATH),
    }
    print(json.dumps(summary, indent=2))

    if len(exported) != 8488 or len(distinct_job_refs) != 246:
        print(
            f"WARNING: expected 8488 rows / 246 job_refs, got "
            f"{len(exported)} rows / {len(distinct_job_refs)} job_refs. "
            "STOP and report — do not proceed to insert.",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
