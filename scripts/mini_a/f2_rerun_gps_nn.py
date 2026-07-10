#!/usr/bin/env python3
"""F2 M1 step 4 -- rerun gps_nn for the unallocated-GPS keeps against the grown
map. Reuses allocate_global_v3.py's own haversine + band (80/150/300 ->
high/medium/low) + same-postcode-cluster split (resolve_unit) logic verbatim.

HARD RULES enforced:
  - existing 6,563 allocations are NEVER re-matched or overwritten. This script
    only APPENDS new rows for photos that are currently unallocated.
  - weak map entries are excluded from the auto-match candidate pool.
  - genuine ambiguity (two distinct candidate jobs both qualify in-band, not
    resolved by the same-postcode-cluster split) -> excluded, not forced,
    tallied for the Lee sheet.
  - if the grown map would put an ALREADY-allocated photo closer to a
    DIFFERENT job than its current allocation, that is logged to
    grind/f2_conflicts.jsonl and the existing allocation is left untouched.

DRY RUN by default (writes nothing but grind/f2_*_dryrun outputs). Pass --apply
to append to grind/allocation_v2.jsonl and write grind/f2_conflicts.jsonl for real.
"""
import json, os, re, sys, datetime as _dt
from math import radians, sin, cos, asin, sqrt
from collections import defaultdict

IP = os.path.expanduser("~/image-plane")
G = os.path.join(IP, "grind")
APPLY = "--apply" in sys.argv

def nr(x):
    m = re.match(r"\s*0*(\d+)-(\d{2})\b", str(x or ""))
    return f"{m.group(1)}-{m.group(2)}" if m else None

def job_year(ref):
    m = re.match(r"\d+-(\d{2})$", ref or "")
    return 2000 + int(m.group(1)) if m else None

def hav(a, b, c, d):
    R = 6371000.0
    dlat = radians(c - a); dlon = radians(d - b)
    h = sin(dlat/2)**2 + cos(radians(a))*cos(radians(c))*sin(dlon/2)**2
    return 2*R*asin(sqrt(h))

def load_jsonl(p):
    out = []
    with open(p) as f:
        for l in f:
            l = l.strip()
            if not l: continue
            out.append(json.loads(l))
    return out

# ---------- classified keeps + current allocation state ----------
classified = load_jsonl(os.path.join(IP, "classified.jsonl"))
verdicts = {r['path']: r['verdict'] for r in classified}
keeps = set(p for p, v in verdicts.items() if v == 'keep')

alloc_rows = load_jsonl(os.path.join(G, "allocation_v2.jsonl"))
flags_rows = load_jsonl(os.path.join(G, "allocation_v2_flags.jsonl"))
flags_by_path = {}
for r in flags_rows:
    if r.get('_meta'): continue
    flags_by_path[r['path']] = r['flag']

allocated_rows_by_path = {}
allocated_keep_paths = set()
any_prior_row_paths = set()  # ANY row at all, flagged or not -- a path already
# touched by a prior pass (tied, excluded-for-cause, or misfile-corrected to
# job_ref=None) reflects a considered decision. F2 must never re-derive or
# resurrect it -- only grow into paths with ZERO prior allocation_v2.jsonl row.
for r in alloc_rows:
    p = r['path']
    any_prior_row_paths.add(p)
    if p in flags_by_path:
        continue
    allocated_keep_paths.add(p)
    allocated_rows_by_path[p] = r

unallocated_keeps = keeps - allocated_keep_paths

geo_rows = load_jsonl(os.path.join(IP, "geolocations.jsonl"))
gps_all = {}
for r in geo_rows:
    if r.get('lat') is not None and r.get('lon') is not None:
        gps_all[r['path']] = (float(r['lat']), float(r['lon']))

gps_no_job_all = {p: gps_all[p] for p in unallocated_keeps if p in gps_all}
already_touched = set(gps_no_job_all) & any_prior_row_paths
gps_no_job = {p: v for p, v in gps_no_job_all.items() if p not in any_prior_row_paths}
print("target set (unallocated keeps with GPS):", len(gps_no_job_all))
print("  of which already have a prior allocation_v2.jsonl row (excluded-for-cause / "
      "misfile-corrected -- a considered decision, SKIPPED, never re-derived):", len(already_touched))
print("  genuinely untouched -- F2 candidate set:", len(gps_no_job))

# dates for the target photos (best-effort; kept_deduped has dates; classified may not)
dates = {}
kd_path = os.path.join(IP, "kept_deduped.jsonl")
if os.path.exists(kd_path):
    for r in load_jsonl(kd_path):
        if r.get('date'):
            dates[r['path']] = r['date']

# ---------- grown job coord map ----------
raw_coords = json.load(open(os.path.join(G, "job_coords.json")))
# usable candidate pool: exclude 'weak' confidence entries from auto-matching
coords = {}
for ref, v in raw_coords.items():
    conf = v.get("confidence")  # None (pre-existing 198, implicit usable) or exact/strong/likely/weak
    if conf == "weak":
        continue
    coords[ref] = (v["lat"], v["lon"], v.get("site", ""), v.get("source", ""), conf)
print("candidate map (weak excluded):", len(coords), "of", len(raw_coords), "total map entries")

# ---------- Xero invoice dates by job_ref (for same-postcode split resolver) ----------
xero_lines = json.load(open(os.path.join(G, "xero_invoice_lines_full.json")))
inv_dates = defaultdict(list)
for e in xero_lines:
    ref = nr(e.get("tracking_ref"))
    if ref and e.get("date"):
        inv_dates[ref].append(e["date"])

def date_to_ord(s):
    try:
        y, m, dd = s[:10].split("-")
        return _dt.date(int(y), int(m), int(dd)).toordinal()
    except Exception:
        return None

_ord_cache = {ref: [o for o in (date_to_ord(x) for x in ds) if o] for ref, ds in inv_dates.items()}
WIN = 75

def resolve_unit(pdate, cluster):
    units = list(cluster)
    po = date_to_ord(pdate) if pdate else None
    py = int(pdate[:4]) if (pdate and pdate[:4].isdigit()) else None
    if py is not None:
        gated = [u for u in units if (job_year(u) is None or job_year(u) <= py)]
        if gated:
            units = gated
    if len(units) == 1:
        return units[0], "date_split", "medium"
    gaps = {}
    for u in units:
        ods = _ord_cache.get(u, [])
        gaps[u] = min((abs(po - o) for o in ods), default=None) if po is not None else None
    in_win = [u for u in units if gaps[u] is not None and gaps[u] <= WIN]
    if len(in_win) == 1:
        return in_win[0], "date_split", "medium"
    active = [u for u in units if _ord_cache.get(u)]
    if len(active) == 1:
        return active[0], "date_only_active", "low"
    have = [(gaps[u], u) for u in units if gaps[u] is not None]
    if len(have) >= 2:
        have.sort()
        if have[0][0] + 30 < have[1][0]:
            return have[0][1], "date_nearest", "low"
    elif len(have) == 1:
        return have[0][1], "date_nearest", "low"
    return None, None, None

# ---------- same-postcode ambiguity clusters (<=35m), same threshold as v3 ----------
items = list(coords.items())
clusters = []
seen = set()
for i, (ref, (la, lo, s, src, conf)) in enumerate(items):
    if ref in seen: continue
    grp = [ref]; seen.add(ref)
    for ref2, (la2, lo2, s2, src2, conf2) in items[i+1:]:
        if ref2 in seen: continue
        if hav(la, lo, la2, lo2) <= 35:
            grp.append(ref2); seen.add(ref2)
    if len(grp) > 1:
        clusters.append(sorted(grp))
ambiguous_ref = {}
for grp in clusters:
    for ref in grp:
        ambiguous_ref[ref] = grp
print("same-postcode ambiguity clusters in grown map:", len(clusters))

BANDS = [(80, "high"), (150, "medium"), (300, "low")]
coord_list = [(ref, la, lo) for ref, (la, lo, s, src, conf) in coords.items()]

def nearest_two(pla, plo):
    best = None; bd = 1e18; second_ref = None; sd = 1e18
    for ref, la, lo in coord_list:
        dd = hav(pla, plo, la, lo)
        if dd < bd:
            second_ref, sd = best, bd
            best, bd = ref, dd
        elif dd < sd:
            second_ref, sd = ref, dd
    return best, bd, second_ref, sd

new_rows = []
ambiguous_excluded = []
band_tally = defaultdict(int)
tier_tally = defaultdict(int)

for p, (pla, plo) in gps_no_job.items():
    best, bd, second_ref, sd = nearest_two(pla, plo)
    band = None
    for r_, name in BANDS:
        if bd <= r_:
            band = name; break
    if not band:
        continue  # >300m, genuinely no candidate -- residue, not this pass's job

    # ambiguity guard: two DIFFERENT jobs both qualify within band-distance,
    # and they are not the same same-postcode cluster (which has its own
    # resolver below) -> exclude, don't force
    same_cluster = (best in ambiguous_ref and second_ref in ambiguous_ref.get(best, []))
    if (not same_cluster) and second_ref is not None:
        second_band = None
        for r_, name in BANDS:
            if sd <= r_:
                second_band = name; break
        if second_band is not None and (sd - bd) < 40:
            ambiguous_excluded.append({"path": p, "candidates": [[best, round(bd,1)], [second_ref, round(sd,1)]]})
            continue

    row = {"path": p, "job_ref": best, "method": "gps_nn_f2", "dist_m": round(bd, 1),
           "confidence": band, "date": dates.get(p),
           "map_source": coords[best][3], "map_confidence": coords[best][4]}

    if best in ambiguous_ref:
        cluster = ambiguous_ref[best]
        u, meth, conf = resolve_unit(dates.get(p), cluster)
        if u:
            row["job_ref"] = u
            row["method"] = meth + "_f2"
            row["confidence"] = conf
            row["split_from"] = cluster
        else:
            ambiguous_excluded.append({"path": p, "candidates": cluster, "reason": "same_postcode_cluster_unresolved"})
            continue

    new_rows.append(row)
    band_tally[row["confidence"]] += 1
    tier_tally[row["method"]] += 1

print("\nnew allocations (would-append):", len(new_rows))
print("by confidence band:", dict(band_tally))
print("by method:", dict(tier_tally))
print("ambiguous / excluded (not forced):", len(ambiguous_excluded))

# ---------- conflict check for ALREADY-allocated keeps ----------
# Scope: F2 only ADDED 11 new job_coords entries this pass. A "conflict this
# pass creates" means the candidate that wins is one of THOSE 11 new entries --
# not a pre-existing map entry the original allocator already knew about (that
# would be a pre-existing coordinate-drift issue in job_coords.json vs the
# actual centroid-refined coords the original run used internally but never
# persisted -- a real anomaly, but not one F2 created or is in scope to fix;
# reported separately, existing allocations untouched either way).
new_entries_this_pass = set(json.load(open(os.path.join(G, "f2_map_growth_dryrun.json")))["new_entries"].keys())
conflicts = []
preexisting_drift = []
for p in allocated_keep_paths:
    if p not in gps_all:
        continue
    existing = allocated_rows_by_path[p]
    existing_ref = existing.get("job_ref")
    if not existing_ref:
        continue
    pla, plo = gps_all[p]
    best, bd, second_ref, sd = nearest_two(pla, plo)
    if best and best != existing_ref and bd <= 150:
        rec = {"path": p, "existing_job_ref": existing_ref,
               "existing_method": existing.get("method"),
               "existing_dist_m": existing.get("dist_m"),
               "candidate_job_ref": best, "candidate_dist_m": round(bd, 1),
               "candidate_map_source": coords[best][3]}
        if best in new_entries_this_pass:
            conflicts.append(rec)
        else:
            preexisting_drift.append(rec)

print("\nTRUE F2-growth conflicts (candidate is one of THIS pass's new entries):", len(conflicts))
print("pre-existing job_coords.json drift conflicts (NOT F2-caused, reported separately, not applied):", len(preexisting_drift))

out = {
    "target_unallocated_gps": len(gps_no_job),
    "new_allocations": len(new_rows),
    "band_tally": dict(band_tally),
    "method_tally": dict(tier_tally),
    "ambiguous_excluded_count": len(ambiguous_excluded),
    "conflicts_count": len(conflicts),
    "preexisting_drift_conflicts_count": len(preexisting_drift),
}
json.dump(out, open(os.path.join(G, "f2_rerun_summary.json"), "w"), indent=1)
json.dump(ambiguous_excluded, open(os.path.join(G, "f2_ambiguous_excluded.json"), "w"))
json.dump(preexisting_drift, open(os.path.join(G, "f2_preexisting_coord_drift_anomaly.json"), "w"))
print("\nwrote grind/f2_rerun_summary.json, grind/f2_ambiguous_excluded.json, grind/f2_preexisting_coord_drift_anomaly.json")

if APPLY:
    with open(os.path.join(G, "allocation_v2.jsonl"), "a") as fh:
        for r in new_rows:
            fh.write(json.dumps(r) + "\n")
    with open(os.path.join(G, "f2_conflicts.jsonl"), "w") as fh:
        for c in conflicts:
            fh.write(json.dumps(c) + "\n")
    print(f"\nAPPLIED: appended {len(new_rows)} rows to grind/allocation_v2.jsonl")
    print(f"APPLIED: wrote {len(conflicts)} rows to grind/f2_conflicts.jsonl ({len(conflicts)} true F2 conflicts)")
else:
    print("\nDRY RUN -- nothing written to allocation_v2.jsonl. Re-run with --apply to commit.")
