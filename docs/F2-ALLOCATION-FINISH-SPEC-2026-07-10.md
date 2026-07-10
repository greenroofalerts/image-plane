# F2 SPEC — Finish allocation (A5): tie the remaining keeps to roofs — 2026-07-10

Source: `DELTA-IMAGE-PLANE-2026-07-10.md` Part 3 F2 + same-day re-rank. Depends on F1
(delivered: `counts.py` is the ONLY number source — every pass here reports via it).
Lee's standing bar (verbatim class): **allocation must be exhaustive** — every image from a
project site, tied to job + date. Categories may be "good enough"; allocation may not.

Scope at spec time — Counted by: `python3 ~/image-plane/counts.py` on Mini A, 2026-07-10T18:32Z:
5,775 unallocated keeps = 4,966 gps-but-no-job · 809 no-coords · (407 of the 5,775 also
missing on disk → Lee's queue, not machine work).

## Hard rules (from skill + CLAUDE.md — the wheel exists, attach to it)
- Do NOT build a new resolver. Reuse: `~/glenross/scripts/job_site_finder.js`,
  `mine-allocation-history.js`, and the source order in
  `~/glenross/docs/product-control/GLENROSS-ALLOCATION-SOURCE-AUDIT-2026-06-23.md` — read
  both docs before writing any code.
- Job universe = Xero job tracking vocab + Drive project folders, NOT customer contacts.
  Site address ≠ billing address. GRA sites = geocode LOOKUP only (already lat/lon), never
  the authority, never re-geocode.
- Never match on one field; confidence-band every result (exact/strong/likely/weak);
  ambiguous → sheet for Lee, never forced.
- All raw addresses/site rows stay on Mini A / `~/.glenross/`. Only counts and band tallies
  come back to chat. Geocoding of postcodes: postcodes.io (postcode-only queries are fine).
- Xero access: self-refresh via `cd ~/glenross && node pull_xero_jobs.js` (rotating token in
  `~/leeos-private/glenross/.env.xero`) — never wait on /mcp.
- allocation_v2.jsonl is append/regenerate via the established grind scripts; if regenerated,
  regenerate `grind/allocation_v2_flags.jsonl` with it (`grind/build_allocation_v2_flags.py`)
  and re-run `counts.py --check`. New allocations carry `method` + `confidence` like existing
  rows.

## Phase M1 — grow the geocoded job map (the lever: 4,966 already have GPS)
1. Current map audit first: how many distinct jobs are geocoded today, from which source
   (GRA sites / reports postcodes / prior passes)? Where do the 4,966 cluster — distance from
   each to nearest CURRENT geocoded job (histogram: ≤150m / ≤500m / ≤2km / >2km)? That
   histogram decides how much map growth closes.
2. Expand the map: Drive project folders (spine `observations` where `source='drive_folder'`,
   path_segments give `NNNN-YY - Client` names) ∪ Xero vocab (self-refresh above) — extract
   postcodes/addresses via the Glenross harvester rules (site = TOP recipient block; billing
   vetoed), geocode postcodes via postcodes.io. Every new map entry: job_ref, lat/lon,
   source, confidence.
3. Rerun the GPS nearest-neighbour pass (existing method, ~150m default) for the
   gps-but-no-job keeps against the expanded map. Existing 6,563 allocations are NOT
   re-matched (stable unless a conflict is found — report conflicts, don't overwrite).
4. Report via counts.py before/after + band tallies. Expect a residue — that's M2/sheets,
   not failure.

## Phase M2 — the 809 no-coords
Album joins (takeout album name = job_ref+site+season — strong), then burst/filename-order
adjacency (a no-GPS photo sandwiched between two same-job photos minutes apart = likely that
job, band `likely` at best). Date evidence from EXIF. Never `exact` without two independent
signals.

## Phase L — Lee residue (after M1+M2, his pace)
Ambiguous + unmatched → sheets via the GUARDED builders only (guards.py, F1): large photos
(one per row, ≥1100px, big number badge — Lee's size rule), counts footer, captions from
ground truth only. 407 missing-on-disk → a look-list on the hub (F8), no build.

## Done means
- counts.py unallocated strictly falls; every machine tie has method+confidence; zero forced
  matches; conflicts with existing allocations reported not overwritten; --check passes after
  every regeneration; before/after receipt quotes counts.py with Counted by lines.
- Explicit residue statement: how many left for Lee, on which sheets.
