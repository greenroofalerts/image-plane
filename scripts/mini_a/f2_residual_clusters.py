#!/usr/bin/env python3
"""Post-F2 residual: cluster the remaining unallocated-GPS keeps, report how
many are still >2km from ANY mapped job (Lee-sheet candidates, next phase)."""
import json, os, re
from math import radians, sin, cos, asin, sqrt

IP = os.path.expanduser("~/image-plane")
G = os.path.join(IP, "grind")

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
            if l:
                out.append(json.loads(l))
    return out

classified = load_jsonl(os.path.join(IP, "classified.jsonl"))
verdicts = {r['path']: r['verdict'] for r in classified}
keeps = set(p for p, v in verdicts.items() if v == 'keep')

alloc_rows = load_jsonl(os.path.join(G, "allocation_v2.jsonl"))
flags_rows = load_jsonl(os.path.join(G, "allocation_v2_flags.jsonl"))
flags_by_path = {r['path']: r['flag'] for r in flags_rows if not r.get('_meta')}
allocated_keep_paths = set(r['path'] for r in alloc_rows if r['path'] not in flags_by_path)
unallocated_keeps = keeps - allocated_keep_paths

geo_rows = load_jsonl(os.path.join(IP, "geolocations.jsonl"))
gps_all = {r['path']: (float(r['lat']), float(r['lon'])) for r in geo_rows if r.get('lat') is not None}
gps_no_job = {p: gps_all[p] for p in unallocated_keeps if p in gps_all}
print("residual gps-but-no-job (post-F2):", len(gps_no_job))

raw = json.load(open(os.path.join(G, "job_coords.json")))
coords = [(v["lat"], v["lon"]) for v in raw.values() if v.get("confidence") != "weak"]

far = []
for p, (pla, plo) in gps_no_job.items():
    bd = min(hav(pla, plo, la, lo) for la, lo in coords)
    if bd > 2000:
        far.append(p)
print(">2km from any mapped job:", len(far))

# single-link cluster the >2km tail at 150m
used = set()
clusters = []
flist = far
posmap = gps_no_job
for i, p in enumerate(flist):
    if p in used: continue
    la, lo = posmap[p]; grp = [p]; used.add(p)
    for q in flist[i+1:]:
        if q in used: continue
        la2, lo2 = posmap[q]
        if hav(la, lo, la2, lo2) <= 150:
            grp.append(q); used.add(q)
    clusters.append(grp)
clusters.sort(key=len, reverse=True)
singles = sum(1 for c in clusters if len(c) == 1)
print("distinct clusters in >2km tail:", len(clusters))
print("singleton clusters:", singles)
print("top 15 cluster sizes:", [len(c) for c in clusters[:15]])
top20_photos = sum(len(c) for c in clusters[:20])
print("photos in top-20 clusters:", top20_photos, f"({100*top20_photos/len(far):.1f}% of tail)" if far else "")

json.dump({"residual_gps_no_job": len(gps_no_job), "far_gt_2km": len(far),
           "clusters": len(clusters), "singletons": singles,
           "top15_sizes": [len(c) for c in clusters[:15]]},
          open(os.path.join(G, "f2_residual_summary.json"), "w"), indent=1)
print("wrote grind/f2_residual_summary.json")
