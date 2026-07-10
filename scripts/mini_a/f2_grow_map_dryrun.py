#!/usr/bin/env python3
"""F2 M1 step 2 -- grow the job coord map. DRY RUN (report only, no writes).
Reuses allocate_global_v3.py's own coord-map/geocode logic; extends it with:
  (a) GRA-mirror lookup for the 1 GRA-only headroom ref
  (b) Xero invoice-line description/reference postcode extraction (validated
      via postcodes.io, since format-match alone is known-unreliable --
      GLENROSS-SITE-FACT-HARVESTER-V3 calls this out explicitly)
  (c) Xero contact-address geocode (same method as allocate_global_v3.py's
      xc_need logic) for headroom refs not covered by (a)/(b)
Every candidate confidence-banded: exact (GRA mirror) / strong (postcode found
directly in invoice text, validated) / likely (single contact, single STREET-type
postcode) / weak (POBOX-only, or multiple conflicting candidates) -- weak entries
are recorded but must be excluded from auto-matching downstream.
"""
import json, os, re, csv, urllib.request
from collections import defaultdict

IP = os.path.expanduser("~/image-plane")
G = os.path.join(IP, "grind")

def nr(x):
    m = re.match(r"\s*0*(\d+)-(\d{2})\b", str(x or ""))
    return f"{m.group(1)}-{m.group(2)}" if m else None

def cnorm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())

UKPC = re.compile(r"\b[A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2}\b")

def geocode_postcodes(pcs):
    out = {}
    pcs = [p for p in pcs if p]
    for i in range(0, len(pcs), 90):
        batch = pcs[i:i+90]
        try:
            req = urllib.request.Request(
                "https://api.postcodes.io/postcodes",
                data=json.dumps({"postcodes": batch}).encode(),
                headers={"Content-Type": "application/json"})
            res = json.load(urllib.request.urlopen(req, timeout=30))
            for item in res.get("result", []):
                q = item.get("query")
                r = item.get("result")
                if r and r.get("latitude"):
                    out[q] = (r["latitude"], r["longitude"])
        except Exception as e:
            print("geocode batch error:", e)
    return out

# ---------- current map ----------
coords = json.load(open(os.path.join(G, "job_coords.json")))
print("current map:", len(coords), "job_refs")

# ---------- headroom (from the committed audit) ----------
q4 = json.load(open(os.path.join(G, "f2_m1_audit_part2_q4.json")))
headroom = q4["union_headroom"]
print("headroom refs:", len(headroom))

# ---------- GRA mirror (address reference lookup only) ----------
gra = json.load(open(os.path.join(G, "gra_sites.json")))
gra_by_ref = {nr(g["job_ref"]): g for g in gra if nr(g["job_ref"])}

# ---------- Xero lines (fresh, both tenants) ----------
xero_lines = json.load(open(os.path.join(G, "xero_invoice_lines_full.json")))
ref_texts = defaultdict(list)
ref_contacts = defaultdict(set)
ref_dates = defaultdict(list)
for e in xero_lines:
    ref = nr(e.get("tracking_ref"))
    if not ref:
        continue
    txt = ((e.get("description") or "") + " " + (e.get("reference") or "")).strip()
    if txt:
        ref_texts[ref].append(txt)
    if e.get("contact"):
        ref_contacts[ref].add(cnorm(e["contact"]))
    if e.get("date"):
        ref_dates[ref].append(e["date"])

# ---------- Xero contact addresses (billing/correspondence, NOT site truth) ----------
try:
    ca = json.load(open(os.path.join(G, "xero_contact_addresses.json")))
except Exception:
    ca = []
c2pc = defaultdict(lambda: {"STREET": set(), "POBOX": set()})
for r in ca:
    pc = (r.get("postcode") or "").strip().upper()
    if not pc:
        continue
    t = r.get("type", "")
    key = "STREET" if t == "STREET" else "POBOX"
    c2pc[cnorm(r.get("contact"))][key].add(pc)

# ---------- Drive folder name postcode (source #1 in priority order -- the
# canonical job-folder naming convention itself carries the full site address,
# not a billing address) ----------
drive_pc_path = os.path.join(G, "f2_drive_postcode_candidates.json")
drive_single = {}
drive_folder_name = {}
if os.path.exists(drive_pc_path):
    dd = json.load(open(drive_pc_path))
    drive_single = dd.get("single_pc", {})
    drive_folder_name = dd.get("folder_name", {})

# ---------- classify each headroom ref ----------
plan = {"gra_geocode": [], "drive_folder_postcode": [], "xero_desc_postcode": [],
        "xero_contact_geocode_street": [],
        "xero_contact_geocode_pobox_only": [], "ambiguous_conflicting_desc_postcode": [],
        "ambiguous_multi_contact_postcode": [], "no_evidence": []}

candidate_postcodes = set()
per_ref_plan = {}

for ref in headroom:
    if ref in coords:
        continue  # already covered by base map somehow -- skip
    entry = None

    # (a) GRA mirror -- exact
    g = gra_by_ref.get(ref)
    if g and (g.get("postcode") or "").strip():
        pc = g["postcode"].strip().upper()
        entry = {"tier": "gra_geocode", "confidence": "exact", "postcode": pc,
                 "site": g.get("address", ""), "evidence": "GRA sites mirror job_ref lookup"}
        candidate_postcodes.add(pc)

    # (b) Drive folder name postcode -- canonical job-folder naming, site address
    if entry is None and ref in drive_single:
        pc = drive_single[ref]
        entry = {"tier": "drive_folder_postcode", "confidence": "strong", "postcode": pc,
                 "site": drive_folder_name.get(ref, ""),
                 "evidence": "postcode token in Drive canonical job-folder name (NNNN-YY - address)"}
        candidate_postcodes.add(pc)

    # (c) Xero desc/reference postcode extraction (validate via postcodes.io later)
    if entry is None and ref in ref_texts:
        found = set()
        found_texts = {}
        for t in ref_texts[ref]:
            for m in UKPC.findall(t.upper()):
                mm = re.sub(r"\s+", "", m)
                # normalise "AB1 2CD" spacing for a canonical key
                canon = mm[:-3] + " " + mm[-3:]
                found.add(canon)
                found_texts.setdefault(canon, t[:100])
        if len(found) == 1:
            pc = list(found)[0]
            entry = {"tier": "xero_desc_postcode", "confidence": "strong", "postcode": pc,
                      "site": found_texts[pc], "evidence": "postcode token in Xero invoice description/reference"}
            candidate_postcodes.add(pc)
        elif len(found) > 1:
            entry = {"tier": "ambiguous_conflicting_desc_postcode", "confidence": "weak",
                      "postcode": None, "candidates": sorted(found),
                      "evidence": "multiple distinct postcode tokens across invoice lines for same job_ref"}

    # (c) Xero contact-address geocode (billing address proxy -- lower confidence)
    if entry is None and ref in ref_contacts:
        contacts = ref_contacts[ref]
        if len(contacts) == 1:
            c = list(contacts)[0]
            d = c2pc.get(c)
            if d:
                street = d["STREET"]; pobox = d["POBOX"]
                if len(street) == 1:
                    pc = list(street)[0]
                    entry = {"tier": "xero_contact_geocode_street", "confidence": "likely",
                              "postcode": pc, "site": c, "evidence": f"single contact '{c}', single STREET-type postcode"}
                    candidate_postcodes.add(pc)
                elif len(street) == 0 and len(pobox) == 1:
                    pc = list(pobox)[0]
                    entry = {"tier": "xero_contact_geocode_pobox_only", "confidence": "weak",
                              "postcode": pc, "site": c, "evidence": f"single contact '{c}', POBOX-type only (correspondence address, not site)"}
                    candidate_postcodes.add(pc)
                elif (len(street) + len(pobox)) > 1:
                    all_pc = street | pobox
                    entry = {"tier": "ambiguous_multi_contact_postcode", "confidence": "weak",
                              "postcode": None, "candidates": sorted(all_pc), "site": c,
                              "evidence": f"single contact '{c}' but multiple distinct postcodes on file"}
        else:
            # multiple contacts -- try union of their single postcodes
            all_pc = set()
            for c in contacts:
                d = c2pc.get(c)
                if d:
                    all_pc |= (d["STREET"] or d["POBOX"])
            if len(all_pc) == 1:
                pc = list(all_pc)[0]
                entry = {"tier": "xero_contact_geocode_street", "confidence": "likely",
                          "postcode": pc, "site": "/".join(sorted(contacts)),
                          "evidence": f"{len(contacts)} contacts, converge on one postcode"}
                candidate_postcodes.add(pc)
            elif len(all_pc) > 1:
                entry = {"tier": "ambiguous_multi_contact_postcode", "confidence": "weak",
                          "postcode": None, "candidates": sorted(all_pc),
                          "evidence": f"{len(contacts)} contacts, {len(all_pc)} distinct postcodes"}

    if entry is None:
        entry = {"tier": "no_evidence", "confidence": None, "postcode": None,
                  "evidence": "no GRA mirror row, no postcode in Xero text, no usable contact-address"}

    per_ref_plan[ref] = entry
    plan[entry["tier"]].append(ref)

print("\n--- plan by tier ---")
for k, v in plan.items():
    print(f"{k}: {len(v)}")

print("\ncandidate postcodes to geocode:", len(candidate_postcodes))

# ---------- validate + geocode candidates ----------
geo = geocode_postcodes(list(candidate_postcodes))
print("postcodes.io resolved:", len(geo), "of", len(candidate_postcodes))
invalid = candidate_postcodes - set(geo.keys())
if invalid:
    print("INVALID/unresolved postcodes (dropped as false-positive extraction):", sorted(invalid))

# ---------- final tally: how many new map entries would this produce ----------
new_entries = {}
downgraded_to_weak_by_invalid_postcode = []
for ref, entry in per_ref_plan.items():
    pc = entry.get("postcode")
    if pc and pc in geo:
        lat, lon = geo[pc]
        new_entries[ref] = {"lat": lat, "lon": lon, "site": entry.get("site", ""),
                              "source": entry["tier"], "confidence": entry["confidence"],
                              "postcode": pc, "evidence": entry["evidence"]}
    elif pc and pc not in geo:
        downgraded_to_weak_by_invalid_postcode.append(ref)
    elif entry["tier"] in ("ambiguous_conflicting_desc_postcode", "ambiguous_multi_contact_postcode"):
        new_entries[ref] = {"lat": None, "lon": None, "site": entry.get("site", ""),
                              "source": entry["tier"], "confidence": "weak",
                              "candidates": entry.get("candidates"), "evidence": entry["evidence"]}

print("\nnew entries (would-write) total:", len(new_entries))
by_conf = defaultdict(int)
for v in new_entries.values():
    by_conf[v["confidence"]] += 1
print("by confidence:", dict(by_conf))
print("dropped (postcode extracted but failed postcodes.io validation):", len(downgraded_to_weak_by_invalid_postcode), downgraded_to_weak_by_invalid_postcode)

json.dump({"plan_by_tier": {k: len(v) for k, v in plan.items()},
           "new_entries_count": len(new_entries),
           "new_entries_by_confidence": dict(by_conf),
           "invalid_postcodes_dropped": sorted(invalid),
           "new_entries": new_entries,
           "no_evidence_refs": plan["no_evidence"]},
          open(os.path.join(G, "f2_map_growth_dryrun.json"), "w"), indent=1)
print("\nwrote", os.path.join(G, "f2_map_growth_dryrun.json"), "(dry run detail, not applied)")
