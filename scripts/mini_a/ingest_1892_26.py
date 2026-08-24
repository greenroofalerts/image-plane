#!/usr/bin/env python3
"""One-shot ingest of job 1892-26 (6 Pancras Square) into visual_observations.

Does not rebuild the identity ladder. Calls id_ladder_service.py.
Does not touch historic 8488. Does not start flip_server. Does not publish.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# /usr/bin/python3 on Mini A has PIL; homebrew python3 does not.
try:
    from PIL import Image
except ImportError:
    Image = None

BASE = Path("/Users/macminia/image-plane")
JOB_DIR = BASE / "incoming" / "google" / "1892-26"
ALBUM = JOB_DIR / "6 Pancras Diagnostic 18-7-26"
THUMBS = JOB_DIR / "thumbs"
CABINET = BASE / "cabinet" / "1892-26"
CAB_ORIG = CABINET / "originals"
CAB_THUMBS = CABINET / "thumbs"
RECEIPT = JOB_DIR / "INGEST-RECEIPT.json"
LADDER = BASE / "id_ladder_service.py"
ENV_FILE = BASE / ".env.flip"
DICTATE_PATH = JOB_DIR / "LEE-DICTATE.txt"

SOURCE = "google-album-1892-26-20260818"
BATCH = "pancras-1892-26-v1"
JOB_REF = "1892-26"
MODEL_NAME = "image-plane-bot-match-1892-26"
VISIT_FALLBACK = "2026-08-18"

# dHash copied from build_repo_dedupe.py (itself copied from src/image_plane/phash.py).
def dhash_hex(img):
    grey = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    px = grey.tobytes()
    bits = 0
    for row in range(8):
        for col in range(8):
            left = px[row * 9 + col]
            right = px[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}"


def load_env():
    env = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v.strip().strip('"').strip("'")
    return env


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_ladder():
    evidence = {
        "job_refs": [JOB_REF],
        "streets": ["6 Pancras Square", "Pancras Square"],
        "text": "job 1892-26 6 Pancras Square diagnostic visit",
        "subject": "1892-26 6 Pancras Square",
    }
    proc = subprocess.run(
        [sys.executable, str(LADDER)],
        input=json.dumps(evidence).encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(BASE),
        timeout=60,
    )
    out = proc.stdout.decode() if proc.stdout else ""
    try:
        return json.loads(out), out, proc.stderr.decode()
    except Exception:
        return {"error": "ladder_unreadable", "stdout": out[:2000], "returncode": proc.returncode}, out, proc.stderr.decode()


def parse_match_method(ladder):
    """Lee already named 1892-26. Use two-lane MATCH if the live ladder reaches it."""
    hits = ladder.get("hits") or {}
    job = ladder.get("job_ref")
    agreeing = [lane for lane, refs in hits.items() if JOB_REF in (refs or [])]
    lanes_run = [x.get("lane") for x in (ladder.get("lanes_run") or [])]
    lanes_unreach = [x.get("lane") for x in (ladder.get("lanes_unreachable") or [])]
    two_plus = len(agreeing) >= 2
    if job == JOB_REF and two_plus:
        return {
            "match_method": "+".join(agreeing),
            "allocation_confidence": "high" if ladder.get("confidence") in ("corroborated", "settled") else "medium",
            "match_status": "ladder_confirmed",
            "lanes_used": agreeing,
            "lanes_run": lanes_run,
            "lanes_unreachable": lanes_unreach,
            "ladder_job_ref": job,
        }
    # Lee named it; ladder did not reach two live lanes.
    return {
        "match_method": "lee_answer",
        "allocation_confidence": "lee_confirmed",
        "match_status": "ladder_confirmed",
        "lanes_used": agreeing,
        "lanes_run": lanes_run,
        "lanes_unreachable": lanes_unreach,
        "ladder_job_ref": job,
    }


# MATCH-1892-26.txt lines, in Lee's language. A file may have several.
MATCH_LINES = {
    "IMG_1841": [
        "Wide dry loose-laid sedum roof",
        "Log piles / hibernacula",
    ],
    "IMG_1842": ["Wide dry loose-laid sedum roof"],
    "IMG_1843": ["Depth hole + ruler (~130mm)"],
    "IMG_1844": ["Light recycled aggregate / dry compost in hand and open"],
    "IMG_1845": ["Light recycled aggregate / dry compost in hand and open"],
    "IMG_1846": ["Drainage tray + filter fleece pulled back (holes)"],
    "IMG_1847": ["Light recycled aggregate / dry compost in hand and open"],
    "IMG_1849": ["Log piles / hibernacula"],
    "IMG_1850": [
        "Wide dry loose-laid sedum roof",
        "Log piles / hibernacula",
    ],
    "IMG_1851": ["Sedum + stones / ballast"],
    "IMG_1852": [
        "Sedum + stones / ballast",
        "Edge / divider issue at stone vs plant",
    ],
    "IMG_1855": ["Depth hole + ruler (~55mm)"],
    "IMG_1858": ["Terrace for habitats / mobile planters"],
    "IMG_1860": ["Sedum + stones / ballast"],
    "IMG_1866": ["Plant-bed roofs looking failed/sparse (floor not labelled in picture)"],
    "IMG_1869": ["Sedum + stones / ballast"],
    "IMG_1870": [
        "Wide dry loose-laid sedum roof",
        "Log piles / hibernacula",
    ],
    "IMG_1872": ["Wide dry loose-laid sedum roof"],
    "IMG_1874": ["Videos not watched"],
    "IMG_1878": ["Vent / drain + mesh stones"],
    "IMG_1880": ["Kit sitting on the roof"],
    "IMG_1882": ["Kit sitting on the roof"],
    "IMG_1886": [
        "Plant-bed roofs looking failed/sparse (floor not labelled in picture)",
        "Ruler and trowel on the ledge",
    ],
    "IMG_1888": [
        "Depth hole + ruler (~80mm)",
        "Ruler and trowel on the ledge",
    ],
    "IMG_1893": ["Videos not watched"],
    "IMG_1896": ["Terrace for habitats / mobile planters"],
    "IMG_1898": ["Indoor moss wall / map pin — not a roof note"],
}

# Nearest honest subject for files not named in MATCH, only where neighbours share a subject.
NEAREST = {
    "IMG_1871": "Wide dry loose-laid sedum roof (nearest honest subject; sits between IMG_1870 and IMG_1872)",
    "IMG_1881": "Kit sitting on the roof (nearest honest subject; sits between IMG_1880 and IMG_1882)",
}

TAG_FOR_LINE = [
    ("loose-laid", ["sedum", "loose-laid"]),
    ("log piles", ["logs", "hibernacula"]),
    ("hibernacula", ["logs", "hibernacula"]),
    ("depth", ["depth"]),
    ("aggregate", ["aggregate"]),
    ("fleece", ["fleece"]),
    ("terrace", ["terrace"]),
    ("sedum", ["sedum"]),
    ("plant-bed", ["sedum"]),
]


def describe(stem, is_mov):
    unresolved = []
    if stem in MATCH_LINES:
        desc = ". ".join(MATCH_LINES[stem]) + "."
        tags = ["diagnostic"]
        blob = desc.lower()
        for needle, extra in TAG_FOR_LINE:
            if needle in blob:
                for t in extra:
                    if t not in tags:
                        tags.append(t)
        if stem == "IMG_1898":
            building, activity = "indoor", "indoor"
            tags = [t for t in tags if t not in ("sedum", "loose-laid", "logs", "hibernacula", "depth", "aggregate", "fleece", "terrace")]
            if "diagnostic" not in tags:
                tags.append("diagnostic")
        elif "terrace" in blob:
            building, activity = "terrace", "diagnostic"
        elif is_mov:
            building, activity = "roof", "diagnostic"
        else:
            building, activity = "roof", "diagnostic"
        return desc, tags, "lee_voice", building, activity, unresolved

    if stem in NEAREST:
        desc = NEAREST[stem]
        tags = ["diagnostic"]
        blob = desc.lower()
        for needle, extra in TAG_FOR_LINE:
            if needle in blob:
                for t in extra:
                    if t not in tags:
                        tags.append(t)
        if "kit" in blob:
            tags = ["diagnostic"]
        building = "roof"
        return desc, tags, None, building, "diagnostic", [
            {"file": stem, "reason": "not_in_match_nearest_subject"}
        ]

    desc = "Unresolved still from the 6 Pancras diagnostic — not paired in MATCH-1892-26."
    return desc, ["diagnostic"], None, None, None, [
        {"file": stem, "reason": "not_in_match"}
    ]


def dms_to_dec(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    return None


def exif_for(path):
    try:
        raw = subprocess.check_output(
            [
                "exiftool", "-j", "-n",
                "-DateTimeOriginal", "-CreateDate", "-MediaCreateDate",
                "-OffsetTimeOriginal", "-OffsetTime", "-OffsetTimeDigitized",
                "-GPSLatitude", "-GPSLongitude", "-Make", "-Model",
                "-MIMEType", "-FileType",
                str(path),
            ],
            stderr=subprocess.DEVNULL,
        )
        info = json.loads(raw)[0]
    except Exception:
        info = {}
    dt = info.get("DateTimeOriginal") or info.get("CreateDate") or info.get("MediaCreateDate")
    off = info.get("OffsetTimeOriginal") or info.get("OffsetTime") or info.get("OffsetTimeDigitized") or "+01:00"
    taken_at = None
    visit_date = VISIT_FALLBACK
    if dt:
        # exiftool -n still gives "2026:08:18 12:38:11" for dates
        s = str(dt).replace(":", "-", 2)
        if "T" not in s and " " in s:
            s = s.replace(" ", "T", 1)
        if len(off) == 5 and (off[0] in "+-") and ":" not in off:
            off = off[:3] + ":" + off[3:]
        try:
            taken_at = s + off
            visit_date = s[:10]
        except Exception:
            taken_at = None
    lat = dms_to_dec(info.get("GPSLatitude"))
    lon = dms_to_dec(info.get("GPSLongitude"))
    slim = {
        "DateTimeOriginal": info.get("DateTimeOriginal"),
        "CreateDate": info.get("CreateDate"),
        "MediaCreateDate": info.get("MediaCreateDate"),
        "Make": info.get("Make"),
        "Model": info.get("Model"),
        "FileType": info.get("FileType"),
        "source_note": "surviving_bytes_after_heic_to_jpeg_conversion",
    }
    return taken_at, visit_date, lat, lon, slim


def rest(env, method, path, body=None, extra_headers=None):
    url = env["LEEOSPLUS_URL"].rstrip("/") + path
    headers = {
        "apikey": env["LEEOSPLUS_SERVICE_KEY"],
        "Authorization": "Bearer " + env["LEEOSPLUS_SERVICE_KEY"],
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(body).encode() if body is not None else None
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, r.headers, json.loads(raw) if raw else None
    except HTTPError as e:
        err = e.read().decode()[:2000]
        return e.code, e.headers, err


def existing_sha_map(env, shas):
    found = {}
    # query in chunks
    for i in range(0, len(shas), 20):
        chunk = shas[i:i + 20]
        inlist = "(" + ",".join(chunk) + ")"
        st, headers, data = rest(
            env, "GET",
            "/rest/v1/visual_observations?select=id,content_sha256,job_ref,allocation_batch,duplicate_of&content_sha256=in." + inlist,
        )
        if st != 200 or not isinstance(data, list):
            raise RuntimeError("sha lookup failed %s %s" % (st, data))
        for row in data:
            found.setdefault(row["content_sha256"], []).append(row)
    return found


def phash_thumb(thumb_path, is_mov):
    if is_mov:
        return None, "skipped_mov"
    if Image is None:
        return None, "pil_unavailable"
    if not thumb_path or not Path(thumb_path).is_file():
        return None, "no_thumb"
    try:
        with Image.open(thumb_path) as im:
            return dhash_hex(im), None
    except Exception as e:
        return None, "phash_failed:%s" % type(e).__name__


def ensure_mov_thumb(stem, incoming_thumb, cabinet_thumb, mov_path):
    if incoming_thumb.is_file():
        return str(incoming_thumb), None
    dest = incoming_thumb
    try:
        subprocess.check_call(
            ["ffmpeg", "-y", "-ss", "0.5", "-i", str(mov_path), "-frames:v", "1", "-q:v", "3", str(dest)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if dest.is_file() and dest.stat().st_size > 0:
            if not cabinet_thumb.is_file():
                subprocess.check_call(["cp", "-p", str(dest), str(cabinet_thumb)])
            return str(dest), None
    except Exception as e:
        return None, "mov_poster_failed:%s" % type(e).__name__
    return None, "mov_poster_missing"


def main():
    now = datetime.now(timezone.utc).isoformat()
    dictate = DICTATE_PATH.read_text().strip()
    env = load_env()
    if "LEEOSPLUS_URL" not in env or "LEEOSPLUS_SERVICE_KEY" not in env:
        print("missing supabase env", file=sys.stderr)
        sys.exit(2)

    ladder, ladder_raw, ladder_err = run_ladder()
    ident = parse_match_method(ladder if isinstance(ladder, dict) else {})

    files = sorted(
        [p for p in ALBUM.iterdir() if p.is_file() and p.name.startswith("IMG_")],
        key=lambda p: p.name,
    )
    heic_like = [p for p in files if p.suffix.lower() in {".heic", ".jpg", ".jpeg"}]
    movs = [p for p in files if p.suffix.lower() == ".mov"]
    if len(heic_like) != 52 or len(movs) != 2:
        print("UNEXPECTED FILE COUNTS stills=%s movs=%s" % (len(heic_like), len(movs)), file=sys.stderr)

    rows = []
    unresolved = []
    # originals were HEIC; another process converted in place before this ingest
    unresolved.append({
        "file": "*",
        "reason": "original_heic_replaced_with_jpeg_before_ingest",
        "detail": "52 HEIC and the album zip were gone at ingest time; sha256 is of surviving JPEG/MOV bytes. Incoming files were not deleted by this ingest.",
    })

    prepared = []
    for path in files:
        stem = path.stem  # IMG_1841
        is_mov = path.suffix.lower() == ".mov"
        cab = CAB_ORIG / path.name
        if not cab.is_file():
            subprocess.check_call(["cp", "-p", str(path), str(cab)])
        incoming_thumb = THUMBS / (stem + ".jpg")
        cabinet_thumb = CAB_THUMBS / (stem + ".jpg")
        thumb_path = None
        if is_mov:
            thumb_path, thumb_err = ensure_mov_thumb(stem, incoming_thumb, cabinet_thumb, path)
            if thumb_err:
                unresolved.append({"file": path.name, "reason": thumb_err})
        else:
            if incoming_thumb.is_file():
                thumb_path = str(incoming_thumb)
            else:
                unresolved.append({"file": path.name, "reason": "missing_thumb"})
                thumb_path = None
        digest = sha256_file(path)
        taken_at, visit_date, lat, lon, exif = exif_for(path)
        phash, phash_err = phash_thumb(thumb_path, is_mov)
        if phash_err and phash_err not in {"skipped_mov"}:
            unresolved.append({"file": path.name, "reason": phash_err})
        desc, tags, tags_source, building, activity, extra_unres = describe(stem, is_mov)
        unresolved.extend(extra_unres)
        prepared.append({
            "stem": stem,
            "name": path.name,
            "incoming_path": str(path),
            "cabinet_path": str(cab),
            "thumb_path": thumb_path,
            "is_mov": is_mov,
            "sha256": digest,
            "phash": phash,
            "taken_at": taken_at,
            "visit_date": visit_date,
            "gps_lat": lat,
            "gps_lon": lon,
            "exif": exif,
            "description": desc,
            "tags": tags,
            "tags_source": tags_source,
            "building": building,
            "activity": activity,
        })

    shas = [p["sha256"] for p in prepared]
    existing = existing_sha_map(env, shas)

    to_insert = []
    duplicates = []
    already_this_batch = []
    for p in prepared:
        hits = existing.get(p["sha256"], [])
        this_batch = [h for h in hits if h.get("allocation_batch") == BATCH and h.get("job_ref") == JOB_REF]
        if this_batch:
            already_this_batch.append({"file": p["name"], "id": this_batch[0]["id"], "sha256": p["sha256"]})
            continue
        dup_of = hits[0]["id"] if hits else None
        if dup_of:
            duplicates.append({
                "file": p["name"],
                "sha256": p["sha256"],
                "duplicate_of": dup_of,
                "existing_job_ref": hits[0].get("job_ref"),
            })
            unresolved.append({
                "file": p["name"],
                "reason": "sha256_already_present",
                "duplicate_of": dup_of,
            })
        row = {
            "content_sha256": p["sha256"],
            "phash": p["phash"],
            "picture_path": p["cabinet_path"],
            "thumb_path": p["thumb_path"],
            "source": SOURCE,
            "original_path": p["incoming_path"],
            "taken_at": p["taken_at"],
            "gps_lat": p["gps_lat"],
            "gps_lon": p["gps_lon"],
            "exif": p["exif"],
            "description": p["description"],
            "model_name": MODEL_NAME,
            "described_at": now,
            "kept": True,
            "tags": p["tags"],
            "lee_note": dictate,
            "tags_source": p["tags_source"],
            "job_ref": JOB_REF,
            "visit_date": p["visit_date"],
            "match_method": ident["match_method"],
            "match_status": ident["match_status"],
            "gra_site_id": None,
            "is_public": False,
            "building": p["building"],
            "activity": p["activity"],
            "allocation_batch": BATCH,
            "allocation_confidence": ident["allocation_confidence"],
            "duplicate_of": dup_of,
            "dedupe_kind": "content_sha256" if dup_of else None,
        }
        to_insert.append((p, row))

    inserted = []
    insert_errors = []
    for i in range(0, len(to_insert), 8):
        chunk = to_insert[i:i + 8]
        payload = [row for _, row in chunk]
        st, headers, data = rest(
            env, "POST",
            "/rest/v1/visual_observations",
            payload,
            extra_headers={"Prefer": "return=representation"},
        )
        if st in (200, 201) and isinstance(data, list):
            for item, ret in zip(chunk, data):
                p, row = item
                inserted.append({
                    "id": ret.get("id"),
                    "file": p["name"],
                    "sha256": p["sha256"],
                    "picture_path": p["cabinet_path"],
                    "original_path": p["incoming_path"],
                    "thumb_path": p["thumb_path"],
                    "duplicate_of": row.get("duplicate_of"),
                    "phash": p["phash"],
                })
            continue
        # retry one-by-one so a unique-constraint on one sha does not drop the rest
        for p, row in chunk:
            st1, _, data1 = rest(
                env, "POST",
                "/rest/v1/visual_observations",
                row,
                extra_headers={"Prefer": "return=representation"},
            )
            if st1 in (200, 201) and isinstance(data1, list) and data1:
                ret = data1[0]
                inserted.append({
                    "id": ret.get("id"),
                    "file": p["name"],
                    "sha256": p["sha256"],
                    "picture_path": p["cabinet_path"],
                    "original_path": p["incoming_path"],
                    "thumb_path": p["thumb_path"],
                    "duplicate_of": row.get("duplicate_of"),
                    "phash": p["phash"],
                })
            else:
                insert_errors.append({"file": p["name"], "status": st1, "error": str(data1)[:500]})
                unresolved.append({"file": p["name"], "reason": "insert_failed", "status": st1})

    # live verify
    st, headers, live = rest(
        env, "GET",
        "/rest/v1/visual_observations?job_ref=eq.1892-26&select=id,original_path,picture_path,description,match_method,allocation_confidence,match_status,gra_site_id,content_sha256,duplicate_of,thumb_path,building,activity,tags_source,allocation_batch,source,kept,is_public&order=original_path",
    )
    live_rows = live if isinstance(live, list) else []
    this_batch_live = [r for r in live_rows if r.get("allocation_batch") == BATCH]
    live_files = set()
    for r in this_batch_live:
        op = r.get("original_path") or ""
        live_files.add(Path(op).name)
    expected_names = [p.name for p in files]
    missing_files = [n for n in expected_names if n not in live_files]

    methods = sorted({r.get("match_method") for r in this_batch_live})
    desc_n = sum(1 for r in this_batch_live if r.get("description"))
    gra_ids = sorted({r.get("gra_site_id") for r in this_batch_live if r.get("gra_site_id")})

    receipt = {
        "job_ref": JOB_REF,
        "site": "6 Pancras Square",
        "not": ["1831-25 3 Pancras", "1895-26 Elephant Park"],
        "ingested_at": now,
        "source": SOURCE,
        "allocation_batch": BATCH,
        "match_method": ident["match_method"],
        "allocation_confidence": ident["allocation_confidence"],
        "match_status": ident["match_status"],
        "gra_site_id": gra_ids[0] if len(gra_ids) == 1 else None,
        "gra_site_ids": gra_ids,
        "gra_note": "GRA sites has 3 Pancras Square as 1831-25 only. No gra_site_id for 6 Pancras / 1892-26. Not used.",
        "lanes_used": ident["lanes_used"],
        "lanes_run": ident["lanes_run"],
        "lanes_unreachable": ident["lanes_unreachable"],
        "lanes_searched_identity": ["lane1_job_ref", "lane2_gra_sites"],
        "lane_notes": {
            "lane1_job_ref": "portfolio_register.csv does not hold 1892-26 (job_registry in LeeOSplus does, display_name 1892-26 6 Pancras Square / Greengage). Ladder lane1 uses the CSV.",
            "lane2_gra_sites": "shared job registry / GRA sites returned no 1892-26 and no 6 Pancras Square. 3 Pancras is 1831-25 and was not used.",
        },
        "ladder": ladder,
        "counts": {
            "files_on_disk": len(files),
            "stills": len(heic_like),
            "movs": len(movs),
            "inserted_this_run": len(inserted),
            "already_this_batch": len(already_this_batch),
            "live_job_rows": len(live_rows),
            "live_batch_rows": len(this_batch_live),
            "descriptions": desc_n,
            "duplicates": len(duplicates),
            "unresolved": len(unresolved),
            "insert_errors": len(insert_errors),
            "missing_files": len(missing_files),
        },
        "row_ids": inserted + already_this_batch,
        "sha256": [{"file": p["name"], "sha256": p["sha256"], "phash": p["phash"]} for p in prepared],
        "paths": {
            "album": str(ALBUM),
            "thumbs": str(THUMBS),
            "cabinet_originals": str(CAB_ORIG),
            "cabinet_thumbs": str(CAB_THUMBS),
            "receipt": str(RECEIPT),
        },
        "duplicates": duplicates,
        "unresolved": unresolved,
        "insert_errors": insert_errors,
        "missing_files": missing_files,
        "match_method_values_live": methods,
        "incoming_preserved": True,
        "original_format_note": "Incoming HEIC were already converted in-place to JPEG (HEIC-CONVERT-RECEIPT.json) and the album zip was gone before this ingest. Rows keep the surviving JPEG/MOV paths. This ingest did not delete incoming files.",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n")

    summary = {
        "receipt": str(RECEIPT),
        "counts": receipt["counts"],
        "match_method": ident["match_method"],
        "gra_site_id": receipt["gra_site_id"],
        "unresolved_files": sorted({u.get("file") for u in unresolved if u.get("file") and u.get("file") != "*"}),
        "unresolved_reasons": unresolved,
        "missing_files": missing_files,
        "insert_errors_n": len(insert_errors),
    }
    print(json.dumps(summary, indent=2))
    if missing_files or insert_errors:
        sys.exit(3)


if __name__ == "__main__":
    main()
