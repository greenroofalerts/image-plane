#!/usr/bin/env python3
from __future__ import annotations
"""Build approved few-shot teaching records from exported spine observations."""

import argparse
import hashlib
import json
from pathlib import Path

PHOTO_RECORD_TYPES = {"approved_photo_teaching", "photo_review"}
NO_JOB_WORDS = {"", "unknown", "none", "no job"}


def sha256_of_file(path: Path) -> str:
    """Work out the fingerprint of one real picture file."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def real_job_ref(value) -> str | None:
    """Return the job reference, or nothing when the row does not name a job."""
    text = str(value or "").strip()
    return None if text.lower() in NO_JOB_WORDS else text


def load_excluded_hashes(path: Path) -> set[str]:
    hashes = set()
    for line in path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            value = row.get("sha") or row.get("sha256")
            if value:
                hashes.add(str(value).lower())
    return hashes


def observation_fields(row: dict) -> dict:
    """Accept exported observation fields, including a JSON content field."""
    content = row.get("extracted_fields") or row.get("content") or row.get("data") or {}
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError:
            content = {}
    if not isinstance(content, dict):
        content = {}
    outer = {key: value for key, value in row.items() if value is not None and key != "extracted_fields"}
    return {**content, **outer}


def photo_path_of(row: dict) -> str | None:
    """Take the picture location from the approved row."""
    return row.get("photo_path") or row.get("source_path") or row.get("path")


def validate_photo_reviews(observations: list[dict]) -> list[dict]:
    """Require exactly the forty approved photo-review records."""
    expected = {f"photo-{number:02d}" for number in range(1, 41)}
    found = []
    for raw in observations:
        row = observation_fields(raw)
        source_id = row.get("source_id")
        record_type = row.get("record_type")
        if source_id == "rules" or record_type not in PHOTO_RECORD_TYPES:
            continue
        found.append(row)
    ids = [row.get("source_id") for row in found]
    if len(found) != 40 or set(ids) != expected or len(ids) != len(set(ids)):
        raise ValueError("Expected one complete approved photo record for each source_id photo-01 through photo-40")
    incomplete = [
        row.get("source_id") for row in found
        if not row.get("approved_summary") or not photo_path_of(row)
    ]
    if incomplete:
        raise ValueError("Approved photo records are incomplete: " + ", ".join(sorted(incomplete)))
    return sorted(found, key=lambda row: int(row["source_id"].split("-")[1]))


def build_teaching_records(observations: list[dict], excluded_hashes: set[str]) -> list[dict]:
    """Keep every approved review row and mark unsafe examples ineligible."""
    records = []
    seen_paths = set()
    seen_hashes = set()
    for raw in validate_photo_reviews(observations):
        row = observation_fields(raw)
        source_path = photo_path_of(row)
        photo_file = Path(str(source_path)).expanduser()
        if not photo_file.is_file():
            raise ValueError(
                f"The picture for {row.get('source_id')} is not on this machine: {source_path}"
            )
        source_sha = sha256_of_file(photo_file)
        job_ref = real_job_ref(row.get("job_ref") or row.get("job"))
        path_key = str(photo_file.resolve())
        sha_key = source_sha.lower()
        eligible = (
            job_ref is not None
            and path_key not in seen_paths
            and sha_key not in seen_hashes
            and sha_key not in excluded_hashes
        )
        seen_paths.add(path_key)
        seen_hashes.add(sha_key)
        records.append({
            "teaching_id": f"lee-review-20260801:{row['source_id']}",
            "review_photo_number": int(row["source_id"].split("-")[1]),
            "spine_observation_id": row.get("spine_observation_id") or row.get("id"),
            "job_ref": job_ref,
            "source_path": str(source_path),
            "source_sha256": source_sha,
            "approved_summary": row["approved_summary"],
            "prior_engine_labels": row.get("prior_engine_labels") or row.get("engine_labels") or [],
            "reader_example_eligible": eligible,
            "review_disposition": row.get("review_disposition") or "approved",
        })
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("observations", type=Path, help="Exported spine observations JSON file")
    parser.add_argument("excluded", type=Path, help="Excluded-photo JSONL ledger")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.observations.read_text())
    observations = data.get("observations", data) if isinstance(data, dict) else data
    if not isinstance(observations, list):
        raise SystemExit("The observations file must contain a JSON list.")
    records = build_teaching_records(observations, load_excluded_hashes(args.excluded))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2))
    print(f"Wrote {len(records)} approved teaching records to {args.output}")


if __name__ == "__main__":
    main()
