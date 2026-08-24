#!/usr/bin/env python3
"""The Image Plane daily worker. One general nightly operation on Mini A.

What it does, in order, for every album in the inbox:
  discover -> account for files -> identity (the recorded ladder) ->
  file or quarantine -> read each new image once with local Qwen ->
  propose findings -> put open questions on the Attention page ->
  save progress so the next run resumes instead of restarting.

What it never does:
  * It never deletes an original, a HEIC, a zip or a video.
  * It never mints a job number and never invents an identity match.
  * It never calls a paid cloud model. Ollama on this machine only.
  * It never touches the historic corpus. Only albums in the inbox
    with a SOURCE.json are handled.
  * It never runs twice at once. A lock file guards the whole run.

The Google Photos fetch itself CANNOT run here. The proven fetch skill
drives Lee's Chrome on the laptop, and this machine has no Chrome tools.
So the fetch stage works from a queue: the laptop skill drops a fetched
album into the inbox with a SOURCE.json, and anything still waiting in
fetch_queue.json is reported on the Attention page as waiting for the
laptop. That is a recorded limit, not a fault.

The image reading uses the two RECORDED instruction sets that exist and
were tested:
  * caption pass  — describe_takeout_v2/1 (27 Jul 2026, proven on the
    Pancras cabinet 52/52).
  * writing pass  — the pdfVision ASK (2 Aug 2026, proven by Lee's own
    eye word-for-word on a real page): every word, number and date.
A FULLER analysis instruction set (work type, defect class, component,
measurements read INTO fields) was searched for and NOT found on this
machine or in the repository. That gap is recorded on the Attention page
by build_attention(); captions are not presented as satisfying it.

Run:    python3 daily_worker.py            one full pass over the inbox
        python3 daily_worker.py --status   print the registry and exit
State:  ~/image-plane/incoming/worker/     (registry, attention, logs)
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image  # /usr/bin/python3 on Mini A has PIL
except ImportError:
    Image = None

BASE = Path(os.environ.get("IMAGE_PLANE_ROOT", str(Path.home() / "image-plane")))
INBOX = BASE / "incoming" / "google"
WORKER = BASE / "incoming" / "worker"
LOGS = WORKER / "logs"
REGISTRY = WORKER / "registry.json"          # one record per album, staged
FETCH_QUEUE = WORKER / "fetch_queue.json"    # albums waiting for the laptop
ATTENTION = WORKER / "attention.json"        # the Attention page reads this
READ_INDEX = WORKER / "readings_index.json"  # sha256 -> [instruction versions read]
RUNS = WORKER / "runs.jsonl"                 # one line per run
SPINE_OUTBOX = WORKER / "spine_outbox.jsonl" # corrections that could not reach the spine
LOCK = WORKER / "worker.lock"
LADDER = BASE / "id_ladder_service.py"
ENV_FILE = BASE / ".env.flip"

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = "qwen3-vl:latest"
EXIFTOOL = "/opt/homebrew/bin/exiftool"

CAPTION_PROMPT = ("Describe this photograph in 1-2 factual sentences: "
                  "the main subject, the setting, and whether it is indoors or outdoors.")
CAPTION_VERSION = "describe_takeout_v2/1"
WRITING_PROMPT = ("Read this image out. Write out every word, number and date you can see, "
                  "keeping the order and the layout. Include headings, labels, "
                  "table figures, stamps and handwriting. Do not describe the image. "
                  "Do not explain. Do not add anything that is not written on it. If part "
                  "cannot be read, write [unreadable] in that place. If the image holds "
                  "no words at all, write exactly: NO WORDS ON THIS PAGE.")
WRITING_VERSION = "pdfvision-ask/1"
READING_VERSION = CAPTION_VERSION + "+" + WRITING_VERSION

BATCH = "daily-worker-v1"
MODEL_NAME_FOR_VO = "image-plane-daily-worker"
IMAGE_EXTS = {".jpg", ".jpeg", ".heic", ".png"}
VIDEO_EXTS = {".mov", ".mp4"}
JOB_REF_RE = re.compile(r"\b(\d{3,4}-\d{2})\b")

STAGES = ["discovered", "fetch_started", "fetch_completed", "files_accounted",
          "identity_done", "reading_started", "reading_completed",
          "findings_proposed", "questions_waiting", "review_completed"]


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(run_log, msg):
    line = "%s %s" % (now_utc(), msg)
    print(line, flush=True)
    with open(run_log, "a") as f:
        f.write(line + "\n")


def load_json(path, fallback):
    if Path(path).exists():
        try:
            return json.loads(Path(path).read_text())
        except Exception:
            return fallback
    return fallback


def save_json(path, data):
    tmp = str(path) + ".tmp"
    Path(tmp).write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)


def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k] = v.strip().strip('"').strip("'")
    return env


def rest(env, method, path, body=None, prefer=None, timeout=60):
    url = env.get("LEEOSPLUS_URL", "").rstrip("/") + path
    headers = {"apikey": env.get("LEEOSPLUS_SERVICE_KEY", ""),
               "Authorization": "Bearer " + env.get("LEEOSPLUS_SERVICE_KEY", ""),
               "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:1000]
    except Exception as e:
        return 0, "unreachable: %s" % type(e).__name__


# ---------------------------------------------------------------- locking

def take_lock(run_log):
    """One worker at a time. A stale lock from a dead process is cleared."""
    WORKER.mkdir(parents=True, exist_ok=True)
    if LOCK.exists():
        try:
            pid = int(LOCK.read_text().split()[0])
            os.kill(pid, 0)  # raises if that process is gone
            log(run_log, "REFUSED: run %s is still active (lock %s)" % (pid, LOCK))
            append_run({"started": now_utc(), "result": "refused_active_run",
                        "active_pid": pid})
            return False
        except (ProcessLookupError, ValueError, PermissionError):
            log(run_log, "stale lock cleared")
            LOCK.unlink()
    LOCK.write_text("%d %s" % (os.getpid(), now_utc()))
    return True


def drop_lock():
    try:
        if LOCK.exists() and LOCK.read_text().split()[0] == str(os.getpid()):
            LOCK.unlink()
    except Exception:
        pass


def append_run(summary):
    with open(RUNS, "a") as f:
        f.write(json.dumps(summary) + "\n")


# ---------------------------------------------------------------- hashing

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def dhash_hex(path):
    if Image is None:
        return None
    try:
        with Image.open(path) as img:
            grey = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            px = grey.tobytes()
            bits = 0
            for row in range(8):
                for col in range(8):
                    bits = (bits << 1) | (1 if px[row * 9 + col] > px[row * 9 + col + 1] else 0)
            return f"{bits:016x}"
    except Exception:
        return None


def exif_for(path):
    """Capture time and camera facts. exiftool first, sips as fallback."""
    info = {}
    if Path(EXIFTOOL).exists():
        try:
            raw = subprocess.check_output(
                [EXIFTOOL, "-j", "-n", "-DateTimeOriginal", "-CreateDate",
                 "-MediaCreateDate", "-GPSLatitude", "-GPSLongitude",
                 "-Make", "-Model", "-FileType", str(path)],
                stderr=subprocess.DEVNULL, timeout=30)
            info = json.loads(raw)[0]
        except Exception:
            info = {}
    dt = info.get("DateTimeOriginal") or info.get("CreateDate") or info.get("MediaCreateDate")
    taken_at = None
    if dt:
        s = str(dt).replace(":", "-", 2).replace(" ", "T", 1)
        taken_at = s
    return {"taken_at": taken_at,
            "gps_lat": info.get("GPSLatitude"), "gps_lon": info.get("GPSLongitude"),
            "make": info.get("Make"), "camera": info.get("Model"),
            "file_type": info.get("FileType")}


# ---------------------------------------------------------------- reading

def to_jpg_1024(src, dest):
    r = subprocess.run(["sips", "-s", "format", "jpeg", "-Z", "1024", str(src),
                        "--out", str(dest)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r.returncode == 0 and Path(dest).is_file()


def qwen(prompt, jpg_path, timeout=300):
    b = base64.b64encode(Path(jpg_path).read_bytes()).decode()
    body = json.dumps({"model": MODEL, "prompt": prompt, "images": [b],
                       "stream": False, "think": False,
                       "options": {"temperature": 0}}).encode()
    t0 = time.time()
    resp = json.loads(urllib.request.urlopen(
        urllib.request.Request(OLLAMA + "/api/generate", data=body,
                               headers={"Content-Type": "application/json"}),
        timeout=timeout).read())
    return (resp.get("response") or "").strip(), round(time.time() - t0, 1)


# ---------------------------------------------------------------- identity

def run_ladder(evidence):
    proc = subprocess.run([sys.executable, str(LADDER)],
                          input=json.dumps(evidence).encode(),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          cwd=str(BASE), timeout=120)
    out = proc.stdout.decode() if proc.stdout else ""
    try:
        return json.loads(out)
    except Exception:
        return {"error": "ladder_unreadable", "stdout": out[:1500],
                "stderr": proc.stderr.decode()[:500], "returncode": proc.returncode}


def judge_identity(ladder, claimed_ref):
    """Two agreeing lanes confirm. Anything less is quarantine, never a guess."""
    hits = ladder.get("hits") or {}
    job = ladder.get("job_ref")
    lanes_run = [x.get("lane") for x in (ladder.get("lanes_run") or [])]
    lanes_unreach = [x.get("lane") for x in (ladder.get("lanes_unreachable") or [])]
    if job:
        agreeing = [lane for lane, refs in hits.items() if job in (refs or [])]
        if len(agreeing) >= 2 and (claimed_ref is None or claimed_ref == job):
            return {"state": "resolved", "job_ref": job,
                    "match_method": "+".join(agreeing),
                    "allocation_confidence": "high" if ladder.get("confidence") in ("corroborated", "settled") else "medium",
                    "lanes_used": agreeing, "lanes_run": lanes_run,
                    "lanes_unreachable": lanes_unreach}
    return {"state": "quarantined", "job_ref": None,
            "ladder_job_ref": job, "lanes_run": lanes_run,
            "lanes_unreachable": lanes_unreach, "hits": hits,
            "reason": ("ladder returned no job" if not job else
                       "fewer than two lanes agree" if not hits else
                       "ladder answer does not match the album's claimed reference")}


# ---------------------------------------------------------------- stages

def progress_path(album_dir):
    return album_dir / "PROGRESS.json"


def load_progress(album_dir, source):
    p = load_json(progress_path(album_dir), None)
    if p is None:
        p = {"album": album_dir.name,
             "album_id": source.get("album_id"),
             "album_name": source.get("album_name"),
             "stages": {"discovered": now_utc(),
                        "fetch_started": source.get("fetched_at"),
                        "fetch_completed": source.get("fetched_at")},
             "fetched_by": source.get("fetched_by")}
        save_json(progress_path(album_dir), p)
    return p


def mark(album_dir, progress, stage, extra=None):
    progress["stages"][stage] = now_utc()
    if extra:
        progress.update(extra)
    save_json(progress_path(album_dir), progress)


def stage_done(progress, stage):
    return bool(progress.get("stages", {}).get(stage))


def unpack_zips(album_dir, run_log):
    """Extract any album zip into originals/. The zip itself is never removed."""
    orig = album_dir / "originals"
    orig.mkdir(exist_ok=True)
    for z in sorted(album_dir.glob("*.zip")):
        markfile = album_dir / (".unpacked-" + z.name)
        if markfile.exists():
            continue
        r = subprocess.run(["unzip", "-o", "-q", str(z), "-d", str(orig)])
        if r.returncode == 0:
            markfile.write_text(now_utc())
            log(run_log, "unpacked %s" % z.name)
        else:
            log(run_log, "UNPACK FAILED %s" % z.name)
    return orig


def account_files(album_dir, progress, run_log):
    orig = unpack_zips(album_dir, run_log)
    files = [p for p in sorted(orig.rglob("*"))
             if p.is_file() and not p.name.startswith(".")]
    if not files:
        # album content may sit loose in the folder (older convention)
        files = [p for p in sorted(album_dir.iterdir()) if p.is_file()
                 and p.suffix.lower() in IMAGE_EXTS | VIDEO_EXTS]
    manifest = load_json(album_dir / "MANIFEST.json", {"files": {}})
    seen_shas = {}
    for p in files:
        rel = str(p.relative_to(album_dir))
        if rel in manifest["files"]:
            seen_shas.setdefault(manifest["files"][rel]["sha256"], rel)
            continue
        digest = sha256_file(p)
        entry = {"sha256": digest, "bytes": p.stat().st_size,
                 "kind": ("image" if p.suffix.lower() in IMAGE_EXTS else
                          "video" if p.suffix.lower() in VIDEO_EXTS else "other")}
        entry.update(exif_for(p))
        if entry["kind"] == "image":
            entry["dhash"] = dhash_hex(p)
        if digest in seen_shas:
            entry["duplicate_of"] = seen_shas[digest]
        else:
            seen_shas[digest] = rel
        manifest["files"][rel] = entry
        save_json(album_dir / "MANIFEST.json", manifest)
    mark(album_dir, progress, "files_accounted",
         {"file_count": len(manifest["files"])})
    log(run_log, "%s: %d files accounted" % (album_dir.name, len(manifest["files"])))
    return manifest


def identity_stage(album_dir, progress, source, run_log):
    claimed = None
    m = JOB_REF_RE.search(source.get("album_name") or album_dir.name)
    if m:
        claimed = m.group(1)
    evidence = {"subject": source.get("album_name") or album_dir.name,
                "text": "google photos album: %s" % (source.get("album_name") or album_dir.name)}
    if claimed:
        evidence["job_refs"] = [claimed]
    ladder = run_ladder(evidence)
    ident = judge_identity(ladder, claimed)
    ident["evidence_given"] = evidence
    ident["ruled_at"] = now_utc()
    save_json(album_dir / "IDENTITY.json", {"ladder": ladder, "identity": ident})
    mark(album_dir, progress, "identity_done", {"identity": ident["state"],
                                                "job_ref": ident.get("job_ref")})
    log(run_log, "%s: identity %s %s" % (album_dir.name, ident["state"],
                                         ident.get("job_ref") or ""))
    return ident


def make_thumb(src, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file():
        return True
    return to_jpg_1024(src, dest)


def reading_stage(album_dir, progress, manifest, run_log):
    """Read each unique new image once with the two recorded instruction sets."""
    ledger_path = album_dir / "readings.jsonl"
    index = load_json(READ_INDEX, {})
    done_here = set()
    if ledger_path.exists():
        for line in ledger_path.read_text().splitlines():
            try:
                done_here.add(json.loads(line)["sha256"])
            except Exception:
                pass
    if not stage_done(progress, "reading_started"):
        mark(album_dir, progress, "reading_started")
    thumbs = album_dir / "thumbs"
    count = 0
    for rel, entry in sorted(manifest["files"].items()):
        sha = entry["sha256"]
        if entry["kind"] == "video":
            continue  # the recorded route never sends videos
        if entry["kind"] != "image":
            continue
        if "duplicate_of" in entry:
            continue
        if sha in done_here:
            continue
        if READING_VERSION in index.get(sha, []):
            # already read in another album: point at it, do not re-run the model
            with open(ledger_path, "a") as f:
                f.write(json.dumps({"sha256": sha, "file": rel,
                                    "reading_version": READING_VERSION,
                                    "reused_existing_reading": True,
                                    "ts": now_utc()}) + "\n")
            done_here.add(sha)
            continue
        src = album_dir / rel
        stemname = Path(rel).stem
        thumb = thumbs / (stemname + ".jpg")
        if not make_thumb(src, thumb):
            with open(ledger_path, "a") as f:
                f.write(json.dumps({"sha256": sha, "file": rel,
                                    "error": "thumbnail_failed", "ts": now_utc()}) + "\n")
            continue
        jpg = "/tmp/_dw_%s.jpg" % sha[:12]
        if not to_jpg_1024(src, jpg):
            continue
        try:
            caption, secs1 = qwen(CAPTION_PROMPT, jpg)
            writing, secs2 = qwen(WRITING_PROMPT, jpg)
        except Exception as e:
            log(run_log, "%s: reader failed on %s (%s)" % (album_dir.name, rel, type(e).__name__))
            break  # the model or the queue is unwell; resume next run
        finally:
            if os.path.exists(jpg):
                os.remove(jpg)
        rec = {"sha256": sha, "file": rel, "album": album_dir.name,
               "taken_at": entry.get("taken_at"), "camera": entry.get("camera"),
               "model": MODEL,
               "caption_prompt_version": CAPTION_VERSION, "caption": caption,
               "caption_seconds": secs1,
               "writing_prompt_version": WRITING_VERSION, "visible_writing": writing,
               "writing_seconds": secs2,
               "reading_version": READING_VERSION,
               "uncertainty": "machine reading; not checked by a person",
               "detailed_analysis": None,
               "detailed_analysis_note": ("no recorded tested detailed-analysis "
                                          "instruction set exists; blocker recorded "
                                          "on the Attention page"),
               "ts": now_utc()}
        with open(ledger_path, "a") as f:
            f.write(json.dumps(rec) + "\n")
        index.setdefault(sha, []).append(READING_VERSION)
        save_json(READ_INDEX, index)
        done_here.add(sha)
        count += 1
        log(run_log, "%s: read %s (%.0fs+%.0fs)" % (album_dir.name, rel, secs1, secs2))
    unique_images = [r for r, e in manifest["files"].items()
                     if e["kind"] == "image" and "duplicate_of" not in e]
    if all(e["sha256"] in done_here for r, e in manifest["files"].items()
           if e["kind"] == "image" and "duplicate_of" not in e):
        mark(album_dir, progress, "reading_completed",
             {"images_read": len(unique_images)})
        log(run_log, "%s: reading complete (%d unique images)" % (album_dir.name, len(unique_images)))
    return count


def filing_stage(album_dir, progress, manifest, ident, env, run_log):
    """File confidently identified media into the cabinet and the estate store."""
    job = ident.get("job_ref")
    if not job:
        return
    cab = BASE / "cabinet" / job / "originals"
    cab_thumbs = BASE / "cabinet" / job / "thumbs"
    cab.mkdir(parents=True, exist_ok=True)
    cab_thumbs.mkdir(parents=True, exist_ok=True)
    filed = load_json(album_dir / "FILED.json", {"rows": {}})
    readings = {}
    rp = album_dir / "readings.jsonl"
    if rp.exists():
        for line in rp.read_text().splitlines():
            try:
                r = json.loads(line)
                readings[r.get("sha256")] = r
            except Exception:
                pass
    for rel, entry in sorted(manifest["files"].items()):
        if entry["kind"] not in ("image", "video") or "duplicate_of" in entry:
            continue
        if rel in filed["rows"]:
            continue
        src = album_dir / rel
        dest = cab / Path(rel).name
        if not dest.is_file():
            subprocess.check_call(["cp", "-p", str(src), str(dest)])
        thumb = album_dir / "thumbs" / (Path(rel).stem + ".jpg")
        cab_thumb = cab_thumbs / (Path(rel).stem + ".jpg")
        if thumb.is_file() and not cab_thumb.is_file():
            subprocess.check_call(["cp", "-p", str(thumb), str(cab_thumb)])
        reading = readings.get(entry["sha256"], {})
        row = {"content_sha256": entry["sha256"], "phash": entry.get("dhash"),
               "picture_path": str(dest),
               "thumb_path": str(thumb) if thumb.is_file() else None,
               "source": "google-album-%s" % (progress.get("album_id") or album_dir.name),
               "original_path": str(src),
               "taken_at": entry.get("taken_at"),
               "gps_lat": entry.get("gps_lat"), "gps_lon": entry.get("gps_lon"),
               "exif": {"Make": entry.get("make"), "Model": entry.get("camera"),
                        "FileType": entry.get("file_type")},
               "description": reading.get("caption"),
               "model_name": MODEL_NAME_FOR_VO,
               "described_at": reading.get("ts"),
               "kept": True, "is_public": False,
               "job_ref": job,
               "visit_date": (entry.get("taken_at") or "")[:10] or None,
               "match_method": ident["match_method"],
               "match_status": "ladder_confirmed",
               "allocation_batch": BATCH,
               "allocation_confidence": ident["allocation_confidence"]}
        st, data = rest(env, "POST", "/rest/v1/visual_observations", [row],
                        prefer="return=representation")
        if st in (200, 201) and isinstance(data, list):
            filed["rows"][rel] = {"id": data[0].get("id"), "sha256": entry["sha256"]}
            save_json(album_dir / "FILED.json", filed)
        else:
            # A refusal from the estate is a finding, never routed around.
            filed.setdefault("refused", {})[rel] = {"status": st, "detail": str(data)[:500]}
            save_json(album_dir / "FILED.json", filed)
            log(run_log, "%s: estate refused %s (%s)" % (album_dir.name, rel, st))


def findings_stage(album_dir, progress, manifest, ident, run_log):
    """Group related images by capture time into PROPOSED findings.

    A proposal is a machine suggestion. It never becomes a confirmed
    technical fact here; only a person's ruling on the job page does that.
    """
    out_path = album_dir / "findings_proposed.json"
    if out_path.exists():
        mark(album_dir, progress, "findings_proposed")
        return
    readings = []
    rp = album_dir / "readings.jsonl"
    if rp.exists():
        for line in rp.read_text().splitlines():
            try:
                readings.append(json.loads(line))
            except Exception:
                pass
    by_sha = {r.get("sha256"): r for r in readings}
    dictate = None
    for cand in ("LEE-DICTATE.txt", "DICTATE.txt"):
        p = album_dir / cand
        if p.exists():
            dictate = p.read_text().strip()
    items = []
    for rel, entry in sorted(manifest["files"].items(),
                             key=lambda kv: (kv[1].get("taken_at") or "", kv[0])):
        if entry["kind"] != "image" or "duplicate_of" in entry:
            continue
        items.append((rel, entry))
    groups, current = [], []
    last_ts = None
    for rel, entry in items:
        ts = entry.get("taken_at")
        t = None
        if ts:
            try:
                t = datetime.fromisoformat(ts)
            except ValueError:
                t = None
        if current and (t is None or last_ts is None or
                        abs((t - last_ts).total_seconds()) > 600):
            groups.append(current)
            current = []
        current.append((rel, entry))
        if t is not None:
            last_ts = t
    if current:
        groups.append(current)
    findings = []
    for i, group in enumerate(groups, 1):
        caps = [by_sha.get(e["sha256"], {}).get("caption") or "" for _, e in group]
        findings.append({
            "id": "%s-proposed-%02d" % (album_dir.name, i),
            "state": "proposed",
            "job_ref": ident.get("job_ref"),
            "visit_date": (group[0][1].get("taken_at") or "")[:10] or None,
            "location": None,
            "images": [rel for rel, _ in group],
            "readings": [e["sha256"] for _, e in group],
            "captions": caps,
            "dictate_fragment": dictate,
            "may_establish": ("these %d images were taken together within "
                              "ten minutes; a person must say what they show"
                              % len(group)),
            "uncertain": "grouping is by capture time only; subject grouping is not established",
            "provenance": {"grouped_by": "daily_worker capture-time clustering",
                           "reading_version": READING_VERSION,
                           "proposed_at": now_utc()},
        })
    save_json(out_path, {"findings": findings})
    mark(album_dir, progress, "findings_proposed", {"findings_count": len(findings)})
    log(run_log, "%s: %d findings proposed" % (album_dir.name, len(findings)))


# ---------------------------------------------------------------- attention

def build_attention(registry):
    """One stable page of everything waiting on a person."""
    entries = []
    queue = load_json(FETCH_QUEUE, {"albums": []})
    for q in queue.get("albums", []):
        if not q.get("fetched"):
            entries.append({"kind": "fetch_waiting",
                            "album_id": q.get("album_id"),
                            "album_name": q.get("album_name"),
                            "why": ("waiting for the laptop Google Photos fetch — "
                                    "Mini A has no Chrome; the proven skill runs on "
                                    "the laptop only"),
                            "link": None})
    if queue.get("auth_blocked"):
        entries.append({"kind": "google_auth",
                        "why": queue["auth_blocked"], "link": None})
    for slug, rec in sorted(registry.items()):
        p = load_json(INBOX / slug / "PROGRESS.json", {})
        ident = load_json(INBOX / slug / "IDENTITY.json", {}).get("identity", {})
        if p.get("identity") == "quarantined":
            thumbs = sorted((INBOX / slug / "thumbs").glob("*.jpg")) if (INBOX / slug / "thumbs").exists() else []
            entries.append({
                "kind": "identity_uncertain",
                "album": slug, "album_name": p.get("album_name"),
                "why": "identity uncertain: %s" % ident.get("reason", "unknown"),
                "identity_evidence": {"lanes_run": ident.get("lanes_run"),
                                      "lanes_unreachable": ident.get("lanes_unreachable"),
                                      "hits": ident.get("hits")},
                "images": ["/worker-media/%s/thumbs/%s" % (slug, t.name) for t in thumbs[:12]],
                "question": ("Which job, if any, does the album '%s' belong to? "
                             "The ladder could not confirm one from two lanes."
                             % (p.get("album_name") or slug)),
                "link": "/album/%s" % urllib.parse.quote(slug),
            })
        fp = load_json(INBOX / slug / "findings_proposed.json", {})
        proposed = [f for f in fp.get("findings", []) if f.get("state") == "proposed"]
        if proposed and p.get("identity") == "resolved":
            entries.append({
                "kind": "findings_waiting",
                "album": slug, "album_name": p.get("album_name"),
                "job_ref": p.get("job_ref"),
                "why": "%d proposed findings await review" % len(proposed),
                "link": "/job/%s" % p.get("job_ref"),
            })
    entries.append({
        "kind": "missing_detailed_reader",
        "why": ("no recorded tested detailed-analysis reading instruction set was "
                "found (searched Mini A image-plane scripts, the repository, and "
                "glenross); images carry the caption and visible-writing passes only"),
        "link": None})
    outbox = []
    if SPINE_OUTBOX.exists():
        outbox = [l for l in SPINE_OUTBOX.read_text().splitlines() if l.strip()]
    if outbox:
        entries.append({"kind": "spine_outbox",
                        "why": "%d corrections could not reach the memory spine and wait in the outbox" % len(outbox),
                        "link": None})
    save_json(ATTENTION, {"built_at": now_utc(), "entries": entries})
    return entries


# ---------------------------------------------------------------- main

def retry_spine_outbox(env, run_log):
    if not SPINE_OUTBOX.exists():
        return
    lines = [l for l in SPINE_OUTBOX.read_text().splitlines() if l.strip()]
    kept = []
    for line in lines:
        try:
            row = json.loads(line)
        except Exception:
            continue
        st, _ = rest(env, "POST", "/rest/v1/observations", row)
        if st not in (200, 201):
            kept.append(line)
    SPINE_OUTBOX.write_text("\n".join(kept) + ("\n" if kept else ""))
    if lines and not kept:
        log(run_log, "spine outbox drained (%d rows)" % len(lines))


def discover(registry, run_log):
    for d in sorted(INBOX.iterdir()):
        if not d.is_dir() or d.name in registry:
            continue
        source_json = d / "SOURCE.json"
        if not source_json.exists():
            # Not the worker's convention. The Pancras cabinet and any older
            # folder are left exactly as they are.
            continue
        registry[d.name] = {"registered": now_utc()}
        log(run_log, "discovered album folder %s" % d.name)
    return registry


def process_album(slug, env, run_log):
    album_dir = INBOX / slug
    source = load_json(album_dir / "SOURCE.json", {})
    progress = load_progress(album_dir, source)
    if stage_done(progress, "review_completed"):
        return "complete"
    manifest = account_files(album_dir, progress, run_log)
    if not stage_done(progress, "identity_done"):
        ident = identity_stage(album_dir, progress, source, run_log)
    else:
        ident = load_json(album_dir / "IDENTITY.json", {}).get("identity", {})
    reading_stage(album_dir, progress, manifest, run_log)
    if ident.get("state") == "resolved":
        filing_stage(album_dir, progress, manifest, ident, env, run_log)
        findings_stage(album_dir, progress, manifest, ident, run_log)
    else:
        mark(album_dir, progress, "questions_waiting")
    return progress.get("stages")


def main():
    WORKER.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    run_log = LOGS / ("run-%s.log" % datetime.now().strftime("%Y%m%d-%H%M%S"))
    registry = load_json(REGISTRY, {})
    if "--status" in sys.argv:
        print(json.dumps(registry, indent=2))
        return 0
    if not take_lock(run_log):
        return 3
    started = now_utc()
    summary = {"started": started, "albums": {}, "result": "ok"}
    try:
        registry = discover(registry, run_log)
        save_json(REGISTRY, registry)
        env = load_env()
        for slug in sorted(registry):
            try:
                summary["albums"][slug] = process_album(slug, env, run_log)
            except Exception as e:
                summary["albums"][slug] = "error: %s" % type(e).__name__
                log(run_log, "%s: ERROR %s: %s" % (slug, type(e).__name__, e))
        retry_spine_outbox(env, run_log)
        entries = build_attention(registry)
        summary["attention_entries"] = len(entries)
    finally:
        summary["finished"] = now_utc()
        append_run(summary)
        drop_lock()
    log(run_log, "run finished: %s" % json.dumps(summary)[:400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
