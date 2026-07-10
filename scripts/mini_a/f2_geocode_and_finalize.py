#!/usr/bin/env python3
"""F2 geocode + finalize: bulk-geocode candidate postcodes via postcodes.io, merge into
job_coords.json. Run on Mini A in ~/image-plane/."""
import json, urllib.request, sys

candidates = json.load(open('grind/f2_merge_candidates.json'))
coords = json.load(open('grind/job_coords.json'))
assert len(coords) == 209, f"expected 209 baseline, got {len(coords)}"

need_geocode = {k: v for k, v in candidates.items() if not (v.get('lat') and v.get('lon'))}
have_latlon = {k: v for k, v in candidates.items() if v.get('lat') and v.get('lon')}

pcs = list({v['postcode'] for v in need_geocode.values() if v.get('postcode')})
print(f"Distinct postcodes to bulk-geocode: {len(pcs)}", file=sys.stderr)

results = {}
BATCH = 100
for i in range(0, len(pcs), BATCH):
    batch = pcs[i:i+BATCH]
    payload = json.dumps({"postcodes": batch}).encode()
    req = urllib.request.Request(
        "https://api.postcodes.io/postcodes",
        data=payload, method="POST",
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    for r in body.get('result', []):
        q = r['query']
        if r.get('result'):
            results[q] = (r['result']['latitude'], r['result']['longitude'])

print(f"Geocoded OK: {len(results)} / {len(pcs)}", file=sys.stderr)
failed_pcs = [p for p in pcs if p not in results]
print(f"Failed/invalid postcodes: {failed_pcs}", file=sys.stderr)

new_entries = {}
geocode_failures = []
for ref, v in need_geocode.items():
    pc = v.get('postcode')
    if not pc or pc not in results:
        geocode_failures.append({"job_ref": ref, "postcode": pc, "store": v['store']})
        continue
    lat, lon = results[pc]
    new_entries[ref] = {
        "lat": lat, "lon": lon, "site": v.get('evidence', '')[:120],
        "source": v['store'], "confidence": v['band'],
        "postcode": pc, "evidence": v['evidence']
    }

for ref, v in have_latlon.items():
    new_entries[ref] = {
        "lat": v['lat'], "lon": v['lon'], "site": v.get('evidence', '')[:120],
        "source": v['store'], "confidence": v['band'],
        "postcode": v.get('postcode'), "evidence": v['evidence']
    }

print(f"Final geocoded new entries: {len(new_entries)}", file=sys.stderr)
print(f"Geocode failures: {len(geocode_failures)}", file=sys.stderr)

# merge into coords (additive only — no existing key touched)
collisions = [k for k in new_entries if k in coords]
assert not collisions, f"collision with existing map keys: {collisions}"

coords.update(new_entries)
json.dump(coords, open('grind/job_coords.json', 'w'), indent=1)
json.dump(geocode_failures, open('grind/f2_geocode_failures.json', 'w'), indent=1)

from collections import Counter
by_source = Counter(v.get('source') for v in coords.values())
band_of_new = Counter(v['confidence'] for v in new_entries.values())

summary = {
    "before_count": 209,
    "after_count": len(coords),
    "new_added": len(new_entries),
    "geocode_failures": len(geocode_failures),
    "after_by_source": dict(by_source),
    "new_by_band": dict(band_of_new),
}
json.dump(summary, open('grind/f2_merge_final_summary.json', 'w'), indent=1)
print(json.dumps(summary, indent=1))
