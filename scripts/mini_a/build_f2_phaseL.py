#!/usr/bin/env python3
"""
F2 Phase L -- Lee residue answer sheets (cluster sheets + ambiguous sheet).

Spec: docs/F2-ALLOCATION-FINISH-SPEC-2026-07-10.md Phase L.
Guards: guards.py (F1, mandatory) -- captions only via guards.caption(), footer via
guards.counts_footer(). No new resolver: reuses the exact single-link 150m clustering
algorithm from f2_residual_clusters_v3.py (read, not edited) but ALSO captures photo
membership (v3 only wrote summary stats), and re-derives everything fresh from
allocation_v2.jsonl + geolocations.jsonl + classified.jsonl at build time -- never
trusts f2_residual_summary_v3.json as a data source, only as a comparison point.

Do NOT touch: classified.jsonl, knowledge_notes.jsonl, allocation_v2.jsonl,
photo_ledger_merged.jsonl, index.html, build_site_view_v2.py.
"""
import json, os, re, subprocess, sys, html, datetime
from math import radians, sin, cos, asin, sqrt

IP = os.path.expanduser("~/image-plane")
G = os.path.join(IP, "grind")
SV = os.path.join(G, "site_view")
sys.path.insert(0, IP)
import guards  # noqa: E402

NOW = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


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


# --------------------------------------------------------------------------
# 1. Derive residual set FRESH -- identical method to f2_residual_clusters_v3.py
#    (read that script, not imported -- it has no importable functions, only a
#    top-level script body, so the logic is reproduced verbatim here).
# --------------------------------------------------------------------------
print("=== Deriving fresh from source jsonl/json files ===")

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
coords = [(v["lat"], v["lon"]) for v in job_coords.values() if v.get("confidence") != "weak"]

# --------------------------------------------------------------------------
# 1b. F2 CANDIDATE PASS (2026-07-10 late) -- loaded here (not in section 7) because
#     both cluster pages AND ambiguous.html need name resolution + candidate
#     rendering. Sources are read-only quarantine files from Step 1+2 of the
#     candidate-pass chain (f2_candidate_engine.py / f2_trello_sweep.py) -- this
#     builder NEVER writes to them.
# --------------------------------------------------------------------------
site_names = load_json(os.path.join(G, "site_names.json"), {})
gra_stories = load_json(os.path.join(G, "gra_stories.json"), {})
f2_candidates = load_json(os.path.join(G, "f2_candidates.json"), {})
f2_trello_quarantine = load_json(os.path.join(G, "f2_trello_quarantine.json"), {})
xero_lines = load_json(os.path.join(G, "xero_invoice_lines_full.json"), [])
trello_by_ref = {r["job_ref"]: r for r in f2_trello_quarantine.get("rows", []) if r.get("job_ref")}
candidates_by_cluster = {c["cluster_id"]: c for c in f2_candidates.get("clusters", [])}
candidates_by_amb_path = {a["path"]: a for a in f2_candidates.get("ambiguous_photos", [])}

far = []
for p, (pla, plo) in gps_no_job.items():
    bd = min(hav(pla, plo, la, lo) for la, lo in coords)
    if bd > 2000:
        far.append(p)

# single-link 150m clustering -- SAME algorithm as f2_residual_clusters_v3.py, but
# capture membership (paths), not just counts.
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
singletons = sum(1 for c in clusters if len(c) == 1)
top20 = clusters[:20]

fresh = {
    "residual_gps_no_job": len(gps_no_job),
    "far_gt_2km": len(far),
    "clusters": len(clusters),
    "singletons": singletons,
    "top20_sizes": [len(c) for c in top20],
    "top20_photo_count": sum(len(c) for c in top20),
}
fresh["top20_pct_of_tail"] = round(100 * fresh["top20_photo_count"] / len(far), 1) if far else None

print(json.dumps(fresh, indent=1))

# --------------------------------------------------------------------------
# 2. Validate against v3 summary file AND against counts.py --json
# --------------------------------------------------------------------------
v3 = load_json(os.path.join(G, "f2_residual_summary_v3.json"), {})
print("\n=== Fresh vs f2_residual_summary_v3.json ===")
diffs_v3 = []
for k in ("residual_gps_no_job", "far_gt_2km", "clusters", "singletons", "top20_photo_count"):
    a, b = fresh.get(k), v3.get(k)
    same = a == b
    print(f"  {k}: fresh={a} v3={b} {'MATCH' if same else 'DIFF'}")
    if not same:
        diffs_v3.append(k)
same_sizes = fresh.get("top20_sizes") == v3.get("top20_sizes")
print(f"  top20_sizes: {'MATCH' if same_sizes else 'DIFF'}")
if not same_sizes:
    diffs_v3.append("top20_sizes")

print("\n=== Fresh vs counts.py --json ===")
try:
    proc = subprocess.run(["python3", os.path.join(IP, "counts.py"), "--json"],
                           capture_output=True, text=True, timeout=60)
    counts_json = json.loads(proc.stdout)
    cp_val = counts_json.get("unallocated_gps_no_job", {}).get("value")
    same_cp = cp_val == fresh["residual_gps_no_job"]
    print(f"  unallocated_gps_no_job: fresh={fresh['residual_gps_no_job']} counts.py={cp_val} "
          f"{'MATCH' if same_cp else 'DIFF'}")
except Exception as e:
    print(f"  counts.py --json FAILED: {e}")
    same_cp = False

# --------------------------------------------------------------------------
# 3. Per-photo date/time helpers
# --------------------------------------------------------------------------
_mdls_cache = {}


def path_date(p):
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", p)
    if m:
        return "%s-%s-%s" % m.groups()
    return None


def creation_datetime(p):
    """mdls kMDItemContentCreationDate, cached; falls back to path date only."""
    if p in _mdls_cache:
        return _mdls_cache[p]
    d = path_date(p)
    result = {"date": d, "time": None}
    if os.path.exists(p):
        try:
            out = subprocess.run(["mdls", "-name", "kMDItemContentCreationDate", "-raw", p],
                                  capture_output=True, text=True, timeout=10).stdout.strip()
            m = re.match(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})", out)
            if m:
                y, mo, da, hh, mm, ss = m.groups()
                result["date"] = f"{y}-{mo}-{da}"
                result["time"] = f"{hh}:{mm}"
        except Exception:
            pass
    _mdls_cache[p] = result
    return result


def fmt_date_human(d):
    if not d:
        return "date unknown"
    try:
        dt = datetime.datetime.strptime(d, "%Y-%m-%d")
        return dt.strftime("%-d %b %Y")
    except Exception:
        return d


def sort_key(p):
    dt = creation_datetime(p)
    return (dt["date"] or "9999", dt["time"] or "99:99", p)


# --------------------------------------------------------------------------
# 4. Thumbnail generation (sips, CPU only) + verification
# --------------------------------------------------------------------------
THUMB_PASS = []
THUMB_FAIL = []


def make_thumb(src, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 5000:
        with open(dest, "rb") as f:
            if f.read(3) == b"\xff\xd8\xff":
                THUMB_PASS.append(dest)
                return True, "cached_ok"
    if not os.path.exists(src):
        THUMB_FAIL.append((dest, "source_missing_on_disk"))
        return False, "source_missing_on_disk"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        subprocess.run(
            ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85", "-Z", "1400",
             src, "--out", dest],
            check=True, capture_output=True, timeout=30,
        )
    except Exception as e:
        THUMB_FAIL.append((dest, "sips_error:%s" % e))
        return False, "sips_error"
    if not os.path.exists(dest):
        THUMB_FAIL.append((dest, "no_output_file"))
        return False, "no_output_file"
    sz = os.path.getsize(dest)
    with open(dest, "rb") as f:
        magic = f.read(3)
    ok = magic == b"\xff\xd8\xff" and sz > 5000
    if ok:
        THUMB_PASS.append(dest)
        return True, "ok"
    THUMB_FAIL.append((dest, "magic=%s size=%d" % (magic.hex(), sz)))
    return False, "bad_output"


# --------------------------------------------------------------------------
# 5. Shared CSS (adapted from closeup-retest-r1.html -- guards-compatible classes)
# --------------------------------------------------------------------------
CSS = """
:root { color-scheme: dark; }
body {
  background:#0f0f10; color:#e8e8e8; margin:0; padding:0 0 80px;
  font:16px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;
}
.wrap { max-width:1180px; margin:0 auto; padding:0 20px; }
.banner {
  background:#1a2333; border-left:5px solid #7fb0e8; padding:16px 18px;
  margin:18px 0 18px; border-radius:0 8px 8px 0;
}
.banner h1 { font-size:20px; margin:0 0 8px; font-weight:700; color:#cfe0f5; }
.banner p { margin:0 0 8px; color:#e8e8e8; font-size:15.5px; }
.banner .stat { color:#7fd18b; font-weight:650; }
a { color:inherit; }
.row { border-top:1px solid #262626; padding:28px 0; }
.row:first-of-type { border-top:none; }
.rowhead { display:flex; align-items:center; gap:12px; margin-bottom:10px; flex-wrap:wrap; }
.badge {
  display:inline-flex; align-items:center; justify-content:center;
  min-width:44px; height:44px; border-radius:9px;
  background:#1c2b22; color:#7fd18b; font-weight:800; font-size:20px;
  font-variant-numeric:tabular-nums;
}
.meta { color:#9aa; font-size:14px; }
.photowrap { display:block; width:100%; margin-bottom:8px; }
.photowrap img { display:block; width:100%; max-width:100%; height:auto; border-radius:8px; background:#1a1a1a; }
.filename { color:#8a9; font-size:13px; margin-top:2px; }
.missing { color:#e0837e; font-size:14px; padding:24px; background:#1a1414; border-radius:8px; text-align:center; }
.caption { background:#141c14; border-left:4px solid #7fd18b; border-radius:0 6px 6px 0; padding:8px 12px; margin:6px 0 12px; font-size:14px; color:#dfe8df; }
.caption-label { color:#7fd18b; font-weight:700; text-transform:uppercase; font-size:11px; letter-spacing:.03em; margin-right:6px; }
.candidates { display:flex; flex-direction:column; gap:8px; margin:10px 0 16px; }
.candidate { background:#181818; border-radius:8px; padding:10px 14px; }
.candidate b { color:#dfe; }
.candidate .addr { color:#9aa; font-size:13.5px; }
.candidate .caveat { color:#e0c168; }
.candidate-none { color:#9aa; }
.candidate-none b { color:#9aa; }
.zero-candidates { color:#dfe8df; font-style:italic; }
.ask { background:#20191a; border-left:4px solid #e0c168; border-radius:0 6px 6px 0; padding:12px 14px; margin-top:12px; font-size:15px; }
.ask b { color:#f0d68a; }
.reprow { display:flex; gap:16px; align-items:flex-start; flex-wrap:wrap; }
.repimg { flex:0 0 320px; max-width:100%; }
.repimg img { width:100%; border-radius:8px; display:block; background:#1a1a1a; }
.repinfo { flex:1 1 260px; min-width:220px; }
.repinfo h3 { margin:0 0 8px; font-size:17px; color:#dfe; }
.repinfo .stat-line { color:#9aa; font-size:14px; margin-bottom:4px; }
.repinfo a.openlink { display:inline-block; margin-top:10px; color:#7fd18b; font-weight:650; text-decoration:none; border:1px solid #2a3a2f; border-radius:6px; padding:8px 14px; }
.repinfo a.openlink:hover { background:#152018; }
.counts-footer { margin:30px auto 0; max-width:1180px; padding:14px 18px; border-top:1px solid #262626; color:#9aa; font-size:12.5px; }
.counts-footer .counted-by, .counts-footer .counted-at { color:#767b80; }
.counts-footer-error { color:#e0837e; }
"""

os.makedirs(os.path.join(SV, "cluster_thumbs"), exist_ok=True)
os.makedirs(os.path.join(SV, "ambiguous_thumbs"), exist_ok=True)

# --------------------------------------------------------------------------
# 5b. F2 candidate-pass rendering helpers (2026-07-10 late).
#
# Name resolution fallback chain (binding, per F2-CANDIDATE-PASS-SPEC-2026-07-10
# STEP 3): candidate's own `label` if it's already a real name/postcode -> NEVER
# accept the placeholder "Job NNN-NN (name unknown)" as a real label -> site_names
# .json -> gra_stories.json -> Trello evidence card address (stripped of leading
# ref + trailing person name) -> job_coords.json postcode-area -> (extra honesty
# net, not in the original chain but required so we never render a bare code)
# Xero invoice contact name -> final honest "no name or address on file".
# --------------------------------------------------------------------------
_PLACEHOLDER_RE = re.compile(r"^Job [\w\-]+ \(name unknown\)$")
_UK_POSTCODE_RE = re.compile(r"\b[A-Z]{1,2}\d[A-Z0-9]?\s*\d[A-Z]{2}\b", re.I)
_ADDRESS_WORDS = {
    "house", "road", "rd", "street", "st", "lane", "ln", "way", "drive", "dr",
    "court", "ct", "park", "close", "ave", "avenue", "farm", "cottage", "barn",
    "lodge", "hall", "grange", "villa", "building", "mews", "gardens", "garden",
    "terrace", "place", "pl", "grove", "rise", "view", "walk", "green", "croft",
    "fold", "yard", "crescent", "square", "sq", "row", "end", "hill", "bridge",
    "common", "fields", "field", "manor",
}


def _looks_like_person_name(seg):
    words = [w for w in re.split(r"\s+", seg.strip()) if w]
    if not (1 < len(words) <= 4):
        return False
    if re.search(r"\d", seg):
        return False
    if _UK_POSTCODE_RE.search(seg):
        return False
    lw = [re.sub(r"[^a-zA-Z]", "", w).lower() for w in words]
    if any(w in _ADDRESS_WORDS for w in lw if w):
        return False
    return all(w[:1].isupper() for w in words if w)


def derive_trello_address(card_name):
    """Best-effort: 'NNNN-YY Address bits, Town, County POSTCODE, Person Name'
    -> 'Address bits, Town' (drops postcode segment + trailing person name).
    Heuristic, documented as such -- these are provisional candidates, never
    written back anywhere."""
    if not card_name:
        return None
    segs = [s.strip() for s in card_name.split(",") if s.strip()]
    if not segs:
        return None
    # Strip leading numeric ref + an optional compound sub-ref suffix, e.g.
    # "289-14-M Peter Elias" -> ref-strip must eat "289-14-M " as one unit, not
    # just "289-14 ", or a stray "-M " fragment survives onto the remainder.
    segs[0] = re.sub(r"^\s*\d{2,4}-\d{2}(?:-[A-Za-z])?\s*", "", segs[0]).strip()
    if not segs[0]:
        segs = segs[1:]
    if not segs:
        return None
    # Pop trailing segments while they're EITHER postcode-bearing OR look like a
    # person's name -- these interleave in real card names ("..., County POSTCODE,
    # Person Name"), so a single combined loop is needed (two separate loops each
    # only look at the current last segment once and miss the postcode segment
    # once a trailing person-name segment is popped after it).
    while len(segs) > 1 and (_UK_POSTCODE_RE.search(segs[-1]) or _looks_like_person_name(segs[-1])):
        segs.pop()
    if not segs:
        return None
    if len(segs) == 1:
        # Single-segment card names (no commas) are either a real address/site
        # nickname ("Cliffe/Firle/Hub - UoB") or just a contact's name with no
        # address at all ("Peter Elias (Infinity Foods)"). Strip any trailing
        # parenthetical aside before judging -- if the remaining core reads as a
        # person's name, this card carries no usable address, so say so and let
        # the caller fall through to the next fallback tier (job_coords, then a
        # job-ref-wide Xero contact search) rather than showing a person's name
        # dressed up as an address.
        seg = segs[0]
        core = re.sub(r"\s*\([^)]*\)\s*$", "", seg).strip() or seg
        if _looks_like_person_name(core):
            return None
        return seg
    if segs[0] == segs[-1]:
        return segs[0]
    return "%s, %s" % (segs[0], segs[-1])


def resolve_job_display(job_ref, cand):
    """Returns (display_string_plain_text, source_tag) for spot-check/audit."""
    label = (cand.get("label") or "").strip()
    if label and not _PLACEHOLDER_RE.match(label):
        return label, "candidate_label"
    sn = site_names.get(job_ref)
    if sn and sn.get("name"):
        return "%s (%s)" % (sn["name"], job_ref), "site_names"
    gs = gra_stories.get(job_ref)
    if gs and gs.get("site"):
        nm = gs["site"].get("name") or gs["site"].get("address")
        if nm:
            return "%s (%s)" % (nm, job_ref), "gra_stories"
    tr = trello_by_ref.get(job_ref)
    if tr:
        for ec in tr.get("evidence_cards", []):
            addr = derive_trello_address(ec.get("card_name"))
            if addr:
                return "%s (%s)" % (addr, job_ref), "trello"
    jc = job_coords.get(job_ref)
    if jc:
        site = (jc.get("site") or "").strip()
        postcode = jc.get("postcode")
        bits = [b for b in (site, postcode) if b]
        if bits:
            return "%s (%s)" % (" — ".join(bits), job_ref), "job_coords"
    # Job-ref-wide Xero contact search (not gated to this specific candidate's
    # own evidence_source -- if ANY invoice line for this job carries a contact
    # name, use it; that's still more honest than a bare code, and the caller
    # never treats it as more than "billed to").
    contact = xero_contact_by_ref.get(job_ref)
    if contact:
        return "Job %s — billed to %s (address not on file)" % (job_ref, contact), "xero_contact"
    return "Job %s — no name or address on file" % job_ref, "none"


_RESOLVE_SOURCE_TALLY = {}
xero_contact_by_ref = {}
for _row in xero_lines:
    _ref = _row.get("tracking_ref")
    _contact = _row.get("contact")
    if _ref and _contact and _ref not in xero_contact_by_ref:
        xero_contact_by_ref[_ref] = _contact


def render_evidence_sentence(cand):
    raw = (cand.get("evidence_raw_text") or "").strip()
    raw = (raw[0].upper() + raw[1:]) if raw else "Matches this date"
    dist = cand.get("distance_km")
    if dist is not None:
        raw += (", %dm away" % round(dist * 1000)) if dist < 1 else (", %.1fkm away" % dist)
    raw = raw.rstrip(".") + "."
    out = html.escape(raw)
    if cand.get("strength") == "weak-wide-window":
        out += (
            " <span class='caveat'>Possible but thin &mdash; this job was invoiced or "
            "active on and off over a long stretch, so the date overlap may be "
            "coincidence.</span>"
        )
    return out


def render_candidate_options_html(cands):
    """cands: list of up to 3 ranked candidate dicts from f2_candidates.json.
    Returns an HTML block: numbered say-able options, last option ALWAYS
    'None of these / other'. Returns None if cands is empty (caller renders
    the zero-candidate message instead)."""
    if not cands:
        return None
    items = []
    for i, cand in enumerate(cands, start=1):
        job_ref = cand["job_ref"]
        display, src = resolve_job_display(job_ref, cand)
        _RESOLVE_SOURCE_TALLY[src] = _RESOLVE_SOURCE_TALLY.get(src, 0) + 1
        ev_sentence = render_evidence_sentence(cand)
        items.append(
            "<div class='candidate'><b>%d.</b> <b>%s</b><br><span class='addr'>%s</span></div>"
            % (i, html.escape(display), ev_sentence)
        )
    last_n = len(cands) + 1
    items.append(
        "<div class='candidate candidate-none'><b>%d.</b> None of these / other &mdash; just say what it is.</div>"
        % last_n
    )
    return "<div class='candidates'>%s</div>" % "".join(items)


def render_zero_candidates_html(context):
    msg = (
        "No invoice or board activity matches this cluster&rsquo;s dates &mdash; dictate freely."
        if context == "cluster"
        else "No invoice or board activity matches this date &mdash; dictate freely."
    )
    return "<div class='candidates'><div class='candidate zero-candidates'>%s</div></div>" % msg


# --------------------------------------------------------------------------
# 6. Build cluster-01.html .. cluster-20.html + cluster-sheets-r1.html index
# --------------------------------------------------------------------------
index_rows_html = []
scaffold = {}

for ci, members in enumerate(top20, start=1):
    cnum = "%02d" % ci
    members_sorted = sorted(members, key=sort_key)
    total_n = len(members_sorted)
    days = sorted(set(creation_datetime(p)["date"] or "unknown" for p in members_sorted))
    n_days = len(days)
    date_lo, date_hi = days[0], days[-1]

    # pick up to 15 spanning the full range
    k = min(15, total_n)
    if total_n <= 15:
        sample = members_sorted
    else:
        idxs = sorted(set(round(i * (total_n - 1) / (k - 1)) for i in range(k)))
        sample = [members_sorted[i] for i in idxs]

    rep = sample[len(sample) // 2]

    rows_html = []
    for n, p in enumerate(sample, start=1):
        dest = os.path.join(SV, "cluster_thumbs", "c%s" % cnum, "%02d.jpg" % n)
        ok, why = make_thumb(p, dest)
        dt = creation_datetime(p)
        d_h = fmt_date_human(dt["date"])
        t_h = dt["time"] or "time unknown"
        fname = os.path.basename(p)
        cap = guards.caption({"path": p, "job_ref": None})
        cap_html = cap.render_html()
        if ok:
            img_rel = "cluster_thumbs/c%s/%02d.jpg" % (cnum, n)
            photo_html = (
                "<a class='photowrap' href='%s' target='_blank' rel='noopener'>"
                "<img loading='lazy' src='%s' alt='Photo %d, cluster %s'></a>"
                % (html.escape(img_rel), html.escape(img_rel), n, cnum)
            )
        else:
            photo_html = "<div class='missing'>Photo file not currently on this machine (%s)</div>" % html.escape(why)
        rows_html.append(
            "<div class='row' id='row-%d'>"
            "<div class='rowhead'><span class='badge'>%d</span>"
            "<span class='meta'>%s &middot; %s</span></div>"
            "%s"
            "<div class='filename'>%s</div>"
            "%s"
            "</div>"
            % (n, n, html.escape(d_h), html.escape(t_h), photo_html, html.escape(fname), cap_html)
        )

    shown_note = ""
    if total_n > 15:
        shown_note = "<p>Showing 15 of %d photos, spread across the whole date range.</p>" % total_n

    cluster_entry = candidates_by_cluster.get(ci)
    cluster_cands = cluster_entry["candidates"] if cluster_entry else []
    if cluster_cands:
        cand_block_html = render_candidate_options_html(cluster_cands)
    else:
        cand_block_html = render_zero_candidates_html("cluster")

    header_p = (
        "<p>These %d photos were taken close together on %d different days, "
        "but they don&rsquo;t match any roof I have a location for. Have a look at the "
        "candidates below, worked out from invoices and the jobs board.</p>"
        "<p><b>How to answer:</b> if one of the numbered options below is right, just say "
        "its number in any Claude window &mdash; &ldquo;cluster %d is 2&rdquo;. If none of "
        "them fit, say &ldquo;cluster %d is none of these&rdquo; and tell me what it actually "
        "is, or give a name/job number outright &mdash; &ldquo;cluster %d is Litten "
        "Path&rdquo; &middot; &ldquo;cluster %d not a job&rdquo;. Dictation is fine; I capture "
        "it from there.</p>"
        % (total_n, n_days, ci, ci, ci, ci)
    )

    page_html = """<!doctype html>
<meta charset="utf-8">
<title>Cluster %s -- which roof is this?</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>%s</style>
<div class="wrap">
<div class="banner">
  <h1>Cluster %d of 20 &mdash; %d photos, %s to %s</h1>
  %s
  %s
</div>
%s
</div>
<div id="counts-footer-slot">%s</div>
""" % (
        cnum, CSS, ci, total_n, fmt_date_human(date_lo), fmt_date_human(date_hi),
        header_p, cand_block_html, shown_note + "\n".join(rows_html), guards.counts_footer(),
    )

    out_path = os.path.join(SV, "cluster-%s.html" % cnum)
    with open(out_path, "w") as f:
        f.write(page_html)

    # index row
    rep_dest = os.path.join(SV, "cluster_thumbs", "c%s" % cnum, "%02d.jpg" % (sample.index(rep) + 1))
    rep_rel = "cluster_thumbs/c%s/%02d.jpg" % (cnum, sample.index(rep) + 1)
    if os.path.exists(rep_dest) and os.path.getsize(rep_dest) > 5000:
        rep_img_html = "<img loading='lazy' src='%s' alt='Representative photo, cluster %s'>" % (
            html.escape(rep_rel), cnum)
    else:
        rep_img_html = "<div class='missing'>no photo on disk</div>"

    index_rows_html.append(
        "<div class='row'><div class='reprow'>"
        "<div class='repimg'>%s</div>"
        "<div class='repinfo'><h3>Cluster %d</h3>"
        "<div class='stat-line'>%d photos</div>"
        "<div class='stat-line'>%s &ndash; %s (%d separate days)</div>"
        "<a class='openlink' href='cluster-%s.html'>Open cluster %d</a>"
        "</div></div></div>"
        % (rep_img_html, ci, total_n, fmt_date_human(date_lo), fmt_date_human(date_hi), n_days, cnum, ci)
    )

    scaffold[str(ci)] = {"job_ref": None, "name": None, "note": None, "not_a_job": False}

index_html = """<!doctype html>
<meta charset="utf-8">
<title>20 photo clusters -- which roofs are these?</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>%s</style>
<div class="wrap">
<div class="banner">
  <h1>20 groups of photos that don&rsquo;t match any roof I have a location for</h1>
  <p>These are photos with a GPS position, taken close together in time and place, more than
  2km from any roof address on file. Grouped into the 20 biggest clusters &mdash; open each one
  and say which roof or site it is, or that it isn&rsquo;t a job at all.</p>
  <p><b>What I need from you:</b> open each group, glance at the photos, and just tell me
  &mdash; out loud or typed, in any Claude window, in any order, as few or as many as you like:
  &ldquo;cluster 4 is Litten Path&rdquo; &middot; &ldquo;cluster 7 not a job&rdquo; &middot;
  &ldquo;cluster 12 is 1479-21&rdquo;. That&rsquo;s the whole job &mdash; same dictation loop as
  the photo rounds you&rsquo;ve done before. I capture your words as ground truth and the photos
  get filed to their roofs. Nothing here needs typing into a form.</p>
</div>
%s
</div>
<div id="counts-footer-slot">%s</div>
""" % (CSS, "\n".join(index_rows_html), guards.counts_footer())

with open(os.path.join(SV, "cluster-sheets-r1.html"), "w") as f:
    f.write(index_html)

with open(os.path.join(G, "f2_cluster_answers_template.json"), "w") as f:
    json.dump(scaffold, f, indent=1)

print("\n=== Cluster pages built: cluster-sheets-r1.html + cluster-01..20.html ===")

# --------------------------------------------------------------------------
# 7. ambiguous.html -- membership + candidates now come straight from
#    f2_candidates.json's `ambiguous_photos` (Step 1+2 of the candidate-pass
#    chain already derived this exact 33-photo set from the same
#    f2_ambiguous_excluded*.json files -- verified identical path-set before
#    this rewrite, see F2-CANDIDATE-PASS-SPEC-2026-07-10.md STEP 3).
# --------------------------------------------------------------------------
unique_paths = sorted(candidates_by_amb_path.keys(), key=sort_key)
print("\n=== Ambiguous sweep ===")
print("unique photos (from f2_candidates.json ambiguous_photos): %d" % len(unique_paths))

amb_rows_html = []
zero_cand_count = 0
for n, p in enumerate(unique_paths, start=1):
    dest = os.path.join(SV, "ambiguous_thumbs", "%03d.jpg" % n)
    ok, why = make_thumb(p, dest)
    dt = creation_datetime(p)
    d_h = fmt_date_human(dt["date"])
    t_h = dt["time"] or "time unknown"
    fname = os.path.basename(p)
    cap = guards.caption({"path": p, "job_ref": None})
    cap_html = cap.render_html()

    amb_cands = candidates_by_amb_path[p].get("candidates", [])
    if amb_cands:
        cand_block_html = render_candidate_options_html(amb_cands)
        last_n = len(amb_cands) + 1
        ask = (
            "<div class='ask'><b>Which one is this?</b> Say the number &mdash; 1 to %d &mdash; "
            "or say &lsquo;%d&rsquo; for none of these / other.</div>" % (len(amb_cands), last_n)
        )
    else:
        zero_cand_count += 1
        cand_block_html = render_zero_candidates_html("ambiguous")
        ask = ""

    if ok:
        img_rel = "ambiguous_thumbs/%03d.jpg" % n
        photo_html = (
            "<a class='photowrap' href='%s' target='_blank' rel='noopener'>"
            "<img loading='lazy' src='%s' alt='Ambiguous photo %d'></a>"
            % (html.escape(img_rel), html.escape(img_rel), n)
        )
    else:
        photo_html = "<div class='missing'>Photo file not currently on this machine (%s)</div>" % html.escape(why)

    amb_rows_html.append(
        "<div class='row' id='amb-%d'>"
        "<div class='rowhead'><span class='badge'>%d</span>"
        "<span class='meta'>%s &middot; %s</span></div>"
        "%s"
        "<div class='filename'>%s</div>"
        "%s"
        "%s"
        "%s"
        "</div>"
        % (n, n, html.escape(d_h), html.escape(t_h), photo_html, html.escape(fname), cap_html,
           cand_block_html, ask)
    )

amb_html = """<!doctype html>
<meta charset="utf-8">
<title>Ambiguous photos -- which roof is it?</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>%s</style>
<div class="wrap">
<div class="banner">
  <h1>%d photos caught between two or more neighbouring roofs</h1>
  <p>Each of these sits close to more than one roof address, so the computer can&rsquo;t pick
  one safely. Have a look at the candidates below each photo, worked out from invoices and
  the jobs board.</p>
  <p><b>How to answer:</b> by the photo numbers, in any Claude window &mdash;
  &ldquo;ambiguous 3 is 1&rdquo; &middot; &ldquo;ambiguous 9 is none of these&rdquo;.
  Dictation is fine.</p>
</div>
%s
</div>
<div id="counts-footer-slot">%s</div>
""" % (CSS, len(unique_paths), "\n".join(amb_rows_html), guards.counts_footer())

with open(os.path.join(SV, "ambiguous.html"), "w") as f:
    f.write(amb_html)

print("ambiguous photos with zero candidates (say so plainly, dictate freely): %d" % zero_cand_count)
print("name resolution source tally (cluster + ambiguous candidates):", _RESOLVE_SOURCE_TALLY)

# --------------------------------------------------------------------------
# 8. Thumbnail verification summary
# --------------------------------------------------------------------------
print("\n=== Thumbnail verification ===")
print("pass: %d" % len(THUMB_PASS))
print("fail: %d" % len(THUMB_FAIL))
for d, why in THUMB_FAIL[:20]:
    print("  FAIL:", d, why)

print("\n=== Done. Fresh totals, diffs, thumb counts printed above. ===")
print("v3 diffs:", diffs_v3 if diffs_v3 else "none")
print("counts.py match:", same_cp)
