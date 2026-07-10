#!/usr/bin/env python3
"""
F2 candidate engine -- STEP 1 of docs/F2-CANDIDATE-PASS-SPEC-2026-07-10.md.

Derives the residual clusters FRESH using the IDENTICAL algorithm as
build_f2_phaseL.py (read, not edited, not imported -- it has no importable
functions). Then, per cluster and per ambiguous photo, finds dated-job
candidates from three local sources (Xero invoice lines, roof_invoice_match,
gra_stories) and scores them by date-overlap tightness + proximity.

Output: grind/f2_candidates.json (quarantine -- provisional, never promoted,
never written as ties, never merged into the map -- IP-L9).

NO writes to allocation_v2.jsonl, job_coords.json, knowledge_notes.jsonl,
counts.py, guards.py. No external network calls. Photo bytes never leave
this machine (script only reads paths/metadata, not pixel bytes).
"""
import json, os, re, subprocess, sys, datetime
from math import radians, sin, cos, asin, sqrt

IP = os.path.expanduser("~/image-plane")
G = os.path.join(IP, "grind")

EXPECTED_TOP20_SIZES = [67, 66, 52, 37, 35, 34, 30, 30, 29, 28, 27, 25, 22, 21, 21, 18, 18, 18, 18, 17]


def hav(a, b, c, d):
    R = 6371000.0
    dlat = radians(c - a)
    dlon = radians(d - b)
    h = sin(dlat / 2) ** 2 + cos(radians(a)) * cos(radians(c)) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(h))


def load_jsonl(p):
    out = []
    with open(p) as f:
        for l in f:
            l = l.strip()
            if l:
                out.append(json.loads(l))
    return out


def load_json(p, default=None):
    if not os.path.exists(p):
        return default
    try:
        return json.load(open(p))
    except Exception:
        return default


# ---------------------------------------------------------------------------
# 1. Derive residual clusters FRESH -- verbatim copy of build_f2_phaseL.py's
#    section 1 (lines ~60-117 in that file). Do not edit that builder.
# ---------------------------------------------------------------------------
print("=== Deriving fresh residual clusters (identical algorithm to build_f2_phaseL.py) ===")

classified = load_jsonl(os.path.join(IP, "classified.jsonl"))
verdicts = {r["path"]: r["verdict"] for r in classified}
keeps = set(p for p, v in verdicts.items() if v == "keep")

alloc_rows = load_jsonl(os.path.join(G, "allocation_v2.jsonl"))
flags_rows = load_jsonl(os.path.join(G, "allocation_v2_flags.jsonl"))
flags_by_path = {r["path"]: r["flag"] for r in flags_rows if not r.get("_meta")}
allocated_keep_paths = set(r["path"] for r in alloc_rows if r["path"] not in flags_by_path)
unallocated_keeps = keeps - allocated_keep_paths

geo_rows = load_jsonl(os.path.join(IP, "geolocations.jsonl"))
gps_all = {r["path"]: (float(r["lat"]), float(r["lon"])) for r in geo_rows if r.get("lat") is not None}
gps_no_job = {p: gps_all[p] for p in unallocated_keeps if p in gps_all}

job_coords = load_json(os.path.join(G, "job_coords.json"), {})
coords_strong = [(v["lat"], v["lon"]) for v in job_coords.values() if v.get("confidence") != "weak"]

far = []
for p, (pla, plo) in gps_no_job.items():
    bd = min(hav(pla, plo, la, lo) for la, lo in coords_strong)
    if bd > 2000:
        far.append(p)

used = set()
clusters = []
flist = far
posmap = gps_no_job
for i, p in enumerate(flist):
    if p in used:
        continue
    la, lo = posmap[p]
    grp = [p]
    used.add(p)
    for q in flist[i + 1:]:
        if q in used:
            continue
        la2, lo2 = posmap[q]
        if hav(la, lo, la2, lo2) <= 150:
            grp.append(q)
            used.add(q)
    clusters.append(grp)
clusters.sort(key=len, reverse=True)
top20 = clusters[:20]
top20_sizes = [len(c) for c in top20]

print("clusters total:", len(clusters))
print("top20_sizes:", top20_sizes)

# ---------------------------------------------------------------------------
# Sanity gate: must match the sizes the builder actually produced last run
# (read from grind/site_view/cluster-01..20.html banners -- the template file
# grind/f2_cluster_answers_template.json only carries the answer scaffold,
# not sizes, so the HTML banners are the size source of truth).
# ---------------------------------------------------------------------------
if top20_sizes != EXPECTED_TOP20_SIZES:
    print("SANITY GATE FAILED: derived top20_sizes != builder's last-produced sizes")
    print("  derived: ", top20_sizes)
    print("  expected:", EXPECTED_TOP20_SIZES)
    sys.exit(1)
print("SANITY GATE PASSED: top20 sizes match build_f2_phaseL.py's last run exactly.\n")

# assert: cluster membership is residual by construction -- no member path is
# an already-allocated-keep path.
for ci, members in enumerate(top20, start=1):
    bad = [p for p in members if p in allocated_keep_paths]
    assert not bad, "cluster %d contains already-allocated paths: %s" % (ci, bad)
print("ASSERT PASSED: no cluster member path is already allocated to a job.\n")

# ---------------------------------------------------------------------------
# 2. Per-photo date helper -- IDENTICAL source/fallback as build_f2_phaseL.py
#    (mdls kMDItemContentCreationDate, cached, falls back to path date).
# ---------------------------------------------------------------------------
_mdls_cache = {}


def path_date(p):
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", p)
    if m:
        return "%s-%s-%s" % m.groups()
    return None


def creation_date(p):
    if p in _mdls_cache:
        return _mdls_cache[p]
    d = path_date(p)
    source = "path_date"
    if os.path.exists(p):
        try:
            out = subprocess.run(["mdls", "-name", "kMDItemContentCreationDate", "-raw", p],
                                  capture_output=True, text=True, timeout=10).stdout.strip()
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", out)
            if m:
                d = "%s-%s-%s" % m.groups()
                source = "exif_mdls"
        except Exception:
            pass
    else:
        source = "path_date_missing_on_disk"
    _mdls_cache[p] = (d, source)
    return (d, source)


def parse_d(s):
    if not s:
        return None
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def fmt_human(d):
    dt = parse_d(d)
    return dt.strftime("%-d %b %Y") if dt else (d or "date unknown")


# ---------------------------------------------------------------------------
# 3. Load dated job-event sources (all local, per spec STEP 1.3).
# ---------------------------------------------------------------------------
print("=== Loading dated job-event sources ===")

xero_lines = load_json(os.path.join(G, "xero_invoice_lines_full.json"), [])
roof_matches = load_jsonl(os.path.join(G, "roof_invoice_match.jsonl"))
gra_stories = load_json(os.path.join(G, "gra_stories.json"), {})
site_names = load_json(os.path.join(G, "site_names.json"), {})

print("xero_invoice_lines_full.json rows:", len(xero_lines))
print("roof_invoice_match.jsonl rows:", len(roof_matches))
print("gra_stories.json job_refs:", len(gra_stories))
print("job_coords.json job_refs:", len(job_coords))
print("site_names.json job_refs:", len(site_names))

# events[job_ref] = [ {date, evidence_text, source_file, source_index} ]
events = {}


def add_event(job_ref, date, evidence_text, source_file, source_index):
    if not job_ref or not date:
        return
    events.setdefault(job_ref, []).append({
        "date": date, "evidence_text": evidence_text,
        "source_file": source_file, "source_index": source_index,
    })


for i, r in enumerate(xero_lines):
    tr = r.get("tracking_ref")
    d = r.get("date")
    if not tr or not d:
        continue
    ev = "invoiced %s (%s)" % (fmt_human(d), (r.get("description") or r.get("reference") or "").strip()[:60])
    add_event(tr, d, ev, "grind/xero_invoice_lines_full.json", i)

for i, r in enumerate(roof_matches):
    band = r.get("band")
    if band not in ("exact", "strong", "likely"):
        continue
    jr = r.get("job_ref")
    d = r.get("event_start")
    ev = "visit %s, %s match (%s)" % (fmt_human(d), band, ",".join(r.get("evidence") or [])[:60])
    add_event(jr, d, ev, "grind/roof_invoice_match.jsonl", i)

gra_items = list(gra_stories.items())
for i, (jr, rec) in enumerate(gra_items):
    for s in (rec.get("stories") or []):
        d = s.get("date")
        ev = "%s: %s" % (s.get("title") or s.get("kind") or "visit", fmt_human(d))
        add_event(jr, d, ev, "grind/gra_stories.json", i)

print("job_refs with >=1 dated event:", len(events))
n_ev = sum(len(v) for v in events.values())
print("total dated events across all sources:", n_ev, "\n")


def ref_variants(ref):
    """Handle mixed zero-padding across sources (e.g. '996-19' vs '0996-19')."""
    out = {ref}
    m = re.match(r"^(\d+)-(\d+)$", ref)
    if m:
        num, yr = m.groups()
        out.add(num.zfill(4) + "-" + yr)
        out.add(str(int(num)) + "-" + yr)
    return out


def resolve_name(job_ref):
    """site_names.json -> gra_stories.json -> job_coords.json (site/postcode).
    Never returns a bare code alone -- always paired with whatever address
    fragment is available, or an explicit 'no address on file' marker."""
    for cand in ref_variants(job_ref):
        sn = site_names.get(cand)
        if sn and sn.get("name"):
            return sn["name"], True
    for cand in ref_variants(job_ref):
        gs = gra_stories.get(cand)
        if gs and gs.get("site"):
            nm = gs["site"].get("name") or gs["site"].get("address")
            if nm:
                return nm, True
    for cand in ref_variants(job_ref):
        jc = job_coords.get(cand)
        if jc:
            site = (jc.get("site") or "").strip()
            if site:
                return site, True
    return None, False


def resolve_coords(job_ref):
    for cand in ref_variants(job_ref):
        jc = job_coords.get(cand)
        if jc and jc.get("lat") is not None:
            return jc["lat"], jc["lon"], jc.get("confidence")
    return None, None, None


# ---------------------------------------------------------------------------
# 4. Candidate scoring per STEP 1.4.
#    date_score  = 14 - min distance in days from event date to the cluster's
#                  actual date span (capped 0..14; window already filters to
#                  +/-14d of the span so this is always in range).
#    prox_score  = max(0, 2 - dist_km) * 7  (0km -> 14, 2km -> 0), only when
#                  the job has coords on file; otherwise omitted (no penalty,
#                  no credit -- proximity leg simply doesn't apply, per spec
#                  wording "(where the job has coords ...)").
#    total_score = date_score + (prox_score or 0)
# ---------------------------------------------------------------------------

def date_distance_days(event_date, lo, hi):
    ed = parse_d(event_date)
    dlo, dhi = parse_d(lo), parse_d(hi)
    if not ed or not dlo or not dhi:
        return None
    if dlo <= ed <= dhi:
        return 0
    return min(abs((ed - dlo).days), abs((ed - dhi).days))


def score_candidate(job_ref, best_event, dist_km):
    date_dist = best_event["_date_dist"]
    date_score = max(0, 14 - date_dist)
    if dist_km is not None:
        prox_score = max(0, 2 - dist_km) * 7
    else:
        prox_score = 0
    return date_score + prox_score


def build_candidates_for_window(lo, hi, centroid=None, date_only=False):
    """Returns ranked list of up to 3 candidate dicts for a date window
    [lo,hi] already expanded +/-14d, optionally checked against a centroid
    (lat,lon) when not date_only."""
    scored = []
    for job_ref, evs in events.items():
        best = None
        for e in evs:
            dd = date_distance_days(e["date"], lo, hi)
            if dd is None:
                continue
            if best is None or dd < best["_date_dist"]:
                best = dict(e)
                best["_date_dist"] = dd
        if best is None:
            continue
        dist_km = None
        conf = None
        if not date_only and centroid is not None:
            jla, jlo, conf = resolve_coords(job_ref)
            if jla is not None:
                dist_km = hav(centroid[0], centroid[1], jla, jlo) / 1000.0
                if dist_km > 2.0:
                    continue  # proximity leg fails when coords ARE on file
        sc = score_candidate(job_ref, best, dist_km)
        scored.append({
            "job_ref": job_ref, "score": round(sc, 2),
            "date_distance_days": best["_date_dist"],
            "distance_km": round(dist_km, 3) if dist_km is not None else None,
            "coords_confidence": conf,
            "best_event": best,
        })
    scored.sort(key=lambda c: (-c["score"], c["date_distance_days"],
                                c["distance_km"] if c["distance_km"] is not None else 999))
    return scored[:3]


def evidence_line(cand, date_only):
    name, has_name = resolve_name(cand["job_ref"])
    label = "%s (%s)" % (name, cand["job_ref"]) if has_name else "Job %s (no address on file)" % cand["job_ref"]
    ev = cand["best_event"]["evidence_text"]
    if date_only:
        line = "%s -- %s" % (label, ev)
    elif cand["distance_km"] is not None:
        line = "%s -- %s, %.1fkm away" % (label, ev, cand["distance_km"])
    else:
        line = "%s -- %s, distance unknown (no coords on file)" % (label, ev)
    return line, label, has_name


# ---------------------------------------------------------------------------
# 5. Per-cluster candidates.
# ---------------------------------------------------------------------------
print("=== Scoring cluster candidates ===")
cluster_out = []
zero_candidate_clusters = []

for ci, members in enumerate(top20, start=1):
    dates = []
    date_sources = {"exif_mdls": 0, "path_date": 0, "path_date_missing_on_disk": 0}
    for p in members:
        d, src = creation_date(p)
        date_sources[src] = date_sources.get(src, 0) + 1
        if d:
            dates.append(d)
    dates_sorted = sorted(dates)
    lo_actual, hi_actual = dates_sorted[0], dates_sorted[-1]
    lo_win = (parse_d(lo_actual) - datetime.timedelta(days=14)).isoformat()
    hi_win = (parse_d(hi_actual) + datetime.timedelta(days=14)).isoformat()

    lats = [gps_no_job[p][0] for p in members]
    lons = [gps_no_job[p][1] for p in members]
    centroid = (sum(lats) / len(lats), sum(lons) / len(lons))

    cands = build_candidates_for_window(lo_win, hi_win, centroid=centroid, date_only=False)
    ranked = []
    for c in cands:
        line, label, has_name = evidence_line(c, date_only=False)
        ranked.append({
            "job_ref": c["job_ref"], "site_name_resolved": has_name, "label": label,
            "score": c["score"], "date_distance_days": c["date_distance_days"],
            "distance_km": c["distance_km"], "coords_confidence": c["coords_confidence"],
            "evidence_line": line,
            "evidence_source": {"file": c["best_event"]["source_file"], "index": c["best_event"]["source_index"]},
            "evidence_raw_text": c["best_event"]["evidence_text"],
        })

    rec = {
        "cluster_id": ci, "photo_count": len(members),
        "date_span_actual": {"lo": lo_actual, "hi": hi_actual},
        "date_span_window_used": {"lo": lo_win, "hi": hi_win},
        "date_sources": date_sources,
        "centroid": {"lat": round(centroid[0], 6), "lon": round(centroid[1], 6)},
        "candidates": ranked,
    }
    cluster_out.append(rec)
    if not ranked:
        zero_candidate_clusters.append(ci)
    print("cluster %2d: %3d photos, %s to %s, %d candidate(s)" %
          (ci, len(members), lo_actual, hi_actual, len(ranked)))

print("\nzero-candidate clusters:", zero_candidate_clusters or "none")

# ---------------------------------------------------------------------------
# 6. Ambiguous photos: date-only candidates, per STEP 1.5.
#    Membership = union of the 3 f2_ambiguous_excluded*.json files, deduped
#    by path -- identical merge to build_f2_phaseL.py section 7.
# ---------------------------------------------------------------------------
print("\n=== Scoring ambiguous-photo candidates (date-only) ===")
raw_files = ["f2_ambiguous_excluded.json", "f2_ambiguous_excluded_m3.json", "f2_ambiguous_excluded_m4.json"]
merged_amb = {}
raw_total = 0
for fn in raw_files:
    rows = load_json(os.path.join(G, fn), [])
    raw_total += len(rows)
    for r in rows:
        merged_amb.setdefault(r["path"], True)
unique_amb_paths = sorted(merged_amb.keys())
print("raw ambiguous rows across 3 files: %d, unique photos after dedupe: %d" % (raw_total, len(unique_amb_paths)))

amb_out = []
zero_candidate_amb = []
for p in unique_amb_paths:
    d, src = creation_date(p)
    if not d:
        amb_out.append({
            "path": p, "date": None, "date_source": src,
            "candidates": [], "note": "no derivable date (no EXIF, no path date)",
        })
        zero_candidate_amb.append(p)
        continue
    lo_win = (parse_d(d) - datetime.timedelta(days=14)).isoformat()
    hi_win = (parse_d(d) + datetime.timedelta(days=14)).isoformat()
    cands = build_candidates_for_window(lo_win, hi_win, centroid=None, date_only=True)
    ranked = []
    for c in cands:
        line, label, has_name = evidence_line(c, date_only=True)
        ranked.append({
            "job_ref": c["job_ref"], "site_name_resolved": has_name, "label": label,
            "score": c["score"], "date_distance_days": c["date_distance_days"],
            "date_only": True,
            "evidence_line": line,
            "evidence_source": {"file": c["best_event"]["source_file"], "index": c["best_event"]["source_index"]},
            "evidence_raw_text": c["best_event"]["evidence_text"],
        })
    if not ranked:
        zero_candidate_amb.append(p)
    amb_out.append({
        "path": p, "date": d, "date_source": src,
        "date_window_used": {"lo": lo_win, "hi": hi_win},
        "candidates": ranked,
    })

print("ambiguous photos with >=1 date-only candidate:", len(unique_amb_paths) - len(zero_candidate_amb))
print("ambiguous photos with zero candidates:", len(zero_candidate_amb))

# ---------------------------------------------------------------------------
# 7. Write quarantine output. ONLY file written besides this script.
# ---------------------------------------------------------------------------
out = {
    "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "provisional": True,
    "note": "IP-L9: candidates are provisional. Never promoted, never written as "
            "ties, never merged into allocation_v2.jsonl or job_coords.json without "
            "Lee's explicit answer.",
    "sanity_gate": {"top20_sizes_expected": EXPECTED_TOP20_SIZES, "top20_sizes_derived": top20_sizes, "match": True},
    "clusters": cluster_out,
    "zero_candidate_clusters": zero_candidate_clusters,
    "ambiguous_photos": amb_out,
    "zero_candidate_ambiguous_count": len(zero_candidate_amb),
}
out_path = os.path.join(G, "f2_candidates.json")
with open(out_path, "w") as f:
    json.dump(out, f, indent=1)
print("\nWrote", out_path)
