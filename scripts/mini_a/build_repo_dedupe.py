#!/usr/bin/env python3
"""
F6 Output 3 -- build_repo_dedupe.py

Dedupe pass over the VALID allocation_v2.jsonl photo set (rows with a job_ref
whose path is NOT in allocation_v2_flags.jsonl -- ~8,488 rows, verified
100% iCloud-sourced on this run -- see PHASE 1c note below).

Writes grind/repo_dedupe_flags.jsonl -- one verdict row per collapsed/flagged
photo: {"path", "duplicate_of", "kind": "exact|near|possible_twin|prior_pass",
"evidence"}.

Never touches allocation_v2.jsonl, allocation_v2_flags.jsonl, photo_ledger_merged.jsonl,
or takeout_ledger_merged.jsonl. Never deletes a source photo. Verdicts land in
THIS new file only.

PHASE 1 (fast, synchronous, written immediately):
  1a. EXACT   -- identical sha256 (photo_ledger_merged.jsonl / takeout_ledger_merged.jsonl)
                 within the SAME job_ref (roof) -> collapse to a keeper.
  1b. PRIOR_PASS -- allocation_v2.jsonl rows that already carry a duplicate_of
                 verdict (240 rows, from the 2026-07-03 takeout-reencode dedupe
                 pass) are imported VERBATIM, never recomputed or contradicted.
  1c. POSSIBLE_TWIN -- cross-ledger (iCloud<->Takeout) basename+date match within
                 the same roof -> flag only, NEVER collapsed (IP-L5: re-encoding
                 across ledgers changes bytes, sha256/near-hash can't be trusted
                 cross-ledger). NOTE: the current valid set is 100% iCloud (the
                 402 Takeout rows in allocation_v2.jsonl are ALL already excluded
                 via allocation_v2_flags.jsonl -- 303 of them via the prior dedupe
                 pass in 1b, the remaining 99 for unrelated reasons out of this
                 build's scope) so this pass is a structural no-op on today's
                 data; it still runs in full so it is live the day Takeout photos
                 re-enter the valid set.

PHASE 2 (near/burst dupes, may be long-running -- appended when done):
  dHash (from src/image_plane/phash.py, copied below with ONE Python-3.9
  compatibility fix noted inline -- see comment) on 640px sips thumbnails for
  every valid, still-active (post-exact) photo that shares a roof AND a visit
  date within +-1 day with another valid photo. Hamming <= 8, restricted to the
  SAME ledger (IP-L5 guard enforced again here, not just at the candidate-pair
  stage) -> collapse to a keeper. Thumbs land in grind/hash_thumbs2/ (NOT
  grind/flip_thumbs -- that cache is keyed by spine row id, different keying).
  Run under nohup + caffeinate -dimsu; progress logged to grind/repo_dedupe.log.

  COLLISION-PROOF THUMB NAMING (fix for the 2026-07-11 false-success run):
  `sips ... --out DIR` names each output after the INPUT file's basename, and
  it RESOLVES SYMLINKS to the target's real basename (probed on Mini A this
  run: a symlink named symlink_abc123.HEIC produced IMG_0876.jpg). Source
  basenames repeat heavily (8,326 candidates -> only ~6,237 distinct
  basenames), so raw paths AND symlinks alike silently overwrite each other's
  thumbs. HARDLINKS keep their own name (same probe: hardlink_def456.HEIC ->
  hardlink_def456.jpg), so each candidate gets a hardlink named
  sha256(path-string)[:16] + orig ext in grind/hash_thumbs_src2/ (cp fallback
  if linking ever fails), and each thumb is looked up by that unique stem.
  A >2% dhash failure rate ABORTS the run with nonzero exit and a loud log
  line -- 100% failure must never report DONE again.

Keeper choice is ALWAYS deterministic: sort the group's paths, the
alphabetically-earliest wins. The script never depends on dict/set iteration
order for a keeper decision -- every keeper choice goes through sorted() first.
Invoke with PYTHONHASHSEED=0 for belt-and-braces reproducibility.
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from datetime import date

from PIL import Image

ROOT = os.path.expanduser("~/image-plane")
GRIND = os.path.join(ROOT, "grind")
ALLOC_V2 = os.path.join(GRIND, "allocation_v2.jsonl")
ALLOC_V2_FLAGS = os.path.join(GRIND, "allocation_v2_flags.jsonl")
PHOTO_LEDGER = os.path.join(ROOT, "photo_ledger_merged.jsonl")
TAKEOUT_LEDGER = os.path.join(ROOT, "takeout_ledger_merged.jsonl")
OUT_FLAGS = os.path.join(GRIND, "repo_dedupe_flags.jsonl")
LOG_PATH = os.path.join(GRIND, "repo_dedupe.log")
THUMBS_SRC_DIR = os.path.join(GRIND, "hash_thumbs_src2")
THUMBS_DIR = os.path.join(GRIND, "hash_thumbs2")
STALE_DIRS = [os.path.join(GRIND, "hash_thumbs"), os.path.join(GRIND, "hash_thumbs_src")]

BATCH = 200
NEAR_HAMMING_THRESHOLD = 8
NEAR_DATE_WINDOW_DAYS = 1
MAX_HASH_FAILURE_RATE = 0.02  # abort if more than 2% of candidates fail to hash


# ---- dHash impl copied from src/image_plane/phash.py (laptop repo) ----
# dhash_hex() is byte-for-byte identical to the source.
# hamming() has ONE change: int.bit_count() is Python >=3.10 only and Mini A
# runs Python 3.9.6 (verified this run: `(5).bit_count()` -> AttributeError).
# bin(x).count("1") is the exact same popcount, just 3.9-safe -- the algorithm
# and its output are unchanged.
def dhash_hex(img):
    """64-bit dHash of an image as a 16-char hex string."""
    grey = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    px = grey.tobytes()  # L mode: one byte per pixel, row-major
    bits = 0
    for row in range(8):
        for col in range(8):
            left = px[row * 9 + col]
            right = px[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}"


def hamming(hex_a, hex_b):
    return bin(int(hex_a, 16) ^ int(hex_b, 16)).count("1")  # py3.9-safe popcount
# ---- end phash.py copy ----


def log(msg):
    line = "{} {}".format(time.strftime("%Y-%m-%dT%H:%M:%S"), msg)
    print(line)
    sys.stdout.flush()
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def is_takeout(p):
    return "takeout" in p.lower()


def load_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def parse_date(s):
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def main():
    log("=== build_repo_dedupe.py start (PYTHONHASHSEED={}) ===".format(os.environ.get("PYTHONHASHSEED")))

    alloc = load_jsonl(ALLOC_V2)
    flag_rows = [d for d in load_jsonl(ALLOC_V2_FLAGS) if not d.get("_meta")]
    flag_paths = {d["path"] for d in flag_rows}

    valid = [d for d in alloc if d.get("job_ref") and d["path"] not in flag_paths]
    log("valid set: {} rows (allocation_v2.jsonl minus allocation_v2_flags.jsonl paths, job_ref required)".format(len(valid)))
    valid_takeout = sum(1 for d in valid if is_takeout(d["path"]))
    log("valid set ledger mix: {} iCloud, {} Takeout".format(len(valid) - valid_takeout, valid_takeout))

    # sha256 lookup: photo_ledger_merged.jsonl (iCloud) + takeout_ledger_merged.jsonl (Takeout)
    sha_by_path = {}
    for d in load_jsonl(PHOTO_LEDGER):
        sha_by_path[d["path"]] = d["sha256"]
    n_icloud_sha = len(sha_by_path)
    for d in load_jsonl(TAKEOUT_LEDGER):
        sha_by_path[d["path"]] = d["sha256"]
    log("sha256 lookup built: {} paths total ({} from photo_ledger_merged.jsonl, {} from takeout_ledger_merged.jsonl)".format(
        len(sha_by_path), n_icloud_sha, len(sha_by_path) - n_icloud_sha))

    missing_sha = [d["path"] for d in valid if d["path"] not in sha_by_path]
    if missing_sha:
        log("WARNING: {} valid rows have no sha256 in either ledger -- skipped for exact-dupe pass. Sample: {}".format(
            len(missing_sha), missing_sha[:3]))
    else:
        log("sha256 coverage: 100% of the valid set")

    out_rows = []

    # ---------- PHASE 1a: EXACT ----------
    groups = defaultdict(list)
    for d in valid:
        sha = sha_by_path.get(d["path"])
        if sha:
            groups[(d["job_ref"], sha)].append(d["path"])

    exact_dupe_paths = set()
    exact_groups = 0
    for (job_ref, sha), paths in groups.items():
        if len(paths) < 2:
            continue
        exact_groups += 1
        ordered = sorted(paths)
        keeper = ordered[0]
        for p in ordered[1:]:
            out_rows.append({
                "path": p,
                "duplicate_of": keeper,
                "kind": "exact",
                "evidence": {"sha256": sha, "job_ref": job_ref, "group_size": len(ordered)},
            })
            exact_dupe_paths.add(p)
    log("PHASE 1a EXACT: {} groups, {} photos collapsed (sha256 match within same job_ref)".format(
        exact_groups, len(exact_dupe_paths)))

    # ---------- PHASE 1b: PRIOR_PASS ----------
    prior_count = 0
    for d in alloc:
        dup = d.get("duplicate_of")
        if not dup:
            continue
        prior_count += 1
        out_rows.append({
            "path": d["path"],
            "duplicate_of": dup,
            "kind": "prior_pass",
            "evidence": {
                "dedupe_status": d.get("dedupe_status"),
                "excluded": d.get("excluded"),
                "prev_job_ref": d.get("prev_job_ref"),
                "job_ref": d.get("job_ref"),
                "imported_from": "allocation_v2.jsonl duplicate_of field (existing verdict, not recomputed)",
            },
        })
    log("PHASE 1b PRIOR_PASS: {} rows imported verbatim from allocation_v2.jsonl (never recomputed)".format(prior_count))

    # ---------- PHASE 1c: POSSIBLE_TWIN ----------
    by_ref_valid = defaultdict(list)
    for d in valid:
        by_ref_valid[d["job_ref"]].append(d)

    possible_twin_count = 0
    for job_ref, rows in by_ref_valid.items():
        ic = [r for r in rows if not is_takeout(r["path"])]
        tk = [r for r in rows if is_takeout(r["path"])]
        if not ic or not tk:
            continue
        icb = defaultdict(list)
        for r in ic:
            icb[os.path.basename(r["path"]).lower()].append(r)
        for t in tk:
            b = os.path.basename(t["path"]).lower()
            for i in icb.get(b, []):
                date_match = "unconfirmed"
                if i.get("date") and t.get("date"):
                    if i["date"] != t["date"]:
                        continue
                    date_match = "exact"
                possible_twin_count += 1
                out_rows.append({
                    "path": t["path"],
                    "duplicate_of": i["path"],
                    "kind": "possible_twin",
                    "evidence": {
                        "basename": b, "job_ref": job_ref,
                        "date_a": i.get("date"), "date_b": t.get("date"),
                        "date_match": date_match,
                        "ledger_a": "icloud", "ledger_b": "takeout",
                        "note": "flag only, never collapsed (IP-L5)",
                    },
                })
    log("PHASE 1c POSSIBLE_TWIN: {} cross-ledger basename+date matches within the valid set "
        "(valid set is currently {} Takeout rows -- see ledger-mix line above)".format(
            possible_twin_count, valid_takeout))

    with open(OUT_FLAGS, "w") as f:
        for r in out_rows:
            f.write(json.dumps(r) + "\n")
    log("PHASE 1 WRITTEN: {} rows -> {}".format(len(out_rows), OUT_FLAGS))

    # ---------- PHASE 2: NEAR ----------
    active = [d for d in valid if d["path"] not in exact_dupe_paths]
    by_ref_active = defaultdict(list)
    for d in active:
        if d.get("date"):
            by_ref_active[d["job_ref"]].append(d)

    pairs = []
    candidate_paths = set()
    for job_ref, rows in by_ref_active.items():
        rows_sorted = sorted(rows, key=lambda r: r["date"])
        n = len(rows_sorted)
        for i in range(n):
            di = parse_date(rows_sorted[i]["date"])
            for j in range(i + 1, n):
                dj = parse_date(rows_sorted[j]["date"])
                if (dj - di).days > NEAR_DATE_WINDOW_DAYS:
                    break
                a, b = rows_sorted[i]["path"], rows_sorted[j]["path"]
                if is_takeout(a) != is_takeout(b):
                    continue  # IP-L5: never pair across ledgers
                pairs.append((a, b))
                candidate_paths.add(a)
                candidate_paths.add(b)

    candidate_paths = sorted(candidate_paths)
    log("PHASE 2 candidate pool: {} photos, {} same-roof same/adjacent-day same-ledger pairs to compare".format(
        len(candidate_paths), len(pairs)))

    os.makedirs(THUMBS_SRC_DIR, exist_ok=True)
    os.makedirs(THUMBS_DIR, exist_ok=True)

    # Collision-proof, batched thumbnailing (see module docstring for the
    # probe evidence): HARDLINK each candidate to a unique name derived from
    # sha256 of the PATH STRING, because sips names --out files after the
    # input basename and resolves symlinks to the target basename. Hardlinks
    # keep their own name; photos + grind are on the same volume (disk3s5).
    def path_key(p):
        return hashlib.sha256(p.encode("utf-8")).hexdigest()[:16]

    key_to_path = {}
    links = []  # (key, link_path)
    missing_on_disk = []
    for p in candidate_paths:
        k = path_key(p)
        if k in key_to_path:
            log("FATAL: path-key collision between {} and {}".format(key_to_path[k], p))
            sys.exit(1)
        key_to_path[k] = p
        if not os.path.exists(p):
            # Known data condition (189 valid-set paths absent on disk as of
            # 2026-07-11): allocation_v2 references a file that is no longer
            # present. NOT a hash failure -- counted and reported separately;
            # the photo simply cannot join the near-dupe pass.
            missing_on_disk.append(p)
            continue
        ext = os.path.splitext(p)[1] or ".jpg"
        link = os.path.join(THUMBS_SRC_DIR, k + ext)
        if not os.path.exists(link):
            try:
                os.link(p, link)  # hardlink: sips keeps THIS basename
            except OSError:
                shutil.copy2(p, link)  # cross-device fallback (not expected)
        links.append((k, link))
    if missing_on_disk:
        log("NOTE: {} candidate photos are MISSING ON DISK (allocation_v2 path has no file) "
            "-- excluded from the near-dupe hash pass, no verdict rows for them. Sample: {}".format(
                len(missing_on_disk), missing_on_disk[:3]))

    total_batches = (len(links) + BATCH - 1) // BATCH
    for bn, bi in enumerate(range(0, len(links), BATCH), start=1):
        chunk = links[bi:bi + BATCH]
        # skip batches whose thumbs all already exist (idempotent rerun)
        todo = [c for c in chunk if not glob.glob(os.path.join(THUMBS_DIR, c[0] + ".*"))]
        if not todo:
            log("sips thumbs: batch {}/{} already cached, skipped".format(bn, total_batches))
            continue
        args = ["sips", "-s", "format", "jpeg", "-Z", "640"] + [c[1] for c in todo] + ["--out", THUMBS_DIR + "/"]
        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode != 0:
            log("WARNING: sips batch {}/{} exit {}: {}".format(bn, total_batches, r.returncode, r.stderr[:300]))
        log("sips thumbs: batch {}/{} done ({}/{})".format(bn, total_batches, min(bi + BATCH, len(links)), len(links)))

    dhash_by_key = {}
    fail = 0
    for n, (k, _) in enumerate(links):
        matches = glob.glob(os.path.join(THUMBS_DIR, k + ".*"))
        if not matches:
            fail += 1
            if fail <= 5:
                log("WARNING: no thumb produced for {} ({})".format(k, key_to_path[k]))
            continue
        try:
            with Image.open(matches[0]) as img:
                dhash_by_key[k] = dhash_hex(img)
        except Exception as e:
            fail += 1
            log("WARNING: dhash failed for {} ({}): {}".format(k, key_to_path[k], e))
        if n and n % 1000 == 0:
            log("dhash progress: {}/{} ({} failures so far)".format(n, len(links), fail))
    log("dHash computed for {}/{} candidate photos ({} failures)".format(len(dhash_by_key), len(links), fail))

    if links and fail / float(len(links)) > MAX_HASH_FAILURE_RATE:
        log("FATAL: dhash failure rate {:.1%} exceeds {:.0%} -- treating as a CRASH, "
            "no near verdicts written, exiting nonzero. The flags file keeps only "
            "phase-1 rows; do NOT treat this run as done.".format(
                fail / float(len(links)), MAX_HASH_FAILURE_RATE))
        sys.exit(1)

    path_to_key = {p: k for k, p in key_to_path.items()}

    # union-find over pairs with hamming <= threshold, same ledger (already filtered above)
    parent = {p: p for p in candidate_paths}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            lo, hi = (ra, rb) if ra < rb else (rb, ra)
            parent[hi] = lo  # deterministic: lexicographically-smaller path wins as root

    evidence_by_path = defaultdict(list)
    near_pairs_used = 0
    sample_pairs = []
    for a, b in pairs:
        ha, hb = dhash_by_key.get(path_to_key.get(a)), dhash_by_key.get(path_to_key.get(b))
        if ha is None or hb is None:
            continue
        d = hamming(ha, hb)
        if d <= NEAR_HAMMING_THRESHOLD:
            union(a, b)
            near_pairs_used += 1
            if len(sample_pairs) < 2:
                sample_pairs.append((a, b, d))
            evidence_by_path[a].append((b, d))
            evidence_by_path[b].append((a, d))
    for a, b, d in sample_pairs:
        log("sample near pair (hamming={}): {} <-> {}".format(d, a, b))

    clusters = defaultdict(list)
    for p in candidate_paths:
        clusters[find(p)].append(p)

    near_rows = []
    for root, members in clusters.items():
        if len(members) < 2:
            continue
        ordered = sorted(members)
        keeper = ordered[0]
        for p in ordered[1:]:
            dist = min((d for _, d in evidence_by_path.get(p, [])), default=None)
            near_rows.append({
                "path": p,
                "duplicate_of": keeper,
                "kind": "near",
                "evidence": {
                    "hamming": dist,
                    "hamming_threshold": NEAR_HAMMING_THRESHOLD,
                    "date_window_days": NEAR_DATE_WINDOW_DAYS,
                    "cluster_size": len(ordered),
                    "method": "dHash-64 (src/image_plane/phash.py), sips 640px thumb",
                },
            })
    near_dupe_count = len(near_rows)
    near_cluster_count = len([m for m in clusters.values() if len(m) > 1])
    log("PHASE 2 NEAR: {} pairs matched (hamming<={}, same roof, date +-{}d, same ledger); "
        "{} clusters, {} photos collapsed".format(
            near_pairs_used, NEAR_HAMMING_THRESHOLD, NEAR_DATE_WINDOW_DAYS, near_cluster_count, near_dupe_count))

    with open(OUT_FLAGS, "a") as f:
        for r in near_rows:
            f.write(json.dumps(r) + "\n")
    log("PHASE 2 APPENDED: {} near rows -> {}".format(len(near_rows), OUT_FLAGS))

    # clean up the poisoned first-run caches (coordinator instruction 2026-07-11):
    # grind/hash_thumbs (basename-collided thumbs) + grind/hash_thumbs_src (symlinks).
    # These are OUR generated caches, never source photos.
    for d in STALE_DIRS:
        if os.path.isdir(d):
            shutil.rmtree(d)
            log("cleaned up stale cache dir {}".format(d))

    total = len(out_rows) + len(near_rows)
    collapsed_paths = {r["path"] for r in out_rows + near_rows if r["kind"] in ("exact", "near")}
    log("valid-set arithmetic: {} valid - {} collapsed (exact+near) = {} keepers surviving; "
        "prior_pass ({}) and possible_twin ({}) rows sit outside/alongside the valid set and collapse nothing here".format(
            len(valid), len(collapsed_paths), len(valid) - len(collapsed_paths), prior_count, possible_twin_count))
    log("=== DONE: {} total verdict rows in {} "
        "(exact={}, prior_pass={}, possible_twin={}, near={}) ===".format(
            total, OUT_FLAGS, len(exact_dupe_paths), prior_count, possible_twin_count, near_dupe_count))


if __name__ == "__main__":
    main()
