#!/usr/bin/env python3
"""F2 M1 step 3 investigation: why are the 86 <=150m-from-a-mapped-job photos
still unallocated? Read-only, no writes. Run on Mini A."""
import json, os, re
from math import radians, sin, cos, asin, sqrt

IP = os.path.expanduser("~/image-plane")
G = os.path.join(IP, "grind")

def nr(x):
    m = re.match(r"\s*0*(\d+)-(\d{2})\b", str(x or ""))
    return f"{m.group(1)}-{m.group(2)}" if m else None

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

# --- reproduce counts.py's keeps / allocated_keep_paths / unallocated split ---
classified = load_jsonl(os.path.join(IP, "classified.jsonl"))
verdicts = {r['path']: r['verdict'] for r in classified}
keeps = set(p for p, v in verdicts.items() if v == 'keep')

alloc_rows = load_jsonl(os.path.join(G, "allocation_v2.jsonl"))
flags_rows = load_jsonl(os.path.join(G, "allocation_v2_flags.jsonl"))
flags_by_path = {}
for r in flags_rows:
    if r.get('_meta'): continue
    flags_by_path[r['path']] = r['flag']

allocated_keep_paths = set()
alloc_row_by_path = {}
for r in alloc_rows:
    p = r['path']
    alloc_row_by_path[p] = r
    if p in flags_by_path:
        continue
    allocated_keep_paths.add(p)

unallocated_keeps = keeps - allocated_keep_paths

geo = load_jsonl(os.path.join(IP, "geolocations.jsonl"))
gps_all = {}
for r in geo:
    if r.get('lat') is not None and r.get('lon') is not None:
        gps_all[r['path']] = (float(r['lat']), float(r['lon']))

gps_no_job = set(p for p in unallocated_keeps if p in gps_all)
print("unallocated_keeps:", len(unallocated_keeps))
print("gps_no_job (derived):", len(gps_no_job))

# --- current job map ---
coords = json.load(open(os.path.join(G, "job_coords.json")))
coord_list = [(ref, v['lat'], v['lon']) for ref, v in coords.items()]
print("map size:", len(coord_list))

# --- distance <=150m from nearest mapped job, among gps_no_job ---
close86 = []
for p in gps_no_job:
    pla, plo = gps_all[p]
    best = None; bd = 1e18
    for ref, la, lo in coord_list:
        dd = hav(pla, plo, la, lo)
        if dd < bd:
            bd = dd; best = ref
    if bd <= 150:
        close86.append((p, best, round(bd, 1)))

print("close86 count (should be ~86):", len(close86))

# --- classify WHY each is unallocated ---
# 1. is the path in kept_deduped.jsonl (the survivors set the matcher actually uses)?
survivors = set()
kd_path = os.path.join(IP, "kept_deduped.jsonl")
if os.path.exists(kd_path):
    for r in load_jsonl(kd_path):
        survivors.add(r['path'])
print("kept_deduped.jsonl rows:", len(survivors))

reasons = {}
detail = []
for p, ref, dist in close86:
    in_survivors = p in survivors
    in_alloc_rows_at_all = p in alloc_row_by_path
    flag = flags_by_path.get(p)
    row = alloc_row_by_path.get(p)
    reason = None
    if not in_survivors:
        reason = "not_in_kept_deduped_survivors_set"
    elif flag == 'excluded':
        reason = "excluded_flag:" + str(row.get('excluded') if row else None)
    elif flag == 'non_keep_path':
        reason = "non_keep_path_flag"
    elif flag == 'no_job_ref':
        reason = "no_job_ref_flag"
    elif row is not None and row.get('needs_lee'):
        reason = "needs_lee_ambiguous_cluster"
    elif row is None:
        reason = "never_produced_a_row_by_matcher_despite_survivor(band>300m_from_ITS_OWN_coords_snapshot_or_dup_path_key)"
    else:
        reason = "unexplained_has_row_but_flagged_unallocated"
    reasons[reason] = reasons.get(reason, 0) + 1
    detail.append({"path": p, "nearest_job": ref, "dist_m": dist, "reason": reason,
                    "in_survivors": in_survivors, "matcher_row": row})

print(json.dumps(reasons, indent=2))

with open(os.path.join(G, "f2_investigate_86.json"), "w") as f:
    json.dump({"close86_count": len(close86), "reasons": reasons, "detail": detail}, f, indent=1)
print("wrote", os.path.join(G, "f2_investigate_86.json"))
