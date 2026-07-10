#!/usr/bin/env python3
"""F2 M3 (map-merge pass) -- rerun gps_nn for the unallocated-GPS keeps against the
map grown by TODAY's merge (job_coords.json 209 -> 377). Copy of f2_rerun_gps_nn.py
(F2-M1's script) verbatim except for three deltas required by this pass's spec:
  1. method tag suffix changed _f2 -> _f2m3 (gps_nn_f2m3 / date_split_f2m3 /
     date_only_active_f2m3 / date_nearest_f2m3) so this pass's rows are
     distinguishable from F2-M1's.
  2. date is derived strictly from the path's /YYYY/MM/DD/ segment (regex),
     falling back to kept_deduped.jsonl's own path-derived date only as a
     cross-check; a photo where NEITHER yields a valid date is NEVER written --
     it goes to residue (grind/f2_undatable_residue_m3.json).
  3. "conflict this pass creates" is scoped to THIS pass's actual new map
     entries (diffed live against grind/job_coords.json.pre_merge_20260710),
     not F2-M1's f2_map_growth_dryrun.json (which only knows about F2-M1's own
     11 additions and would misattribute every conflict here).

Same hard rules as F2-M1: existing allocation_v2.jsonl rows (any prior row,
flagged or not) are NEVER re-derived; weak map entries excluded from
auto-matching; genuine ambiguity excluded not forced; conflicts reported not
overwritten.

DRY RUN by default. Pass --apply to append to grind/allocation_v2.jsonl and
write grind/f2_conflicts_m3.jsonl for real.
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

PATH_DATE_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")

def derive_date_from_path(path):
    m = PATH_DATE_RE.search(path)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return _dt.date(y, mo, d).isoformat()
    except ValueError:
        return None

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
any_prior_row_paths = set()
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
print("  of which already have a prior allocation_v2.jsonl row (SKIPPED, never re-derived):", len(already_touched))
print("  genuinely untouched -- M3 candidate set:", len(gps_no_job))

# dates: strict path-derived (spec requirement); kept_deduped date used only as
# a cross-check fallback when the path itself doesn't parse (rare / defensive).
kd_dates = {}
kd_path = os.path.join(IP, "kept_deduped.jsonl")
if os.path.exists(kd_path):
    for r in load_jsonl(kd_path):
        if r.get('date'):
            kd_dates[r['path']] = r['date']

def resolve_date(path):
    d = derive_date_from_path(path)
    if d:
        return d
    return kd_dates.get(path)  # fallback only; still may be None -> residue

# ---------- grown job coord map ----------
raw_coords = json.load(open(os.path.join(G, "job_coords.json")))
coords = {}
for ref, v in raw_coords.items():
    conf = v.get("confidence")
    if conf == "weak":
        continue
    coords[ref] = (v["lat"], v["lon"], v.get("site", ""), v.get("source", ""), conf)
print("candidate map (weak excluded):", len(coords), "of", len(raw_coords), "total map entries")

# ---------- Xero invoice dates by job_ref (same-postcode split resolver) ----------
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

# ---------- same-postcode ambiguity clusters (<=35m) ----------
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
undatable_residue = []
band_tally = defaultdict(int)
tier_tally = defaultdict(int)

for p, (pla, plo) in gps_no_job.items():
    best, bd, second_ref, sd = nearest_two(pla, plo)
    band = None
    for r_, name in BANDS:
        if bd <= r_:
            band = name; break
    if not band:
        continue  # >300m -- residue, not this pass's job (spatial residue, separate report)

    same_cluster = (best in ambiguous_ref and second_ref in ambiguous_ref.get(best, []))
    if (not same_cluster) and second_ref is not None:
        second_band = None
        for r_, name in BANDS:
            if sd <= r_:
                second_band = name; break
        if second_band is not None and (sd - bd) < 40:
            ambiguous_excluded.append({"path": p, "candidates": [[best, round(bd,1)], [second_ref, round(sd,1)]]})
            continue

    pdate = resolve_date(p)
    if not pdate:
        undatable_residue.append({"path": p, "candidate_job_ref": best, "dist_m": round(bd, 1)})
        continue  # undatable -- NEVER written, goes to residue per spec

    row = {"path": p, "job_ref": best, "method": "gps_nn_f2m3", "dist_m": round(bd, 1),
           "confidence": band, "date": pdate,
           "map_source": coords[best][3], "map_confidence": coords[best][4]}

    if best in ambiguous_ref:
        cluster = ambiguous_ref[best]
        u, meth, conf = resolve_unit(pdate, cluster)
        if u:
            row["job_ref"] = u
            row["method"] = meth + "_f2m3"
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
print("undatable residue (never written):", len(undatable_residue))

# ---------- conflict check, scoped to THIS pass's actual new map entries ----------
pre_merge_coords = json.load(open(os.path.join(G, "job_coords.json.pre_merge_20260710")))
new_entries_this_pass = set(raw_coords.keys()) - set(pre_merge_coords.keys())
print("this pass's new map entries (live diff vs pre_merge backup):", len(new_entries_this_pass))

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

print("\nTRUE M3-growth conflicts (candidate is one of THIS pass's new entries):", len(conflicts))
print("pre-existing job_coords.json drift conflicts (NOT this pass's doing, reported separately, not applied):", len(preexisting_drift))

out = {
    "target_unallocated_gps": len(gps_no_job),
    "new_allocations": len(new_rows),
    "band_tally": dict(band_tally),
    "method_tally": dict(tier_tally),
    "ambiguous_excluded_count": len(ambiguous_excluded),
    "undatable_residue_count": len(undatable_residue),
    "conflicts_count": len(conflicts),
    "preexisting_drift_conflicts_count": len(preexisting_drift),
    "new_map_entries_this_pass": len(new_entries_this_pass),
}
json.dump(out, open(os.path.join(G, "f2_rerun_summary_m3.json"), "w"), indent=1)
json.dump(ambiguous_excluded, open(os.path.join(G, "f2_ambiguous_excluded_m3.json"), "w"), indent=1)
json.dump(undatable_residue, open(os.path.join(G, "f2_undatable_residue_m3.json"), "w"), indent=1)
json.dump(preexisting_drift, open(os.path.join(G, "f2_preexisting_coord_drift_anomaly_m3.json"), "w"), indent=1)
print("\nwrote grind/f2_rerun_summary_m3.json, f2_ambiguous_excluded_m3.json, f2_undatable_residue_m3.json, f2_preexisting_coord_drift_anomaly_m3.json")

if APPLY:
    with open(os.path.join(G, "allocation_v2.jsonl"), "a") as fh:
        for r in new_rows:
            fh.write(json.dumps(r) + "\n")
    with open(os.path.join(G, "f2_conflicts_m3.jsonl"), "w") as fh:
        for c in conflicts:
            fh.write(json.dumps(c) + "\n")
    print(f"\nAPPLIED: appended {len(new_rows)} rows to grind/allocation_v2.jsonl")
    print(f"APPLIED: wrote {len(conflicts)} rows to grind/f2_conflicts_m3.jsonl ({len(conflicts)} true M3 conflicts)")
else:
    print("\nDRY RUN -- nothing written to allocation_v2.jsonl. Re-run with --apply to commit.")
