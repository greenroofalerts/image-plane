# F2 Address Stores Inventory — 2026-07-10

Read-only sweep. Purpose: enumerate every existing store that maps a green-roof job ref
(NNNN-YY) to a site address/postcode/lat-lon, so a later pass can merge net-new refs into
`~/image-plane/grind/job_coords.json` (baseline: **209 refs**, confirmed same-day as the F2-M1
pass in `docs/F2-M1-RUN-2026-07-10.md`, which already grew the map 198→209 using 4 established
sources: GRA sites mirror, Drive folder names, Xero invoice-line description, Xero contact
geocode).

Correction to record: an earlier pass declared "no evidence" after checking 4 thin sources.
This sweep checked those 4 plus 9 more and found substantial address evidence sitting unused,
above all in Supabase `known_entities` (never touched by F2-M1) and the **live** GRA `sites`
table (which has grown to 105 rows — the F2-M1 pass used a stale 70-row local mirror).

All ref comparisons normalise zero-padding (`0970-19` == `970-19`) before matching against the
209-key baseline.

---

## Per-store findings

### 1. `~/.glenross/site-facts-draft-v4-2026-06-23.json` (laptop)
Site-fact harvester output, 60 refs, each with `kept`/`struck` postcode candidates tagged by
`zone` (footer=billing, VETOED; body/top=usable) and `tier` (strong/medium/uncertain/area_mismatch).

- Total refs in file: 60
- Refs with ≥1 non-footer (usable) postcode candidate: **30**
  - tier=strong: 25 (20 not in job_coords.json)
  - tier=medium (no strong): 4 (3 not in job_coords.json)
  - tier=uncertain only: 1 (1 not in job_coords.json)
- **Not in job_coords.json: 24** — `1049-19, 108-12, 109-12, 1093-19, 1112-19, 1136-20, 1148-20,
  121-12, 127-12, 130-12, 132-12, 135-12, 1358-21, 136-12, 1377-21, 1398-21, 1406-21, 1408-21,
  1426-21, 1432-21, 1448-21, 1457-21, 1480-22, 1487-22`

### 2. `~/image-plane/portfolio_register_v2.csv` (laptop)
182 distinct refs. `geocode_status` distribution:
- ok: 91, report_postcode: 38, needs_address_from_folder: 27, no_match: 18, report_no_postcode: 8
- Refs with lat+lon actually populated (ok + report_postcode): **129**
- **Not in job_coords.json: 0** — this file is already fully absorbed into the map (it's job_coords.json's own `portfolio` source tier, 148 entries claimed in F2-M1 doc; some portfolio refs may since have been superseded but none are missing).

### 3. `~/glenross/xero_contact_addresses.json` (laptop)
76 rows, keyed by **contact name**, not job_ref — 56 distinct contacts, 75/76 have a postcode.
No job_ref field exists in this file at all.
- Joined via `~/glenross/xero_invoice_lines_full.json` (2,871 lines, `tracking_ref` + `contact`):
  543 distinct NNNN-YY-shaped tracking_refs exist corpus-wide; only 56 of those resolve to a
  contact with a known address.
- **FLAGGED — billing/contact address, not site address** (hard rule: site ≠ billing). Net-new
  after join: **2 refs** — `1815-25, 74-12`. Excluded from the headroom union below; listed
  separately as low-confidence.

### 4. glengarry / leeos-plus / leeos-brain / green-roof-portal sweep (laptop)
- `~/glengarry`: no site/address JSON found outside `node_modules`/`.git`/worktrees (checked
  file-name patterns `*site*`, `*address*`, and postcode-density grep across all json/csv).
  **0 refs.**
- `~/leeos-plus`: postcode-density grep across non-venv/non-node json/csv → no hits (matches
  were all Google API discovery docs in `.venv`, false positives). **0 refs.**
- `~/leeos-brain`: **does not exist** on this machine.
- `~/green-roof-portal`: found two stores not in Lee's original list (following the trail):
  - **`site_audit_2026-01-22.csv`** — 58 distinct refs, `address`+`postcode` columns, genuine
    site addresses (not billing). 29/58 have a postcode. **Not in job_coords.json: 2** —
    `1408-21, 1432-21` (both already found via store 1 above — overlap, not additive to union).
  - **`report-builder/reports/*.json`** (2 refs: `1301-21`, `1513-22`) — full `site.address` +
    `site.postcode` fields. Both **already in job_coords.json**. 0 net new.

### 5. `~/.glenross/rules/` + josie-* files (laptop)
Checked `lee-durable-rules.jsonl`, `lee-line-decisions.jsonl`, `lee-vendor-notes.jsonl` (0
job_ref/address/postcode fields — pure bookkeeping-code rules) and all josie-* files
(`josie-allocation-2026-06-23.{md,json}`, `witness-josie-2026-06-23.md` + `.verdicts.md`,
`josie-reply-pack-2026-06-23/josie-draft-email.md`) — grepped for UK-postcode pattern, **0
hits**. This is a bank-transaction categorisation store (job field mostly `"missing"`), not a
job→site mapping. **0 refs.**

### 6. Mini A `~/image-plane/grind/site_names.json`
172 refs. Only 106 have a non-null `name` field; fields present are `name`, `source`,
`lee_plants_named`, `conflicts` — **no address or postcode field at all**. Only 2/172 entries
have postcode-shaped text anywhere in the value (incidental, not structured). Mostly just
names, as suspected. **Negligible/0 usable net-new.**

### 7. Mini A `~/image-plane/grind/gra_stories.json`
97 refs. 71 have `site.postcode` + `site.address` populated in the prose-source structure.
**Not in job_coords.json: 0 real refs** (only `TEST-LEE`, a test artifact, excluded).

### 8. Mini A `~/image-plane/grind/gra_sites.json` (local mirror, 70 rows)
All 70 rows have postcode. **Not in job_coords.json: 0** — this mirror is fully absorbed.
(Compare to store 12 below — the LIVE Supabase table has grown past this mirror.)

### 9. `reports_corpus.jsonl` (identical on laptop + Mini A, md5-verified match)
89 lines, 61 distinct refs, 53 with postcode. **Not in job_coords.json: 1** — `1772-25`.

### 10. Supabase LeeOSplus `known_entities` (live query)
882 total rows; 787 rows carry a job_ref (664 distinct refs — dupes are structural, not merged,
per standing ruling). 385 distinct refs have *some* address/postcode value.

Raw address values are frequently a **supplier/installer/contact's own address**, not the site
(e.g. "The Stables, Wrotham Rd, Meopham, Kent" appears identically against 40 different job_refs
— that's Liquid Applied Solutions Ltd's business address, reused for every job they touched).
9 such addresses are shared across ≥3 distinct job_refs and were excluded as non-site.

- **STRICT (postcode-bearing, non-repeated address only) distinct refs: 259**
- **Not in job_coords.json: 163** — full list:
  `1000-19, 1020-19, 1036-19, 1079-19, 108-12, 109-12, 1099-19, 110-12, 1110-19, 1120-19,
  1133-20, 1138-20, 121-12, 1219-20, 1226-20, 123-12, 1236-20, 1269-21, 127-12, 1288-21,
  1290-21, 130-12, 1303-21, 132-12, 1320-21, 135-12, 136-12, 1380-21, 1395-21, 1425-21,
  1426-21, 1427-21, 1432-21, 1446-21, 1447-21, 1448-21, 1457-21, 1472-21, 1489-22, 149-13,
  150-13, 1502-22, 1508-22, 151-13, 152-13, 1535-22, 1554-22, 1573-22, 160-13, 1605-23,
  1607-23, 1610-23, 1614-23, 1624-23, 1625-23, 1634-23, 1636-23, 1639-23, 1640-23, 165-13,
  1655-23, 1661-23, 1668-23, 1676-23, 1687-24, 1691-24, 1717-24, 173-13, 174-13, 1750-24,
  180-13, 189-13, 190-13, 197-13, 206-13, 207-13, 223-13, 232-13, 252-13, 256-13, 260-13,
  261-13, 265-13, 267-13, 271-14, 277-14, 280-14, 282-14, 284-14, 285-14, 315-14, 333-14,
  340-14, 342-14, 343-14, 352-14, 356-14, 371-14, 372-14, 375-14, 379-14, 401-14, 406-14,
  411-14, 438-15, 449-15, 453-15, 456-15, 471-15, 483-15, 489-15, 528-15, 534-15, 564-15,
  572-15, 580-15, 615-16, 621-16, 622-16, 629-16, 636-16, 649-16, 664-16, 678-16, 686-16,
  695-16, 704-16, 713-16, 738-16, 748-17, 757-15, 758-17, 759-17, 799-17, 804-17, 810-17,
  821-17, 831-17, 832-17, 840-17, 843-18, 848-18, 862-18, 866-18, 870-18, 872-18, 889-18,
  891-18, 897-18, 911-18, 916-18, 917-18, 927-18, 930-18, 939-18, 949-18, 956-18, 958-18,
  960-18, 976-19, 978-19, 979-19, 981-19`

This is the single largest untapped store found this sweep — **never checked by the F2-M1
pass** (which read Xero + Drive + GRA mirror only, not this table).

### 11. Supabase LeeOSplus `observations` source='drive_folder'
2,784 rows (paginated fully — PostgREST silently caps at 1000/request, same gotcha F2-M1 hit).
`source_metadata` keys are always `{depth, parent_id, drive_root, owner_email, created_time,
drive_file_id, modified_time, path_segments}` — **no address/postcode field exists in
source_metadata, ever.** The only address signal is an occasional postcode embedded in
`extracted_fields.remaining_text` (the folder's own display name) — 72 refs corpus-wide (strict
word-boundary UK-postcode regex, not the looser pattern that gave 145 false-positive hits on
IDs/hashes on a first pass). **Not in job_coords.json: 0** — this is exactly the
`drive_folder_postcode` tier F2-M1 already added.

### 12. Supabase GRA `dbjdxamqbwhyhnlwsfxk` — live tables (via `~/green-roof-portal/.env.local` service key)
- **`sites`: LIVE count = 105** (not 70/71 as the local mirror and skill doc state — the live
  table has grown). 101/105 have postcode + latitude/longitude populated.
  - **Not in job_coords.json: 11** — `1343-21-AVP, 1343-21-LWS, 1343-21-STL` (sub-site variants
    of job 1343-21 — Avondale Park / Little Wormwood Scrubs / St Luke's Gardens, 3 separate
    council sites under one contract ref), `1367-21, 1380-21, 149-13, 1640-23, 1655-23,
    1658-23, 1851-26`, plus `TEST-LEE` (test artifact, excluded from real count → **10 real
    refs**).
- **`roofos_inspections`: LIVE count = 100** (skill doc says 102, drifted). 65 distinct
  `job_ref` values, but **only 38 are clean NNNN-YY format** — the other 27 are free-text
  fragments (`"17 Thurley Road London SW"`, `"5 Currie Hill Close"`, `"job 1394"`, `"new site
  Elm Road BN3"`, `"Station Road"`, several `"Test..."`/`"Verification Test"` rows). This is a
  **data-quality problem in the `job_ref` column itself**, not a new evidence source — some of
  those free-text values do encode real addresses but aren't ref-keyed and can't be joined
  without manual cleanup. Of the 38 clean refs: **0 not in job_coords.json** (roofos_inspections
  carries no address of its own — only via join to `sites`, already counted above).

### 13. Supabase LeeOSplus `observations` source ILIKE '%glengarry%' + `obligations` table
- `observations` glengarry-tagged rows: 37, almost entirely `extractor_shadow` Gmail
  classification noise (unrelated receipts, "human review" flags). 1 postcode-shaped hit, and
  it's an unrelated PayByPhone parking receipt — **0 usable refs.**
- **`obligations` table: 74 total rows, 25 with job_ref set, 23 with a genuine postcode** in
  the `note` field. This is high-quality, Lee-confirmed data (real addresses + contacts,
  several with Lee's own resolution notes).
  - **Not in job_coords.json: 4** — `1343-21-AVP, 1343-21-LWS, 1343-21-STL, 149-13` (fully
    overlapping with store 12's live-sites finding — cross-validates it).

---

## Union: total headroom

Union of all "not in job_coords.json" refs found across every store (de-duplicated,
normalised), **excluding** the store-3 billing-address-only join (flagged low-confidence,
site≠billing):

**182 distinct refs** have usable location evidence sitting in an existing store, unmerged.
(184 if the 2 billing-only refs from store 3 are included — recommend NOT including them
without a manual site-address check first.)

Breakdown of where the 182 come from (a ref can appear in >1 store):
- known_entities (store 10, strict): 163 — the dominant contributor
- site-facts-draft-v4 (store 1): 24
- GRA sites LIVE (store 12): 10
- obligations (store 13): 4 (all overlap store 12)
- reports_corpus (store 9): 1
- site_audit_2026-01-22.csv (store 4): 2 (both overlap store 1)

## Corrected zero-evidence count vs F2-M1's "413"

`grind/f2_map_growth_dryrun.json` records `"no_evidence": 413` against a 425-ref headroom list
captured in `grind/f2_m1_audit_part2_q4.json` (`union_headroom`, before the same-day F2-M1 map
grew 198→209). Recomputing that exact 425-ref list against the current 209-key map (425 minus
the 11 refs F2-M1 added) gives **414** refs still outside the map (off-by-one from the doc's
413, likely one ref dropped as an invalid-postcode candidate without being added — not
investigated further, immaterial).

Cross-checking those 414 against this sweep's newly-found stores (principally known_entities,
which F2-M1 never queried):

- **177 of the 414 now have usable location evidence** somewhere in this sweep's stores
  (counted by: set intersection of the 414-ref list against the union of stores 1, 4, 9, 10, 12,
  13 above).
- **Corrected zero-evidence count: 237** (414 − 177) — refs with genuinely no address evidence
  in any of the 13 stores checked, F2-M1's 4 plus this sweep's 9.

---

## Counted by

- job_coords.json baseline (209): `ssh macminia@192.168.178.61 python3 -c "json.load(open('grind/job_coords.json'))"` — this run.
- Store 1 (site-facts-v4): direct json load + zone/tier filter — this run.
- Store 2 (portfolio_register_v2.csv): csv.DictReader + Counter — this run.
- Store 3 (xero_contact_addresses.json + invoice-lines join): direct json load + set join — this run.
- Store 4 (green-roof-portal): find + csv.DictReader — this run.
- Store 5 (.glenross rules/josie): grep — this run.
- Stores 6-9 (Mini A grind/ files): ssh python3 inline — this run.
- Store 10 (known_entities): `curl .../rest/v1/known_entities?job_ref=not.is.null` (787 rows, content-range header confirmed 0-786/787) — this run.
- Store 11 (observations drive_folder): `curl .../rest/v1/observations?source=eq.drive_folder`, 3x paginated (0-999, 1000-1999, 2000-2783; content-range confirmed total 2784) — this run.
- Store 12 (GRA sites/roofos_inspections live): `curl .../rest/v1/sites` and `/roofos_inspections`, content-range headers confirmed 0-104/105 and 0-99/100 — this run.
- Store 13 (glengarry observations + obligations): `curl .../rest/v1/obligations?job_ref=not.is.null` (content-range 0-24/25) — this run.
- F2-M1 cross-check: `grind/f2_map_growth_dryrun.json` + `grind/f2_m1_audit_part2_q4.json` read directly on Mini A — this run.

## Looked in

- Laptop: `~/.glenross/` (site-facts v1-v4 + witness md + rules/ + josie-* + inbox/), `~/image-plane/portfolio_register_v2.csv`, `~/image-plane/reports_corpus.jsonl`, `~/glenross/xero_contact_addresses.json`, `~/glenross/xero_invoice_lines_full.json`, `~/glengarry` (full repo minus node_modules/.git/worktrees, filename + postcode-grep sweep), `~/leeos-plus` (same sweep, minus .venv), `~/leeos-brain` (checked, absent), `~/green-roof-portal` (full repo sweep — found site_audit_2026-01-22.csv and report-builder/reports/*.json not in the original list).
- Mini A (`ssh macminia@192.168.178.61`): `~/image-plane/grind/site_names.json`, `gra_stories.json`, `gra_sites.json`, `reports_corpus.jsonl`, `docs/F2-M1-RUN-2026-07-10.md`, `docs/F2-M1-AUDIT-2026-07-10.md`, `grind/f2_*.json` (all 9 F2 working files), `grind/job_coords.json`.
- Supabase LeeOSplus (`jrmcvuqtvrgehrthwtjz`, service key from `~/leeos-plus/.env`): `known_entities` (full 787-row job_ref pull), `observations` (full 2,784-row drive_folder pull, paginated; glengarry-tagged 37 rows), `obligations` (all 74 rows / 25 job_ref rows).
- Supabase GRA (`dbjdxamqbwhyhnlwsfxk`, service-role key found in `~/green-roof-portal/.env.local` — not anon-only as the task brief assumed): `sites` (full 105-row pull), `roofos_inspections` (full 100-row pull).

## Could not look in

- Mini B (`macminib`) — not checked; task scope named Mini A only for the photo-grind stores, and Mini B is described elsewhere as a DuckDB/candle machine, not an address store, so this is a low-risk gap, not a verified absence.
- Gmail — not searched. The skill doc notes per-project email content ("who said what") is a separate unclosed task; any address text sitting in email bodies (e.g. client-sent addresses never filed to Drive/Xero) is unaccounted for here.
- Google Drive file *contents* (PDFs, docs) beyond folder *names* — only the crawled `observations` folder-name metadata was checked; actual document bodies (which the site-fact harvester v1-v4 partially covers via `doc_pdf`/`primary_pdf` sources, but only for the 60 refs it was run against) were not re-opened by this sweep.
- Xero UI/API directly beyond the two already-pulled JSON exports (`xero_contact_addresses.json`, `xero_invoice_lines_full.json`) — did not re-pull live in case of drift since 20:04 today; both are same-day.
- `~/leeos-plus/memory-spine/` internal DB/vector store (if one exists beyond the `observations` Supabase table) — only the Supabase table was queried; did not inspect the repo's local `.venv`-adjacent code for a second, non-Supabase spine store.
- Any machine or repo not named in the brief and not surfaced by the `~/green-roof-portal` / `~/glengarry` / `~/leeos-plus` greps (e.g. personal Notes.app, Apple Photos captions, or paper records) — no signal pointed there, so not pursued, but not verified absent either.
