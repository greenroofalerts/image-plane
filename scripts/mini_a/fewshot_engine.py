#!/usr/bin/env python3
from __future__ import annotations
"""Few-shot photo labeller for the approved Image Plane teaching set."""

import argparse
import base64
import hashlib
import json
import math
import random
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Tuple

CURATED_LABELS = [
    "pregrown sedum", "pregrown wildflower", "plug & seed", "shingle (riverbed & bank)",
    "haybase", "xeroflor", "install", "maintenance visit", "diagnostic inspection",
    "handover", "reactive repair", "survey/quote visit", "skylight", "parapet",
    "valley gutter", "gutter", "fall-arrest", "flashing", "roof deck", "scupper",
    "outlet", "habitat feature", "waterproof membrane", "drainage board", "filter fleece",
    "growing medium", "sedum blanket", "pebble channel", "perforated aluminium",
    "porous pipe", "misting heads", "timer", "gate valve", "moss encroachment",
    "invasive weeds", "sycamore seedlings", "couch grass", "buddleia", "gaps in planting",
    "leaf litter", "calcification", "debris", "one species taking over",
]

ALIAS_MAP = {
    "sedum": "pregrown sedum", "sedum blanket": "sedum blanket", "moss": "moss encroachment",
    "pebble-border": "pebble channel", "pebble_border": "pebble channel",
    "pebble border": "pebble channel", "sycamore": "sycamore seedlings",
    "waterproofing": "waterproof membrane", "epdm": "waterproof membrane",
    "drainage_board": "drainage board", "filter-fleece": "filter fleece",
    "aluminium_separator": "perforated aluminium", "bare-areas": "gaps in planting",
    "bare areas": "gaps in planting", "feed-in-spring": None, "drip_edge_finish": None,
    "drip-over-edge": None, "anti-shear": None,
}
META_TAGS = {
    "best-practice", "xny", "how_not_to_example", "needs-lee", "fault", "non-roof",
    "revival", "before_shot", "after_shot", "plant_id_wanted", "moss_id_wanted",
    "leak-candidate", "construction", "irrigation",
}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp"}
DEFAULT_BASE = Path("/Users/macminia/image-plane")
FIXED_TEST_SEED = 20260801


class RunLimitError(ValueError):
    """Raised when a bounded run asks for too many photos."""


def sha256_of(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def file_digest(path: Path) -> str:
    return sha256_of(path) if path.exists() else "unavailable"


def photo_to_jpg_b64(path: str) -> str:
    """Convert one photo to JPEG for the local reader."""
    temporary = "/tmp/_fs_e_tmp.jpg"
    try:
        subprocess.run(
            ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85", path, "--out", temporary],
            check=True, capture_output=True, timeout=120,
        )
        return base64.b64encode(Path(temporary).read_bytes()).decode()
    except subprocess.CalledProcessError as error:
        raise RuntimeError("Photo conversion failed") from error


def label_photo(path: str, label_list_json: str, examples_text: str, model: str = "qwen3-vl") -> List[str]:
    """Ask the local photo reader to select curated labels."""
    prompt = (
        "You are labelling a green-roof survey photo in the roof surveyor's own words.\n"
        f"Approved examples from this job only:\n{examples_text}\n\n"
        "Now label this photo. Select all matching labels from this list. "
        "Reply only with a JSON array of labels.\n" + label_list_json
    )
    body = json.dumps({
        "model": model, "prompt": prompt, "images": [photo_to_jpg_b64(path)], "stream": False,
        "options": {"num_ctx": 4096, "temperature": 0.1},
    }).encode()
    request = urllib.request.Request(
        "http://localhost:11434/api/generate", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            text = json.loads(response.read()).get("response", "").strip()
    except urllib.error.URLError as error:
        raise RuntimeError("The local photo reader is unavailable") from error
    match = re.search(r"\[.*\]", text, re.S)
    try:
        return json.loads(match.group(0)) if match else []
    except json.JSONDecodeError:
        return []


def load_jsonl(path: Path) -> List[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_knowledge_notes(path: str | Path) -> List[dict]:
    return load_jsonl(Path(path))


def load_photo_ledger(path: str | Path) -> Dict[str, dict]:
    return {row["path"]: row for row in load_jsonl(Path(path)) if row.get("path")}


def load_excluded_shas(path: str | Path) -> Set[str]:
    return {
        str(row.get("sha") or row.get("sha256")).lower()
        for row in load_jsonl(Path(path))
        if row.get("sha") or row.get("sha256")
    }


def load_approved_teaching(path: str | Path) -> List[dict]:
    records = json.loads(Path(path).read_text())
    if not isinstance(records, list):
        raise ValueError("The teaching file must contain a JSON list")
    return records


def row_job(row: dict) -> str | None:
    return row.get("job_ref") or row.get("job")


# --- The ID ladder, as recorded in ~/.claude/skills/green-roof-image-plane/SKILL.md ---
# Riding law: never one field on its own. Lee's own answer is the one exemption.
# Ambiguous goes to Lee and is never picked automatically.
# Nothing here works out a job for itself. It reads the recorded photo register
# (lane 7) and the recorded located-job map (lane 2). See the ledger, 1 Aug 2026.

NO_JOB_WORDS = {"", "unknown", "none", "n/a", "-"}
LEE_ANSWER_METHODS = {"lee_cluster_answer", "lee_verdict", "lee_answer"}
LEE_ANSWER_BANDS = {"lee_confirmed", "lee"}
LOCATION_LIMIT_M = 150.0

# Lane 1 is "the exact job reference (registry AND ALIASES)". This is the alias
# half. A job typed two ways is ONE job, and the wrong spelling must resolve to
# the right one wherever a job reference is read.
#
# Lee ruled on 1 August 2026, verbatim: "1588 is a known mistype that has worked
# its way into even invoices - just combine them". So 1588-26 and 1858-26 are not
# two sites 18 metres apart. They are one job typed two ways, and the wrong one
# reached Xero as well as the photo records.
#
# STANDING SHAPE, worth keeping: when two references differ only by transposed
# digits and sit metres apart, suspect a mistype before you suspect two sites,
# and put it to Lee, who knows his own typing history.
JOB_REF_ALIASES = {
    "1588-26": "1858-26",
}


def named_job(value: object) -> str | None:
    """Return a real job reference, or None when the field names no job.

    Lane 1 aliases are applied here, so every reader of a job reference gets the
    settled spelling and no caller has to remember the mistake.
    """
    text = str(value or "").strip()
    if text.lower() in NO_JOB_WORDS:
        return None
    return JOB_REF_ALIASES.get(text.lower(), text)


def lane_routes(method: str) -> set[str]:
    """The lanes a recorded method names, for example lane2_gra_sites+lane4_xero.

    Lee ruled on 1 August 2026, verbatim: "five routes doesnt need extra". A
    register row whose own method names two or more lanes has already satisfied
    the never-one-field law inside that row. Asking the position lane to confirm
    it again is extra work for nothing.
    """
    return set(re.findall(r"lane\d+", str(method or "").lower()))


def load_photo_register(path: str | Path) -> Dict[str, dict]:
    """Lane 7 — the recorded photo register. Never recomputed here."""
    register = {}
    for row in load_jsonl(Path(path)):
        if row.get("path"):
            register[str(row["path"])] = row
    return register


def load_located_jobs(path: str | Path) -> Dict[str, dict]:
    """Lane 2 — the recorded located-job map. Never re-geocoded here.

    Lane 1 aliases are applied to the keys, so a job typed two ways cannot look
    like two sites standing metres apart. Where both spellings are present, the
    settled spelling is kept and the mistype is dropped.
    """
    data = json.loads(Path(path).read_text())
    located: Dict[str, dict] = {}
    for ref, row in data.items():
        if row.get("lat") is None:
            continue
        settled = named_job(ref)
        if settled is None:
            continue
        if settled in located and ref.lower() in JOB_REF_ALIASES:
            continue
        located[settled] = row
    return located


def load_photo_points(path: str | Path) -> Dict[str, Tuple[float, float]]:
    """Recorded picture positions. Never re-read from the picture files here."""
    points = {}
    for row in load_jsonl(Path(path)):
        if row.get("path") and row.get("lat") is not None and row.get("lon") is not None:
            points[str(row["path"])] = (float(row["lat"]), float(row["lon"]))
    return points


def metres_apart(first: Tuple[float, float], second: Tuple[float, float]) -> float:
    radius = 6371000.0
    lat1, lat2 = math.radians(first[0]), math.radians(second[0])
    half_lat = (lat2 - lat1) / 2
    half_lon = math.radians(second[1] - first[1]) / 2
    inner = math.sin(half_lat) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(half_lon) ** 2
    return 2 * radius * math.asin(math.sqrt(inner))


def location_lane(point: Tuple[float, float] | None, located_jobs: Dict[str, dict]) -> str | None:
    """Lane 2 — the nearest located job inside the recorded limit, or nothing."""
    if not point:
        return None
    nearest, shortest = None, None
    for ref, row in located_jobs.items():
        distance = metres_apart(point, (float(row["lat"]), float(row["lon"])))
        if shortest is None or distance < shortest:
            nearest, shortest = ref, distance
    if shortest is None or shortest > LOCATION_LIMIT_M:
        return None
    # Lane 1 aliases apply here too. A job typed two ways is one job, so a
    # mistype in the located map can never look like a second site next door.
    return named_job(nearest)


def is_location_method(method: str) -> bool:
    """A register row found by position sits in lane 2, not in a second lane."""
    return str(method or "").lower().startswith("gps")


def resolve_job(row: dict, register: Dict[str, dict], points: Dict[str, Tuple[float, float]],
                located_jobs: Dict[str, dict], base: Path = DEFAULT_BASE) -> dict:
    """Work out which job a picture belongs to, by the recorded lanes only.

    Returns the job, the lanes that found it, and a plain reason when it refuses.
    """
    given = named_job(row_job(row))
    if given:
        return {"job_ref": given, "method": "lee_answer", "reason": None}

    path = row.get("source_path") or row.get("path")
    absolute = row.get("absolute_path") or (str(normalise_path(path, base)) if path else None)
    entry = register.get(str(absolute or "")) or register.get(str(path or ""))
    point = points.get(str(absolute or "")) or points.get(str(path or ""))
    by_location = location_lane(point, located_jobs)

    if not entry:
        if by_location:
            return {"job_ref": None, "method": None,
                    "reason": "Only the position lane found a job. One lane is not enough."}
        return {"job_ref": None, "method": None, "reason": "No recorded lane found a job."}

    method = str(entry.get("method") or "")
    band = str(entry.get("confidence") or "").lower()
    registered = named_job(entry.get("job_ref"))
    if not registered:
        return {"job_ref": None, "method": None, "reason": "The photo register names no job."}

    if method.lower() in LEE_ANSWER_METHODS or band in LEE_ANSWER_BANDS:
        return {"job_ref": registered, "method": "lee_answer", "reason": None}

    if by_location and by_location != registered:
        return {"job_ref": None, "method": None,
                "reason": f"The lanes disagree: the register says {registered}, "
                          f"the position says {by_location}. This one goes to Lee."}

    # Lee, 1 August 2026: "five routes doesnt need extra". When the register row
    # already names two or more lanes, the never-one-field law is satisfied
    # inside that row. Neither the band test nor the position test may refuse it.
    routes = lane_routes(method)
    if len(routes) >= 2:
        return {"job_ref": registered,
                "method": "+".join(sorted(routes)),
                "reason": None}

    if band != "high":
        return {"job_ref": None, "method": None,
                "reason": f"The photo register is only {band or 'unbanded'} sure."}

    if is_location_method(method):
        return {"job_ref": None, "method": None,
                "reason": "The register found this by position, so position cannot confirm it. "
                          "One lane is not enough."}

    if not by_location:
        return {"job_ref": None, "method": None,
                "reason": f"Only the photo register ({method}) found a job. One lane is not enough."}

    return {"job_ref": registered, "method": "lane7_photo_register+lane2_gra_sites", "reason": None}


def load_ladder_sources(base: Path = DEFAULT_BASE) -> dict:
    """Load the three recorded sources. Names every source that is absent."""
    files = {
        "register": (base / "grind" / "allocation_v2.jsonl", load_photo_register),
        "points": (base / "geolocations.jsonl", load_photo_points),
        "located_jobs": (base / "grind" / "job_coords.json", load_located_jobs),
    }
    sources = {}
    absent = []
    for name, (path, loader) in files.items():
        if path.exists():
            sources[name] = loader(path)
        else:
            sources[name] = {}
            absent.append(str(path))
    sources["source_counts"] = {name: len(sources[name]) for name in files}
    sources["absent_sources"] = absent
    return sources


def normalise_path(path: str | None, base: Path = DEFAULT_BASE) -> Path | None:
    """Resolve a stored path against the operational photo base."""
    if not path:
        return None
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve()


def resolve_examples(target: dict, teaching: List[dict], base: Path = DEFAULT_BASE,
                     sources: dict | None = None) -> Tuple[List[dict], dict]:
    """Resolve the target job by the recorded lanes, then select approved examples.

    Returns the examples and the resolution, so every result row can say which
    lanes found the job and, when there is no example, why.
    """
    sources = sources or {}
    register = sources.get("register") or {}
    points = sources.get("points") or {}
    located_jobs = sources.get("located_jobs") or {}
    resolution = resolve_job(target, register, points, located_jobs, base)
    target_job = resolution["job_ref"]
    if not target_job:
        return [], resolution

    target_path = normalise_path(target.get("source_path") or target.get("path"), base)
    target_sha = str(target.get("source_sha256") or target.get("sha256") or "").lower()
    selected = []
    seen_paths = set()
    seen_hashes = set()
    for record in teaching:
        review_path = normalise_path(record.get("source_path"), base)
        review_sha = str(record.get("source_sha256") or "").lower()
        if not record.get("reader_example_eligible"):
            continue
        if resolve_job(record, register, points, located_jobs, base)["job_ref"] != target_job:
            continue
        if review_path == target_path or review_sha == target_sha:
            continue
        if review_path in seen_paths or review_sha in seen_hashes:
            continue
        seen_paths.add(review_path)
        seen_hashes.add(review_sha)
        selected.append(record)
        if len(selected) == 3:
            break
    if not selected:
        resolution = {**resolution,
                      "reason": f"The job is {target_job}, but no approved example belongs to it."}
    return selected, resolution


def select_approved_examples(target: dict, teaching: List[dict], base: Path = DEFAULT_BASE,
                             sources: dict | None = None) -> List[dict]:
    """Select at most three approved examples for the target's resolved job."""
    return resolve_examples(target, teaching, base, sources)[0]


def format_examples(examples: List[dict]) -> str:
    if not examples:
        return "No approved examples are available for this job."
    return "\n".join(
        f'Example {row["teaching_id"]}: "{row.get("approved_summary", "")}"'
        for row in examples
    )


def is_photo(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in PHOTO_EXTENSIONS


def photo_files_in_folder(folder: Path) -> List[Path]:
    return sorted(path for path in folder.rglob("*") if is_photo(path))


def canonical_note(note: dict) -> str:
    """Make one stable representation of a source note."""
    return json.dumps(note, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_case_rows(notes: List[dict], base: Path) -> List[dict]:
    """Give each source note a stable identifier, independent of input order."""
    ordered = sorted((canonical_note(note), note) for note in notes)
    duplicates = {}
    rows = []
    for canonical, note in ordered:
        digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
        occurrence = duplicates.get(canonical, 0) + 1
        duplicates[canonical] = occurrence
        suffix = "" if occurrence == 1 else f"-{occurrence:02d}"
        relative = note.get("path") or ""
        rows.append({
            "case_id": f"note-{digest}{suffix}",
            "source_id": str(note.get("source_id") or note.get("id") or ""),
            "source_path": relative, "absolute_path": str(base / relative),
            "job_ref": row_job(note), "lee_note": note.get("note", ""),
            "lee_tags": note.get("tags", []),
        })
    return rows


def select_unseen_notes(notes: List[dict], base: Path, teaching: List[dict], excluded: Set[str], requested: int, seed: int) -> List[dict]:
    """Select exactly requested unseen notes, or raise before any model call."""
    review_paths = {normalise_path(row.get("source_path"), base) for row in teaching if row.get("source_path")}
    review_shas = {str(row.get("source_sha256")).lower() for row in teaching if row.get("source_sha256")}
    source_counts = {}
    for note in notes:
        if note.get("path"):
            source_counts[note["path"]] = source_counts.get(note["path"], 0) + 1
    candidates = []
    for row in build_case_rows(notes, base):
        path = Path(row["absolute_path"])
        if not row["lee_tags"] or not row["source_path"] or source_counts[row["source_path"]] != 1:
            continue
        if normalise_path(row["source_path"], base) in review_paths or not path.exists() or not is_photo(path):
            continue
        sha = sha256_of(path)
        if sha in excluded or sha in review_shas:
            continue
        row["source_sha256"] = sha
        candidates.append(row)
    random.Random(seed).shuffle(candidates)
    if len(candidates) < requested:
        raise RunLimitError(f"Only {len(candidates)} eligible unseen photos exist; {requested} are required")
    return candidates[:requested]


def label_candidate(path: Path, excluded: Set[str], examples: List[dict], label_list_json: str, *, labeler=label_photo) -> dict:
    """Apply the hash guard before conversion and model use."""
    sha = sha256_of(path)
    if sha.lower() in excluded:
        return {"source_sha256": sha, "skip_reason": "excluded", "engine_labels": []}
    labels = labeler(str(path), label_list_json, format_examples(examples))
    return {"source_sha256": sha, "skip_reason": None, "engine_labels": labels}


def new_run_folder(runs_root: Path, prefix: str = "fewshot") -> Path:
    runs_root.mkdir(parents=True, exist_ok=True)
    run_id = f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    folder = runs_root / run_id
    suffix = 1
    while folder.exists():
        folder = runs_root / f"{run_id}-{suffix}"
        suffix += 1
    folder.mkdir()
    return folder


def write_run(run: Path, manifest: dict, results: List[dict], baseline: dict | None = None) -> None:
    (run / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (run / "heldout_results.json").write_text(json.dumps({"run_id": manifest["run_id"], "results": results}, indent=2))
    (run / "baseline_keyword.json").write_text(json.dumps(baseline or {"run_id": manifest["run_id"], "results": []}, indent=2))


def run_folder(folder: Path, runs_root: Path, excluded: Set[str], teaching: List[dict], *, labeler=label_photo, job_ref: str | None = None, base: Path = DEFAULT_BASE, sources: dict | None = None) -> Path:
    """Label no more than ten local photo files in stable order."""
    sources = load_ladder_sources(base) if sources is None else sources
    paths = photo_files_in_folder(folder)
    eligible = []
    skipped = []
    for path in paths:
        sha = sha256_of(path)
        if sha.lower() in excluded:
            skipped.append({"source_path": str(path), "source_sha256": sha, "skip_reason": "excluded", "engine_labels": []})
        else:
            eligible.append((path, sha))
    if len(eligible) > 10:
        raise RunLimitError("Folder mode refuses more than 10 eligible photos")
    run = new_run_folder(runs_root, "folder")
    results = list(skipped)
    for index, (path, sha) in enumerate(eligible, 1):
        target = {"job_ref": job_ref, "source_path": str(path), "source_sha256": sha}
        examples, resolution = resolve_examples(target, teaching, base, sources)
        result = label_candidate(path, excluded, examples, json.dumps(CURATED_LABELS), labeler=labeler)
        results.append({
            "case_id": f"folder:{index:03d}", "source_path": str(path), "source_sha256": sha,
            "job_ref": resolution["job_ref"], "job_method": resolution["method"],
            "no_example_reason": resolution["reason"] if not examples else None,
            "example_ids": [row["teaching_id"] for row in examples],
            "lee_note": "", "lee_tags": [], **result,
        })
    manifest = {"run_id": run.name, "mode": "folder", "requested_count": len(eligible), "selected_case_ids": [row.get("case_id") for row in results if row.get("case_id")], "ladder_sources": sources.get("source_counts", {}), "absent_sources": sources.get("absent_sources", [])}
    write_run(run, manifest, results)
    return run


def run_test_small(base: Path, teaching_path: Path, excluded_path: Path, notes_path: Path, ledger_path: Path, *, labeler=label_photo, sources: dict | None = None) -> Path:
    teaching = load_approved_teaching(teaching_path)
    excluded = load_excluded_shas(excluded_path)
    sources = load_ladder_sources(base) if sources is None else sources
    selected = select_unseen_notes(load_knowledge_notes(notes_path), base, teaching, excluded, 10, FIXED_TEST_SEED)
    run = new_run_folder(base / "grind" / "fewshot_runs")
    results = []
    for row in selected:
        examples, resolution = resolve_examples(row, teaching, base, sources)
        output = label_candidate(Path(row["absolute_path"]), excluded, examples, json.dumps(CURATED_LABELS), labeler=labeler)
        results.append({
            **row, "job_ref": resolution["job_ref"], "job_method": resolution["method"],
            "no_example_reason": resolution["reason"] if not examples else None,
            "example_ids": [item["teaching_id"] for item in examples], **output,
        })
    baseline = {"run_id": run.name, **run_keyword_baseline(results, load_photo_ledger(ledger_path))}
    manifest = {
        "run_id": run.name, "mode": "test-small", "seed": FIXED_TEST_SEED, "requested_count": 10,
        "selected_case_ids": [row["case_id"] for row in results], "teaching_file_id": teaching_path.name,
        "input_file_hashes": {"notes": file_digest(notes_path), "teaching": file_digest(teaching_path), "ledger": file_digest(ledger_path)},
        "exclusion_file_hash": file_digest(excluded_path), "withheld": "Approved-review photos and excluded photos were withheld.",
        "ladder_sources": sources.get("source_counts", {}), "absent_sources": sources.get("absent_sources", []),
    }
    write_run(run, manifest, results, baseline)
    return run


def canonicalise_tag(tag: str) -> str:
    mapped = ALIAS_MAP.get(tag.lower().strip(), tag.lower().strip())
    return mapped.lower() if mapped else tag.lower().strip()


def split_tags(tags: List[str]) -> Tuple[Set[str], Set[str], Set[str]]:
    meta, mapped, unmapped = set(), set(), set()
    for tag in tags:
        lowered = tag.lower().strip()
        if lowered in META_TAGS:
            meta.add(lowered)
        elif canonicalise_tag(tag) in CURATED_LABELS:
            mapped.add(canonicalise_tag(tag))
        else:
            unmapped.add(canonicalise_tag(tag))
    return meta, mapped, unmapped


def score_predictions(engine_labels: List[str], truth_tags: List[str]) -> Dict:
    truth_meta, truth_mapped, truth_unmapped = split_tags(truth_tags)
    predicted = {canonicalise_tag(label) for label in engine_labels}
    hits = len(predicted & truth_mapped)
    truth_raw, predicted_raw = {tag.lower() for tag in truth_tags}, {tag.lower() for tag in engine_labels}
    strict_hits = len(truth_raw & predicted_raw)
    return {
        "recall": hits / len(truth_mapped) if truth_mapped else 0.0,
        "precision": hits / len(predicted) if predicted else 0.0,
        "strict_recall": strict_hits / len(truth_raw) if truth_raw else 0.0,
        "strict_precision": strict_hits / len(predicted_raw) if predicted_raw else 0.0,
        "hits": hits, "strict_hits": strict_hits, "meta_count": len(truth_meta),
        "mapped_count": len(truth_mapped), "unmapped_count": len(truth_unmapped),
    }


def run_keyword_baseline(test_results: List[dict], ledger: Dict[str, dict]) -> Dict:
    results = []
    for row in test_results:
        source = row.get("source_path") or row.get("path")
        description = ledger.get(source, {}).get("response", "").lower()
        labels = [label for label in CURATED_LABELS if label in description]
        results.append({"case_id": row.get("case_id"), "engine_labels": labels, **score_predictions(labels, row.get("lee_tags", []))})
    return {"n_tested": len(results), "results": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--test-small", action="store_true")
    group.add_argument("--folder")
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--job-ref")
    args = parser.parse_args()
    base = args.base
    teaching = base / "grind" / "fewshot_approved_teaching_20260801.json"
    excluded = base / "grind" / "excluded_moves_20260728.jsonl"
    if args.test_small:
        run = run_test_small(base, teaching, excluded, base / "knowledge_notes.jsonl", base / "photo_ledger_merged.jsonl")
    else:
        folder = Path(args.folder)
        if not folder.is_absolute():
            folder = base / folder
        run = run_folder(folder, base / "grind" / "fewshot_runs", load_excluded_shas(excluded), load_approved_teaching(teaching), job_ref=args.job_ref, base=base)
    print(f"Run files written to {run}")


if __name__ == "__main__":
    main()
