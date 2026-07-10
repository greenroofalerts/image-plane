#!/usr/bin/env python3
"""
F2 Trello sweep -- STEP 2 of docs/F2-CANDIDATE-PASS-SPEC-2026-07-10.md.

Phase A: pulls ALL Trello boards (incl. closed) and all cards per board, extracts
job refs / UK postcodes / address-looking lines / dates, geocodes postcodes via
postcodes.io, diffs against grind/job_coords.json (419 refs), writes
grind/f2_trello_quarantine.json (source: "trello"; job_coords.json is NEVER touched).

Phase B: rescores grind/f2_candidates.json (Step 1 output) using the IDENTICAL
residual-cluster derivation as f2_candidate_engine.py / build_f2_phaseL.py, now
with:
  (a) Trello card dates counted as job-activity evidence (evidence line names the
      board, operator English -- "due 12 Jul 2024, on the OR MAIN board that
      month").
  (b) Trello-geocoded coords used in the proximity leg for jobs that gain them --
      candidates within 2km score up; candidates whose new coords put them >2km
      away are DROPPED from the ranked list and logged in "trello_distance_dropped"
      on the cluster record, with the evidence line saying why.
  (c) a `strength` field: "tight" (cluster date span <=60 days) vs
      "weak-wide-window" (cluster span >60 days OR the candidate job invoices
      continuously over >1 year with >=5 dated events).
  (d) the Step-1 label bug fixed: job_coords.json "site" values that are raw
      known_entities provenance text (e.g. "known_entities postcode-bearing...")
      are NEVER shown as a name -- fall back to postcode, else
      "Job NNNN-YY (name unknown)".

v1 is backed up to grind/f2_candidates.json.v1 before v2 is written in place.

NO writes to allocation_v2.jsonl, job_coords.json, knowledge_notes.jsonl,
counts.py, guards.py. Only external calls: api.trello.com, api.postcodes.io.
Photo bytes never touched/leave this machine (this script only reads dates,
paths, and job-ref text -- no pixels).
"""
import os
import sys

# IP-L6: pin PYTHONHASHSEED before any set/dict-iteration-order-sensitive work
# (clustering below iterates over dict/set derived path collections).
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execvpe(sys.executable, [sys.executable] + sys.argv, os.environ)

import json
import re
import time
import datetime
import shutil
from math import radians, sin, cos, asin, sqrt

try:
    from dateutil import parser as dateutil_parser
except Exception:
    dateutil_parser = None

import requests

IP = os.path.expanduser("~/image-plane")
G = os.path.join(IP, "grind")
ENV_PATH = os.path.expanduser("~/leeos-brain/.env")

CANDIDATES_PATH = os.path.join(G, "f2_candidates.json")
CANDIDATES_V1_PATH = os.path.join(G, "f2_candidates.json.v1")
QUARANTINE_PATH = os.path.join(G, "f2_trello_quarantine.json")

EXPECTED_TOP20_SIZES = [67, 66, 52, 37, 35, 34, 30, 30, 29, 28, 27, 25, 22, 21, 21, 18, 18, 18, 18, 17]


# ---------------------------------------------------------------------------
# shared helpers (verbatim logic from f2_candidate_engine.py where noted)
# ---------------------------------------------------------------------------
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


def ref_variants(ref):
    out = {ref}
    m = re.match(r"^(\d+)-(\d+)$", ref)
    if m:
        num, yr = m.groups()
        out.add(num.zfill(4) + "-" + yr)
        out.add(str(int(num)) + "-" + yr)
    return out


def is_raw_provenance(text):
    """Guard against the Step-1 label bug: job_coords.json 'site' values sourced
    from known_entities carry raw provenance text (e.g. 'known_entities
    postcode-bearing non-repeated address (contact/entity: Derek Wood)'). Never
    show that as a display name."""
    if not text:
        return False
    t = text.lower()
    return t.startswith("known_entities") or "(contact/entity:" in t


# ===========================================================================
# PHASE A -- Trello sweep
# ===========================================================================
print("=" * 70)
print("PHASE A: Trello sweep")
print("=" * 70)


def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


env = load_env(ENV_PATH)
TRELLO_KEY = env.get("TRELLO_API_KEY")
TRELLO_TOKEN = env.get("TRELLO_TOKEN")
if not TRELLO_KEY or not TRELLO_TOKEN:
    print("FATAL: TRELLO_API_KEY/TRELLO_TOKEN not found in", ENV_PATH)
    sys.exit(1)

SESSION = requests.Session()


def trello_get(path, params, max_retries=3):
    params = dict(params)
    params["key"] = TRELLO_KEY
    params["token"] = TRELLO_TOKEN
    url = "https://api.trello.com" + path
    err = None
    for attempt in range(1, max_retries + 1):
        try:
            r = SESSION.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json(), None
            err = "HTTP %s: %s" % (r.status_code, r.text[:200])
        except Exception as e:
            err = str(e)
        time.sleep(0.8 * attempt)
    return None, err


boards, err = trello_get("/1/members/me/boards", {"fields": "name,closed", "filter": "all"})
if boards is None:
    print("FATAL: could not list boards after 3 retries:", err)
    sys.exit(1)
print("boards found (incl. closed):", len(boards))

all_cards = []
consecutive_fail = 0
boards_scanned = 0
boards_failed = []
for b in boards:
    bid, bname, bclosed = b["id"], b["name"], b.get("closed", False)
    cards, err = trello_get(
        "/1/boards/%s/cards/all" % bid,
        {"fields": "name,desc,due,dateLastActivity,labels,closed,shortUrl"},
    )
    if cards is None:
        consecutive_fail += 1
        boards_failed.append({"board_id": bid, "board_name": bname, "error": err})
        print("  FAILED board %-40s : %s" % (bname[:40], err))
        if consecutive_fail >= 3:
            print("\nFATAL: 3 consecutive board pulls failed. STOPPING per chain-wide law "
                  "(3 fails = STOP, report the wall, do not improvise). No output written.")
            sys.exit(1)
        continue
    consecutive_fail = 0
    boards_scanned += 1
    for c in cards:
        c["_board_id"] = bid
        c["_board_name"] = bname
        c["_board_closed"] = bclosed
        all_cards.append(c)
    print("  %-40s %4d cards (closed=%s)" % (bname[:40], len(cards), bclosed))
    time.sleep(0.3)

print("\nboards_scanned: %d / %d" % (boards_scanned, len(boards)))
print("boards_failed:", len(boards_failed))
print("total cards pulled:", len(all_cards))

# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------
JOB_REF_RE = re.compile(r"\b\d{2,4}-\d{2}\b")


def plausible_job_ref(ref):
    """Sanity filter against regex noise (dates, quarter labels, prices written
    as NN-NN that coincidentally match \\d{2,4}-\\d{2}). The real job-ref corpus
    (job_coords.json, 419 refs) only ever carries a 2-digit YEAR suffix in
    11..26 and a non-zero job number -- enforce the same shape here with a
    small buffer (10..27) so genuine near-boundary refs aren't lost."""
    m = re.match(r"^(\d{2,4})-(\d{2})$", ref)
    if not m:
        return False
    num, yr = int(m.group(1)), int(m.group(2))
    if num == 0:
        return False
    if not (10 <= yr <= 27):
        return False
    # False-positive guard: ISO date fragments "2024-10" (Oct 2024) parse as a
    # plausible-looking ref under the year-suffix rule above (10 <= 10 <= 27).
    # Confirmed live incident (matches like "2024-10", "2023-10", "1839-26"
    # surfaced from Trello card dates written in text). No real job number in
    # job_coords.json's 419-ref corpus is a 2000-2030 calendar year with a
    # 01-12 second group, so reject that specific shape.
    if 2000 <= num <= 2030 and 1 <= yr <= 12:
        return False
    return True
POSTCODE_RE = re.compile(r"\b([A-Za-z]{1,2}\d[A-Za-z\d]?\s*\d[A-Za-z]{2})\b")
STREET_WORDS_RE = re.compile(
    r"\b(Road|Rd|Street|St|Avenue|Ave|Close|Lane|Ln|Drive|Dr|Way|Gardens?|Gdns|"
    r"Grove|Crescent|Cres|Court|Ct|Place|Pl|Hill|Park|Terrace|Mews|Row|Walk)\b",
    re.IGNORECASE,
)
DATE_TEXT_RE = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})\b",
    re.IGNORECASE,
)


def normalize_postcode(pc):
    pc = pc.upper().replace(" ", "")
    if len(pc) > 3:
        return pc[:-3] + " " + pc[-3:]
    return pc


def extract_text_dates(text):
    out = []
    if dateutil_parser is None:
        return out
    for m in DATE_TEXT_RE.finditer(text or ""):
        raw = m.group(1)
        try:
            dt = dateutil_parser.parse(raw, dayfirst=True, default=datetime.datetime(2000, 1, 1))
            if 2005 <= dt.year <= 2027:
                out.append(dt.date().isoformat())
        except Exception:
            pass
    return out


def extract_from_card(c):
    name = c.get("name") or ""
    desc = c.get("desc") or ""
    text = name + "\n" + desc
    refs = sorted(set(
        m.group(0) for m in JOB_REF_RE.finditer(text)
        if plausible_job_ref(m.group(0))
        # False-positive guard: "10-12 Quebec Street" is a house-number range,
        # not a job ref, if a street-suffix word follows within a few words --
        # confirmed live incident (OR MAIN card "589-15  10-12 Quebec Street").
        and not STREET_WORDS_RE.search(text[m.end():m.end() + 25])
    ))
    postcodes_raw = sorted(set(m.group(1) for m in POSTCODE_RE.finditer(text)))
    postcodes = sorted(set(normalize_postcode(p) for p in postcodes_raw))
    address_lines = []
    for line in desc.split("\n"):
        line = line.strip()
        if not line:
            continue
        if POSTCODE_RE.search(line) or STREET_WORDS_RE.search(line):
            address_lines.append(line[:200])
    dates = []
    if c.get("due"):
        dates.append({"kind": "due", "date": c["due"][:10]})
    if c.get("dateLastActivity"):
        dates.append({"kind": "dateLastActivity", "date": c["dateLastActivity"][:10]})
    for d in extract_text_dates(text):
        dates.append({"kind": "text_date", "date": d})
    return refs, postcodes, address_lines, dates


print("\n=== Extracting refs/postcodes/addresses/dates from cards ===")
card_records = []
all_refs_found = set()
all_postcodes_found = set()
for c in all_cards:
    refs, postcodes, addr_lines, dates = extract_from_card(c)
    if not (refs or postcodes or addr_lines):
        continue
    rec = {
        "board_id": c["_board_id"], "board_name": c["_board_name"],
        "board_closed": c["_board_closed"],
        "card_id": c["id"], "card_name": c.get("name"),
        "card_closed": c.get("closed"), "short_url": c.get("shortUrl"),
        "refs": refs, "postcodes": postcodes, "address_lines": addr_lines,
        "dates": dates,
    }
    card_records.append(rec)
    all_refs_found.update(refs)
    all_postcodes_found.update(postcodes)

print("cards with >=1 ref/postcode/address signal:", len(card_records))
print("unique job-ref-shaped strings found:", len(all_refs_found))
print("unique postcodes found:", len(all_postcodes_found))

# ---------------------------------------------------------------------------
# geocode postcodes.io ONLY
# ---------------------------------------------------------------------------
def geocode_postcodes_bulk(postcodes):
    result = {}
    postcodes = sorted(set(postcodes))
    for i in range(0, len(postcodes), 100):
        batch = postcodes[i:i + 100]
        try:
            r = requests.post("https://api.postcodes.io/postcodes", json={"postcodes": batch}, timeout=20)
            data = r.json()
        except Exception as e:
            print("  geocode batch failed:", e)
            continue
        for row in data.get("result", []):
            pc = row["query"]
            res = row.get("result")
            if res:
                result[pc] = {"lat": res["latitude"], "lon": res["longitude"], "postcode": res["postcode"]}
        time.sleep(0.2)
    return result


print("\n=== Geocoding via postcodes.io ===")
geocoded = geocode_postcodes_bulk(all_postcodes_found)
print("postcodes geocoded successfully: %d / %d" % (len(geocoded), len(all_postcodes_found)))

# ---------------------------------------------------------------------------
# diff against job_coords.json (419 refs) -- read-only
# ---------------------------------------------------------------------------
job_coords = load_json(os.path.join(G, "job_coords.json"), {})
known_refs = set(job_coords.keys())


def ref_known(ref):
    return any(v in known_refs for v in ref_variants(ref))


ref_agg = {}
for rec in card_records:
    for ref in rec["refs"]:
        agg = ref_agg.setdefault(ref, {"cards": [], "postcodes": set()})
        agg["cards"].append(rec)
        agg["postcodes"].update(rec["postcodes"])

new_refs = []
known_refs_gaining_address = []
for ref, agg in ref_agg.items():
    if not ref_known(ref):
        new_refs.append(ref)
        continue
    existing_pc = None
    for v in ref_variants(ref):
        if v in job_coords and job_coords[v].get("postcode"):
            existing_pc = job_coords[v]["postcode"].upper().replace(" ", "")
            break
    for pc in agg["postcodes"]:
        if not existing_pc or pc.replace(" ", "") != existing_pc:
            known_refs_gaining_address.append(ref)
            break

address_only_cards = [rec for rec in card_records if not rec["refs"] and (rec["postcodes"] or rec["address_lines"])]

print("\nNEW refs vs the %d in job_coords.json: %d" % (len(known_refs), len(new_refs)))
print("known refs gaining a new/different postcode: %d" % len(known_refs_gaining_address))
print("address-only cards (no job ref, but postcode/address present): %d" % len(address_only_cards))

# trello_coords: usable in Phase B proximity leg for refs job_coords.json does
# not already have coords for. In-memory only -- job_coords.json is NEVER written.
trello_coords = {}
for ref, agg in ref_agg.items():
    for pc in sorted(agg["postcodes"]):
        if pc in geocoded:
            trello_coords[ref] = geocoded[pc]
            break

quarantine_rows = []
for ref in sorted(set(new_refs) | set(known_refs_gaining_address)):
    agg = ref_agg[ref]
    pcs = sorted(agg["postcodes"])
    coord = trello_coords.get(ref)
    quarantine_rows.append({
        "job_ref": ref,
        "status": "new_ref" if ref in new_refs else "known_ref_new_address",
        "postcodes_found": pcs,
        "geocoded": coord,
        "source": "trello",
        "evidence_cards": [
            {"board_name": c["board_name"], "card_name": c["card_name"],
             "short_url": c["short_url"], "dates": c["dates"]}
            for c in agg["cards"]
        ],
    })
for rec in address_only_cards:
    pcs = rec["postcodes"]
    coord = None
    for pc in pcs:
        if pc in geocoded:
            coord = geocoded[pc]
            break
    quarantine_rows.append({
        "job_ref": None,
        "status": "address_only_card",
        "postcodes_found": pcs,
        "address_lines": rec["address_lines"],
        "geocoded": coord,
        "source": "trello",
        "evidence_cards": [{"board_name": rec["board_name"], "card_name": rec["card_name"],
                             "short_url": rec["short_url"], "dates": rec["dates"]}],
    })

quarantine_out = {
    "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "provisional": True,
    "note": "IP-L9: quarantine only. job_coords.json is NEVER written by this script. "
            "Rows here are candidate evidence for Lee's answer, not ties.",
    "boards_total": len(boards),
    "boards_scanned": boards_scanned,
    "boards_failed": boards_failed,
    "cards_scanned": len(all_cards),
    "cards_with_signal": len(card_records),
    "unique_refs_found": len(all_refs_found),
    "unique_postcodes_found": len(all_postcodes_found),
    "postcodes_geocoded": len(geocoded),
    "known_refs_baseline": len(known_refs),
    "new_refs_count": len(new_refs),
    "known_refs_gaining_address_count": len(known_refs_gaining_address),
    "address_only_cards_count": len(address_only_cards),
    "rows": quarantine_rows,
}
with open(QUARANTINE_PATH, "w") as f:
    json.dump(quarantine_out, f, indent=1)
print("\nWrote", QUARANTINE_PATH)


# ===========================================================================
# PHASE B -- rescore grind/f2_candidates.json
# ===========================================================================
print("\n" + "=" * 70)
print("PHASE B: rescore f2_candidates.json with Trello evidence")
print("=" * 70)

if not os.path.exists(CANDIDATES_PATH):
    print("FATAL: %s not found -- Step 1 must run first." % CANDIDATES_PATH)
    sys.exit(1)

v1_doc = load_json(CANDIDATES_PATH)
shutil.copyfile(CANDIDATES_PATH, CANDIDATES_V1_PATH)
print("Backed up v1 ->", CANDIDATES_V1_PATH)

# --- 1. Derive residual clusters FRESH -- identical algorithm to
#     f2_candidate_engine.py / build_f2_phaseL.py. Not imported (no importable
#     functions in either); duplicated verbatim here, not edited there.
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
if top20_sizes != EXPECTED_TOP20_SIZES:
    print("SANITY GATE FAILED: derived top20_sizes != builder's last-produced sizes")
    print("  derived: ", top20_sizes)
    print("  expected:", EXPECTED_TOP20_SIZES)
    sys.exit(1)
print("SANITY GATE PASSED: top20 sizes match build_f2_phaseL.py's last run exactly.\n")

for ci, members in enumerate(top20, start=1):
    bad = [p for p in members if p in allocated_keep_paths]
    assert not bad, "cluster %d contains already-allocated paths: %s" % (ci, bad)
print("ASSERT PASSED: no cluster member path is already allocated to a job.\n")

# --- 2. per-photo date helper (identical to engine)
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
            out = subprocess_run_mdls(p)
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


import subprocess


def subprocess_run_mdls(p):
    return subprocess.run(["mdls", "-name", "kMDItemContentCreationDate", "-raw", p],
                           capture_output=True, text=True, timeout=10).stdout.strip()


# --- 3. dated job-event sources (identical to engine) + Trello (new)
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

events = {}


def add_event(job_ref, date, evidence_text, source_file, source_index, event_source="local"):
    if not job_ref or not date:
        return
    events.setdefault(job_ref, []).append({
        "date": date, "evidence_text": evidence_text,
        "source_file": source_file, "source_index": source_index,
        "event_source": event_source,
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

n_ev_local = sum(len(v) for v in events.values())
print("job_refs with >=1 dated event (pre-Trello):", len(events))
print("total local dated events:", n_ev_local)

# Trello events -- ANY ref seen on a card, new or already known, counts.
trello_events_added = 0
KIND_LABEL = {"due": "due", "dateLastActivity": "active", "text_date": "mentioned"}
for ref, agg in ref_agg.items():
    seen = set()
    for c in agg["cards"]:
        for dd in c["dates"]:
            key = (dd["kind"], dd["date"], c["card_id"])
            if key in seen:
                continue
            seen.add(key)
            kind_label = KIND_LABEL.get(dd["kind"], dd["kind"])
            ev = "%s %s, on the %s board that month" % (kind_label, fmt_human(dd["date"]), c["board_name"])
            add_event(ref, dd["date"], ev, "grind/f2_trello_quarantine.json", c["card_id"], event_source="trello")
            trello_events_added += 1

print("Trello dated events added:", trello_events_added)
print("job_refs with >=1 dated event (post-Trello):", len(events), "\n")


def event_dates_for(job_ref):
    return sorted(parse_d(e["date"]) for e in events.get(job_ref, []) if parse_d(e["date"]))


def is_continuous_job(job_ref):
    """Chronic/continuous invoicing pattern -- IP: >=5 dated events spanning
    >365 days (e.g. 468-15, 413-14, 622-16 maintenance jobs)."""
    dts = event_dates_for(job_ref)
    if len(dts) < 5:
        return False
    span = (dts[-1] - dts[0]).days
    return span > 365


def resolve_coords_aug(job_ref):
    for cand in ref_variants(job_ref):
        jc = job_coords.get(cand)
        if jc and jc.get("lat") is not None:
            return jc["lat"], jc["lon"], jc.get("confidence"), "job_coords"
    for cand in ref_variants(job_ref):
        tc = trello_coords.get(cand)
        if tc:
            return tc["lat"], tc["lon"], "trello_geocoded", "trello"
    return None, None, None, None


def resolve_name_v2(job_ref):
    for cand in ref_variants(job_ref):
        sn = site_names.get(cand)
        if sn and sn.get("name") and not is_raw_provenance(sn["name"]):
            return sn["name"], True
    for cand in ref_variants(job_ref):
        gs = gra_stories.get(cand)
        if gs and gs.get("site"):
            nm = gs["site"].get("name") or gs["site"].get("address")
            if nm and not is_raw_provenance(nm):
                return nm, True
    for cand in ref_variants(job_ref):
        jc = job_coords.get(cand)
        if jc:
            site = (jc.get("site") or "").strip()
            if site and not is_raw_provenance(site):
                return site, True
            pc = (jc.get("postcode") or "").strip()
            if pc:
                return pc, True
    return None, False


def date_distance_days(event_date, lo, hi):
    ed = parse_d(event_date)
    dlo, dhi = parse_d(lo), parse_d(hi)
    if not ed or not dlo or not dhi:
        return None
    if dlo <= ed <= dhi:
        return 0
    return min(abs((ed - dlo).days), abs((ed - dhi).days))


def score_candidate(best_event, dist_km):
    date_dist = best_event["_date_dist"]
    date_score = max(0, 14 - date_dist)
    if dist_km is not None:
        prox_score = max(0, 2 - dist_km) * 7
    else:
        prox_score = 0
    return date_score + prox_score


def build_candidates_for_window(lo, hi, centroid=None, date_only=False, drop_log=None):
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
        coord_src = None
        if not date_only and centroid is not None:
            jla, jlo, conf, coord_src = resolve_coords_aug(job_ref)
            if jla is not None:
                dist_km = hav(centroid[0], centroid[1], jla, jlo) / 1000.0
                if dist_km > 2.0:
                    # Only log as a Trello-driven demotion when the coords came
                    # FROM the Trello sweep -- excluding a job whose job_coords.json
                    # distance already failed the 2km gate is unchanged Step-1
                    # behaviour, not new information, and would bloat this log
                    # with ~600+ non-candidates per cluster for no signal.
                    if drop_log is not None and coord_src == "trello":
                        name, has_name = resolve_name_v2(job_ref)
                        label = "%s (%s)" % (name, job_ref) if has_name else "Job %s (name unknown)" % job_ref
                        drop_log.append({
                            "job_ref": job_ref, "label": label,
                            "distance_km": round(dist_km, 3), "coords_source": coord_src,
                            "reason": "Trello-geocoded address puts it %.1fkm away (outside 2km) -- "
                                      "demoted/dropped." % dist_km,
                        })
                    continue
        sc = score_candidate(best, dist_km)
        scored.append({
            "job_ref": job_ref, "score": round(sc, 2),
            "date_distance_days": best["_date_dist"],
            "distance_km": round(dist_km, 3) if dist_km is not None else None,
            "coords_confidence": conf, "coords_source": coord_src,
            "best_event": best,
        })
    scored.sort(key=lambda c: (-c["score"], c["date_distance_days"],
                                c["distance_km"] if c["distance_km"] is not None else 999))
    return scored[:3]


def strength_for(cluster_span_days, job_ref):
    if cluster_span_days > 60 or is_continuous_job(job_ref):
        return "weak-wide-window"
    return "tight"


def evidence_line(cand, date_only, strength):
    name, has_name = resolve_name_v2(cand["job_ref"])
    label = "%s (%s)" % (name, cand["job_ref"]) if has_name else "Job %s (name unknown)" % cand["job_ref"]
    ev = cand["best_event"]["evidence_text"]
    if date_only:
        line = "%s -- %s" % (label, ev)
    elif cand["distance_km"] is not None:
        line = "%s -- %s, %.1fkm away" % (label, ev, cand["distance_km"])
    else:
        line = "%s -- %s, distance unknown (no coords on file)" % (label, ev)
    if strength == "weak-wide-window":
        line += " [weak: wide window / continuous invoicing -- treat as low-confidence]"
    return line, label, has_name


# --- 5. per-cluster rescoring
print("=== Rescoring cluster candidates (with Trello evidence) ===")
cluster_out = []
zero_candidate_clusters = []
strength_histogram = {"tight": 0, "weak-wide-window": 0}
distance_carrying_count = 0
v1_by_cluster = {c["cluster_id"]: c for c in v1_doc.get("clusters", [])}
per_cluster_diff = []

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
    cluster_span_days = (parse_d(hi_actual) - parse_d(lo_actual)).days
    lo_win = (parse_d(lo_actual) - datetime.timedelta(days=14)).isoformat()
    hi_win = (parse_d(hi_actual) + datetime.timedelta(days=14)).isoformat()

    lats = [gps_no_job[p][0] for p in members]
    lons = [gps_no_job[p][1] for p in members]
    centroid = (sum(lats) / len(lats), sum(lons) / len(lons))

    drop_log = []
    cands = build_candidates_for_window(lo_win, hi_win, centroid=centroid, date_only=False, drop_log=drop_log)
    ranked = []
    for c in cands:
        strength = strength_for(cluster_span_days, c["job_ref"])
        strength_histogram[strength] += 1
        if c["distance_km"] is not None:
            distance_carrying_count += 1
        line, label, has_name = evidence_line(c, date_only=False, strength=strength)
        ranked.append({
            "job_ref": c["job_ref"], "site_name_resolved": has_name, "label": label,
            "score": c["score"], "date_distance_days": c["date_distance_days"],
            "distance_km": c["distance_km"], "coords_confidence": c["coords_confidence"],
            "coords_source": c["coords_source"], "strength": strength,
            "evidence_line": line,
            "evidence_source": {"file": c["best_event"]["source_file"], "index": c["best_event"]["source_index"]},
            "evidence_raw_text": c["best_event"]["evidence_text"],
            "event_source": c["best_event"].get("event_source", "local"),
        })

    rec = {
        "cluster_id": ci, "photo_count": len(members),
        "date_span_actual": {"lo": lo_actual, "hi": hi_actual},
        "date_span_days": cluster_span_days,
        "date_span_window_used": {"lo": lo_win, "hi": hi_win},
        "date_sources": date_sources,
        "centroid": {"lat": round(centroid[0], 6), "lon": round(centroid[1], 6)},
        "candidates": ranked,
        "trello_distance_dropped": drop_log,
    }
    cluster_out.append(rec)
    if not ranked:
        zero_candidate_clusters.append(ci)

    old = v1_by_cluster.get(ci)
    old_refs = [c["job_ref"] for c in old["candidates"]] if old else []
    new_refs_ranked = [c["job_ref"] for c in ranked]
    changed = old_refs != new_refs_ranked
    per_cluster_diff.append({
        "cluster_id": ci, "changed": changed,
        "v1_candidates": old_refs, "v2_candidates": new_refs_ranked,
        "trello_dropped": [d["job_ref"] for d in drop_log],
    })
    print("cluster %2d: %3d photos, span %4d d, %d candidate(s) -- %s" %
          (ci, len(members), cluster_span_days, len(ranked), "CHANGED" if changed else "no change"))

print("\nzero-candidate clusters:", zero_candidate_clusters or "none")

# --- 6. ambiguous photos (date-only, identical membership derivation)
print("\n=== Rescoring ambiguous-photo candidates (date-only, with Trello) ===")
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
    cands = build_candidates_for_window(lo_win, hi_win, centroid=None, date_only=True, drop_log=None)
    ranked = []
    for c in cands:
        # ambiguous photos have no cluster span concept -- strength keyed off
        # whether the matched job invoices continuously (span-based leg n/a).
        strength = "weak-wide-window" if is_continuous_job(c["job_ref"]) else "tight"
        strength_histogram[strength] += 1
        line, label, has_name = evidence_line(c, date_only=True, strength=strength)
        ranked.append({
            "job_ref": c["job_ref"], "site_name_resolved": has_name, "label": label,
            "score": c["score"], "date_distance_days": c["date_distance_days"],
            "date_only": True, "strength": strength,
            "evidence_line": line,
            "evidence_source": {"file": c["best_event"]["source_file"], "index": c["best_event"]["source_index"]},
            "evidence_raw_text": c["best_event"]["evidence_text"],
            "event_source": c["best_event"].get("event_source", "local"),
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

# --- 7. write v2 in place
out = {
    "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "provisional": True,
    "note": "IP-L9: candidates are provisional. Never promoted, never written as "
            "ties, never merged into allocation_v2.jsonl or job_coords.json without "
            "Lee's explicit answer. v2: rescored with Trello sweep evidence "
            "(grind/f2_trello_quarantine.json) -- see 'strength' field on each "
            "candidate and 'trello_distance_dropped' on each cluster.",
    "sanity_gate": {"top20_sizes_expected": EXPECTED_TOP20_SIZES, "top20_sizes_derived": top20_sizes, "match": True},
    "clusters": cluster_out,
    "zero_candidate_clusters": zero_candidate_clusters,
    "ambiguous_photos": amb_out,
    "zero_candidate_ambiguous_count": len(zero_candidate_amb),
    "trello_events_added": trello_events_added,
    "strength_histogram": strength_histogram,
    "distance_carrying_candidate_count": distance_carrying_count,
    "per_cluster_diff_v1_v2": per_cluster_diff,
}
with open(CANDIDATES_PATH, "w") as f:
    json.dump(out, f, indent=1)
print("\nWrote", CANDIDATES_PATH, "(v2, in place -- v1 backed up)")

# --- 8. sample cards for spot-check
print("\n=== 5 sample Trello card rows (for orchestrator spot-check) ===")
sample_pool = [r for r in card_records if r["refs"] or r["postcodes"]]
for rec in sample_pool[:5]:
    print(json.dumps({
        "board_name": rec["board_name"], "card_name": rec["card_name"],
        "refs": rec["refs"], "postcodes": rec["postcodes"],
        "dates": rec["dates"], "short_url": rec["short_url"],
    }))

print("\n=== DONE ===")
