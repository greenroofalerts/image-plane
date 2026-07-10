#!/usr/bin/env python3
"""F2 map-merge pass — merge inventory's usable stores into grind/job_coords.json.
Run on Mini A, in ~/image-plane/. Read-only stores are already copied into grind/f2_*.
"""
import json, re, csv, sys
from collections import Counter, defaultdict

PC_RE = re.compile(r'\b([Gg][Ii][Rr] 0[Aa]{2})\b|\b((?:[A-Za-z]{1,2}[0-9][A-Za-z0-9]?)\s*([0-9][A-Za-z]{2}))\b')

def extract_postcodes(text):
    if not text:
        return []
    out = []
    # No leading \b: this corpus frequently concatenates the postcode directly onto the
    # preceding word with no space (e.g. "Co DurhamDL2 1TS"). Trailing \b still required.
    for m in re.finditer(r'([A-Za-z]{1,2}[0-9][A-Za-z0-9]?)\s*([0-9][A-Za-z]{2})\b', text):
        out.append(f"{m.group(1).upper()} {m.group(2).upper()}")
    return out

def norm_ref(r):
    if not r:
        return r
    r = r.strip()
    m = re.match(r'^0*(\d+)-(\d+)$', r)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return r

# ---- load current map ----
coords = json.load(open('grind/job_coords.json'))
before_count = len(coords)
before_by_source = Counter(v.get('source') for v in coords.values())

candidates = {}  # ref -> list of (postcode, band, source_name, evidence, extra)
conflicts_log = []

# ---- Store 10: known_entities strict ----
ke = json.load(open('grind/f2_known_entities_raw.json'))
addr_counter = Counter()
row_pc = []
for row in ke:
    ref = norm_ref(row.get('job_ref'))
    if not ref:
        continue
    addr = row.get('address') or ''
    pcs = extract_postcodes(row.get('postcode') or '') or extract_postcodes(addr)
    if not pcs:
        continue
    addr_key = addr.strip().lower()
    addr_counter[addr_key] += 0  # placeholder, count distinct refs below
    row_pc.append((ref, pcs[0], addr_key, row.get('display_name')))

# count distinct refs per address (non-repeated address rule: exclude addresses shared by >=3 distinct refs)
addr_refs = defaultdict(set)
for ref, pc, addr_key, name in row_pc:
    addr_refs[addr_key].add(ref)
banned_addrs = {a for a, refs in addr_refs.items() if len(refs) >= 3}

ke_by_ref = defaultdict(set)  # ref -> set of distinct postcodes (after excluding shared addrs)
ke_evidence = {}
for ref, pc, addr_key, name in row_pc:
    if addr_key in banned_addrs:
        continue
    ke_by_ref[ref].add(pc)
    ke_evidence[ref] = name

ke_strict_refs = set(ke_by_ref.keys())
print(f"[known_entities] strict distinct refs: {len(ke_strict_refs)}", file=sys.stderr)

ke_internal_conflicts = {ref: pcs for ref, pcs in ke_by_ref.items() if len(pcs) > 1}
print(f"[known_entities] internal multi-postcode refs: {len(ke_internal_conflicts)}", file=sys.stderr)

for ref, pcs in ke_by_ref.items():
    if ref in coords:
        continue
    if len(pcs) > 1:
        conflicts_log.append({
            "job_ref": ref, "reason": "known_entities internal disagreement",
            "candidates": sorted(pcs), "stores": ["known_entities"]
        })
        continue
    pc = next(iter(pcs))
    candidates.setdefault(ref, []).append({
        "postcode": pc, "band": "strong", "store": "known_entities",
        "evidence": f"known_entities postcode-bearing non-repeated address (contact/entity: {ke_evidence.get(ref)})"
    })

# ---- Store 1: site-facts-draft-v4 non-footer, tier->band ----
tier_band = {"strong": "strong", "medium": "likely", "uncertain": "weak"}
sf = json.load(open('grind/f2_site_facts_v4.json'))
for ref, rec in sf.items():
    ref = norm_ref(ref)
    kept = rec.get('kept') or []
    non_footer = [c for c in kept if c.get('zone') != 'footer']
    if not non_footer:
        continue
    if ref in coords:
        continue
    # pick best tier available among non-footer candidates
    tiers_present = [c.get('tier') for c in non_footer]
    best_tier = None
    for t in ("strong", "medium", "uncertain"):
        if t in tiers_present:
            best_tier = t
            break
    if not best_tier:
        continue
    pcs = {c['pc'] for c in non_footer if c.get('tier') == best_tier}
    band = tier_band[best_tier]
    if len(pcs) > 1:
        conflicts_log.append({
            "job_ref": ref, "reason": "site-facts-v4 internal disagreement (same tier)",
            "candidates": sorted(pcs), "stores": ["site-facts-draft-v4"]
        })
        continue
    pc = next(iter(pcs))
    candidates.setdefault(ref, []).append({
        "postcode": pc, "band": band, "store": "site-facts-draft-v4",
        "evidence": f"non-footer postcode candidate, tier={best_tier}, zone={non_footer[0].get('zone')}"
    })

# ---- Store 12: GRA live sites ----
gra = json.load(open('grind/f2_gra_sites_live.json'))
gra_by_ref = {}
for row in gra:
    ref = row.get('job_ref')
    if not ref or ref == 'TEST-LEE':
        continue
    gra_by_ref[norm_ref(ref)] = row

sub_site_parent = '1343-21'
sub_variants = ['1343-21-AVP', '1343-21-LWS', '1343-21-STL']
parent_row = gra_by_ref.get(sub_site_parent)
parent_pc = None
if parent_row:
    parent_pc = (parent_row.get('postcode') or '').strip().upper()
elif sub_site_parent in coords:
    parent_pc = coords[sub_site_parent].get('postcode')

sub_pcs_seen = {}
for v in sub_variants:
    row = gra_by_ref.get(v)
    if not row:
        continue
    pc = (row.get('postcode') or '').strip().upper()
    sub_pcs_seen[v] = (pc, row)

distinct_sub_pcs = {pc for pc, _ in sub_pcs_seen.values() if pc}
fold_to_parent = False
if parent_pc and len(distinct_sub_pcs) <= 1 and (not distinct_sub_pcs or parent_pc in distinct_sub_pcs):
    fold_to_parent = True

gra_new_refs = ['1367-21', '1380-21', '149-13', '1640-23', '1655-23', '1658-23', '1851-26']
for ref in gra_new_refs:
    ref = norm_ref(ref)
    if ref in coords:
        continue
    row = gra_by_ref.get(ref)
    if not row:
        continue
    pc = (row.get('postcode') or '').strip().upper()
    lat, lon = row.get('latitude'), row.get('longitude')
    if not pc and not (lat and lon):
        continue
    candidates.setdefault(ref, []).append({
        "postcode": pc or None, "lat": lat, "lon": lon, "band": "strong",
        "store": "gra_sites_live", "evidence": f"GRA sites live row, address={row.get('address')}"
    })

if not fold_to_parent and distinct_sub_pcs:
    # keep as distinct entries (they carry distinct postcodes)
    for v, (pc, row) in sub_pcs_seen.items():
        if v in coords:
            continue
        candidates.setdefault(v, []).append({
            "postcode": pc or None, "lat": row.get('latitude'), "lon": row.get('longitude'),
            "band": "strong", "store": "gra_sites_live",
            "evidence": f"GRA sub-site variant of {sub_site_parent}, address={row.get('address')}"
        })
    sub_site_decision = "kept distinct (postcodes differ from parent/each other)"
else:
    sub_site_decision = f"folded to parent {sub_site_parent} (same/no distinguishing postcode) — no separate entries added"

# ---- Store 9: reports_corpus.jsonl (1 ref: 1772-25) ----
rc_new_ref = norm_ref('1772-25')
if rc_new_ref not in coords:
    with open('reports_corpus.jsonl') as f:
        for line in f:
            rec = json.loads(line)
            ref = norm_ref(rec.get('job_ref') or rec.get('ref'))
            if ref != rc_new_ref:
                continue
            pc = None
            for k in ('postcode', 'site_postcode'):
                if rec.get(k):
                    pc = rec[k]
                    break
            if not pc:
                pcs = extract_postcodes(json.dumps(rec))
                pc = pcs[0] if pcs else None
            if pc:
                candidates.setdefault(rc_new_ref, []).append({
                    "postcode": pc, "band": "strong", "store": "reports_corpus",
                    "evidence": "reports_corpus.jsonl postcode field"
                })
            break

# ---- Store: green-roof-portal site_audit csv — cross-validation only (both overlap site-facts) ----
audit_pc = {}
with open('grind/f2_site_audit.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        ref = norm_ref(row.get('ref') or row.get('job_ref'))
        pc = (row.get('postcode') or '').strip().upper()
        if ref and pc:
            audit_pc[ref] = pc

# ---- EXCLUDE billing-flagged xero_contact refs ----
excluded_billing = {norm_ref('1815-25'), norm_ref('74-12')}
for ref in list(candidates.keys()):
    if ref in excluded_billing:
        del candidates[ref]
        conflicts_log.append({"job_ref": ref, "reason": "excluded: billing/xero_contact address only, never used", "candidates": [], "stores": ["xero_contact_addresses"]})

# ---- cross-store conflict resolution ----
final_new = {}
per_source_new_counts = Counter()
band_tally = Counter()

for ref, cands in candidates.items():
    if ref in coords:
        continue
    pcs_present = {c['postcode'] for c in cands if c.get('postcode')}
    # cross-check against site_audit csv too (informational; site_audit itself contributes 0 net-new)
    if ref in audit_pc:
        pcs_present.add(audit_pc[ref])
    if len(pcs_present) > 1:
        conflicts_log.append({
            "job_ref": ref, "reason": "cross-store postcode disagreement",
            "candidates": sorted(pcs_present),
            "stores": sorted({c['store'] for c in cands})
        })
        continue  # do not pick a winner — no map entry added this pass
    # single agreed postcode (or a GRA row with lat/lon but no postcode)
    chosen = max(cands, key=lambda c: {"strong": 3, "likely": 2, "weak": 1}.get(c['band'], 0))
    final_new[ref] = chosen
    per_source_new_counts[chosen['store']] += 1
    band_tally[chosen['band']] += 1

print(f"Candidates considered: {len(candidates)}", file=sys.stderr)
print(f"Final new (no conflict): {len(final_new)}", file=sys.stderr)
print(f"Conflicts logged: {len(conflicts_log)}", file=sys.stderr)
print(f"Sub-site decision: {sub_site_decision}", file=sys.stderr)

# save intermediate for geocode step
json.dump(final_new, open('grind/f2_merge_candidates.json', 'w'), indent=1)
json.dump(conflicts_log, open('grind/f2_merge_conflicts.json', 'w'), indent=1)
json.dump({
    "before_count": before_count,
    "before_by_source": dict(before_by_source),
    "new_by_store": dict(per_source_new_counts),
    "band_tally": dict(band_tally),
    "sub_site_decision": sub_site_decision,
    "candidates_considered": len(candidates),
    "final_new_no_conflict": len(final_new),
    "conflicts_logged": len(conflicts_log),
}, open('grind/f2_merge_summary_pre_geocode.json', 'w'), indent=1)

print(json.dumps({
    "before_count": before_count,
    "new_by_store": dict(per_source_new_counts),
    "band_tally": dict(band_tally),
    "conflicts": len(conflicts_log),
}, indent=1))
