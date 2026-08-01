#!/usr/bin/env python3
"""Build the picture hashes for every photo Lee has already ruled out.

This runs ON MINI A. It reads the recorded exclusion list and writes a NEW
file beside it. It never writes to the exclusion list and it deletes nothing.

Each output row is one excluded picture:

    {"sha256": ..., "name": ..., "size": ..., "phash": [upright, 90, 180, 270]}

Four hashes are stored for each excluded picture, one for each quarter turn.
An arriving picture then needs only one hash of its own. That is the same
answer as turning the arriving picture, and it is three times less work at
intake. Measured 1 Aug 2026: a plain compare caught 0 of 40 rotated pairs and
a rotation-aware compare caught 40 of 40 (window finding ref 60).

The hashing method is NOT copied here. It is imported from the exporter,
scripts/mini_b/export_icloud_photos.py, which the runner already places on
this machine. One copy of the method means it cannot drift.

A file that cannot be read is written to a second file with the reason. It is
never dropped in silence.

Run it again to carry on where it stopped. Rows already written are skipped.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

DEFAULT_INPUT = Path.home() / "image-plane" / "grind" / "excluded_moves_20260728.jsonl"
DEFAULT_OUTPUT = Path.home() / "image-plane" / "grind" / "excluded_picture_hashes_20260801.jsonl"


def load_exporter():
    """Import the exporter so the hashing method has exactly one copy."""
    module_path = Path(__file__).resolve().parent.parent / "mini_b" / "export_icloud_photos.py"
    if not module_path.exists():
        raise SystemExit(
            "Cannot find the exporter at {0}.\n"
            "Copy the whole scripts folder to this machine, "
            "so scripts/mini_a and scripts/mini_b sit side by side.".format(module_path)
        )
    spec = importlib.util.spec_from_file_location("icloud_intake", module_path)
    if spec is None or spec.loader is None:
        raise SystemExit("Cannot load the exporter at {0}".format(module_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def excluded_rows(path):
    """Read the recorded exclusion list. Read only. Never written to."""
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                rows.append({"line": line_number, "error": "Line is not valid JSON"})
                continue
            data["line"] = line_number
            rows.append(data)
    return rows


def picture_path(row):
    """Return where the excluded file lives now, or None."""
    for key in ("to", "from", "path"):
        value = row.get(key)
        if isinstance(value, str) and value and os.path.exists(value):
            return Path(value)
    return None


def done_hashes(path):
    """Return the SHA-256 values already written, so a re-run carries on."""
    values = set()
    if not path.exists():
        return values
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            value = data.get("sha256")
            if isinstance(value, str):
                values.add(value)
    return values


def append_line(path, record):
    """Append one row and save it to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def build(input_path, output_path, limit=None, progress_every=100):
    """Write one hash row for every excluded picture that can be read."""
    intake = load_exporter()
    unreadable_path = output_path.with_name(output_path.stem + "-unreadable" + output_path.suffix)
    rows = excluded_rows(input_path)
    already = done_hashes(output_path)
    result = {
        "rows": len(rows),
        "already_done": 0,
        "hashed": 0,
        "unreadable": 0,
        "not_a_picture": 0,
        "missing_file": 0,
        "bad_row": 0,
    }
    seen = set()
    for index, row in enumerate(rows, start=1):
        if limit is not None and result["hashed"] >= limit:
            break
        line_number = row.get("line")
        sha = row.get("sha256")
        if not isinstance(sha, str) or len(sha) != 64:
            result["bad_row"] += 1
            append_line(unreadable_path, {"line": line_number, "reason": "No SHA-256 value on the row"})
            continue
        if sha in already or sha in seen:
            result["already_done"] += 1
            continue
        path = picture_path(row)
        if path is None:
            result["missing_file"] += 1
            append_line(
                unreadable_path,
                {"line": line_number, "sha256": sha, "reason": "File is not at any recorded path"},
            )
            continue
        if path.suffix.lower() not in intake.IMAGE_EXTENSIONS:
            result["not_a_picture"] += 1
            append_line(
                unreadable_path,
                {"line": line_number, "sha256": sha, "path": str(path), "reason": "Not a picture file"},
            )
            continue
        try:
            size = path.stat().st_size
        except OSError as error:
            result["unreadable"] += 1
            append_line(
                unreadable_path,
                {"line": line_number, "sha256": sha, "path": str(path), "reason": "Cannot read the size: {0}".format(error)},
            )
            continue
        values = intake.picture_hashes(path, rotations=True)
        if not values:
            result["unreadable"] += 1
            append_line(
                unreadable_path,
                {"line": line_number, "sha256": sha, "path": str(path), "reason": "Cannot read the picture"},
            )
            continue
        append_line(output_path, {"sha256": sha, "name": path.name, "size": size, "phash": values})
        seen.add(sha)
        result["hashed"] += 1
        if progress_every and result["hashed"] % progress_every == 0:
            print("{0} hashed of {1} rows read".format(result["hashed"], index), file=sys.stderr, flush=True)
    return result


def build_parser():
    parser = argparse.ArgumentParser(description="Hash every picture Lee has already ruled out.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, help="Stop after this many new pictures. For a smoke test.")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not args.input.exists():
        raise SystemExit("Cannot find the exclusion list at {0}".format(args.input))
    if args.output.resolve() == args.input.resolve():
        raise SystemExit("The output file must never be the exclusion list.")
    result = build(args.input, args.output, limit=args.limit)
    print(json.dumps(result, sort_keys=True))
    print("Counted by: rows read from {0}".format(args.input))
    print("Written to: {0}".format(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
