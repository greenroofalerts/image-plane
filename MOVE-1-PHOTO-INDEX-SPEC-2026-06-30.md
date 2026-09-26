# Move 1 — Central Photo Index (connect the shed to the house)

*Anchored to LEE-411 (child of Memory Spine LEE-391). Companion to VISUAL-CORPUS-DELIVERY-MAP + IMAGE-PLANE-END-USES (2026-06-30). Status: DRAFT — building.*

## Goal
Move the photo work from a pile of local files on Mini A into the **central memory (the spine)**,
so every one of the 14 end-uses becomes a *reader* on one shared truth and nothing gets re-stored
or re-labelled per surface. This move builds **only the shelf and its labels** — no diagnosis, no
tagging engine, no packs. Those are later moves that read from this shelf.

## Confirmed facts (2026-06-30)
- **Disk:** Mini A has ~237 GB free. **Photos already live on Mini A** (157 GB extracted in
  `~/takeout-extracted` + 228 GB zipped in `~/takeout-2026-06`). No new copy, no external drive.
- **Picture cupboard = Mini A** (co-located with the describe AI; Mini B has the networking fault).
  The index stores only the *address* of each picture, so the cupboard can move later without
  touching anything else.
- Weekend describe pipeline finished (`PIPELINE_DONE`); `visit_bundles.jsonl` already exists.
- Source files on Mini A `~/image-plane/`: `takeout_ledger_merged.jsonl`, `photo_ledger_merged.jsonl`,
  `geolocations.jsonl`, `reports_corpus.jsonl`, `knowledge_notes.jsonl`, `visit_bundles.jsonl`.

## Design decision (recommended, per LEE-411 open question #1)
Photos get **their own table** (`visual_observations`), joined by ID to the existing spine entities
(sites / jobs / visits) — NOT crammed into the generic `observations` text table. Unity is at the
*entity* level (a photo, a report and a visit all point at the same job), not the physical table.

## The index — `visual_observations` (one row per photo)
*(Exact entity FK targets confirmed against the live spine before migration — see "Open: entity join".)*

| Group | Columns (plain meaning) |
|---|---|
| Which photo | `id` · `content_sha256` (identity / exact-dupe) · `phash` (near-dupe/burst) · `picture_path` (address in cupboard) · `thumb_path` |
| Where from | `source` (icloud/takeout/manual) · `original_path` · `taken_at` (EXIF) · `gps_lat` · `gps_lon` · `exif` (jsonb) |
| What it shows | `description` · `model_name` · `prompt` · `raw_response` · `described_at` · `kept` (bool) · `dropped_reason` · `tags` (jsonb) · `tags_source` (ai/lee) · `tagged_at` |
| Which job ← key | `site_id` · `job_id` · `visit_id` (FKs) · `match_method` (gps/date/postcode/manual) · `match_confidence` · `match_status` (matched/unmatched/needs-review) |
| Housekeeping | `created_at` · `updated_at` |

### Companion tables (tiny, built same move)
- **`visits`** — `id`, `job_id`, `visit_date` → one dated visit = the bundle of its photos + report.
- **`reports`** (89 already ingested) — joined to `job_id` + `visit_id` so report and photos sit together.

## Build steps
1. **Schema** — create `visual_observations` (+ `visits`, `reports` if not already present) in the
   spine, FKs to the real entity tables.
2. **Pour** — load the ~22k records (descriptions + provenance + GPS + job matches) from the Mini A
   JSONL into the index. Local files become a *backup*, not the source of truth.
3. **Addresses** — write each photo's cupboard path into `picture_path`.
4. **Visit bundles** — populate `visits` from `visit_bundles.jsonl`; link reports.

## Acceptance — the proof ladder (built in, not optional)
1. **Code** — migration runs, tables exist, tests pass.
2. **Output** — counts reconcile: index rows == kept photos in source JSONL; no missing job-link
   where a match existed; no half-finished `match_status`.
3. **Factual sample** — 12 random rows checked against the *real* picture and the *real* job:
   description matches the photo, filed to the right job.
4. **Operator** — Lee opens one job → its visits, each = photos + report, dated. *(Only rung needing Lee's eyes.)*
5. **World** — NOT YET (arrives when a real output — pack / report-attach — is used).

Completion is written **on Mini A** (watcher drops a DONE-file + proof results), not dependent on the
chat session staying awake.

## RESOLVED: entity join + home (2026-06-30)
**Decision: the photo index lives in GRA "Green Roof Portal" (`dbjdxamqbwhyhnlwsfxk`), NOT the
LeeOSplus spine.** Evidence: GRA `sites` already carries the hand-filled diagnosis fields this
project is meant to auto-produce (`vegetation_cover`, `weed_pressure`, `moss_level`,
`moisture_stress`, `substrate_depth_mm`, `condition_trend`, `bare_patches`, `wind_exposure`), plus
real `visits`, `projects` (jobs, `job_ref`), and 102 `roofos_inspections` (the reports). Photo →
site → diagnosis is one native join here; in the spine it would be a cross-database join Postgres
can't do. **Divergence from LEE-411's literal wording** ("sibling to spine observations") — flagged,
deliberate, justified by the real schema. Spine link preserved via the entity-alias graph
(`known_entity_aliases`, 1342 rows) at the entity level.

**Guard:** historical photo-bundles are NOT written into GRA's live `visits` table (operational:
fees/invoices/client confirmations) — pollution risk to the customer app. Photos carry their own
`taken_at` + `site_id`; `visit_id` is set only when a real visit exists. Bundle view is derived.

**Built + verified 2026-06-30:** `public.visual_observations` created — 30 columns, 4 FKs
(sites/visits/projects/inspections, all `on delete set null`), unique index on `content_sha256`
(idempotent reruns), indexes on site/taken_at/status + GIN on tags, RLS ENABLED (anon blocked,
service-role writes). 0 rows. **Proof rung 1 (Code) = PASS.**

## CORRECTION 2 (2026-06-30, Lee): GRA is NOT the home — moved to the knowledge plane
Per canon (`~/leeos-private/VISION-OBLIGATION-SPINE.md` + Glenross harvester): **GRA = Layer 7 product/
contact surface, "address reference only, not the authority."** The image plane belongs in the
**knowledge plane (the spine, `LeeOSplus jrmcvuqtvrgehrthwtjz`)** — which is where LEE-411 originally
put it. The earlier same-session decision to host `visual_observations` inside the GRA DB was an error
(over-weighted GRA's convenient diagnosis fields) and re-centred GRA against canon. **Fixed:** dropped
the empty table from GRA, recreated in the spine, keyed by `job_ref`, with NO FK to GRA. GRA is a
downstream **consumer** that reads by `job_ref` for its ~20 live-portal clients (the site card etc.
are GRA features that pull from the authority — that replication is correct subordination, not a bug).

## CORRECTION 1 (2026-06-30, Lee): GRA's 71 sites are NOT the site universe
GRA is a **client portal** seeded from Trello; only **~20 sites are LIVE**. The real job universe is
**hundreds of jobs** keyed `job_ref` NNNN-YY. So:
- **`job_ref` is the photo's primary "which job" key** (added to the table). It spans all jobs.
- **`site_id` / `visit_id` are OPTIONAL overlays** — populated only for the ~20 live-portal sites.
  A photo with a `job_ref` and NO `site_id` is **correct and complete**, not an orphan/failure.
- "Matched" = has a `job_ref`. Reframed: do NOT measure success by GRA-site hit rate.
- **`portfolio_register*.csv`** (was loosely called "personal register" — bad jargon; it's just Lee's
  spreadsheet list of jobs, ~198, fuller than GRA's 71) is one input to the job_ref reconciliation,
  alongside the job_refs already extracted into the photo corpus.

**Bigger direction Lee floated (captured, NOT in Move 1 scope):** this photo+description grid (with
Lee's site-visit words under each photo) could become the **maintenance-record format, replacing PDF
battles**, and a seed for **expanding GRA to cover all jobs** (not just the ~20 live). The Move 1
index keyed on `job_ref` is forward-compatible with both that and "GRA stays thin" — so the build
does not depend on resolving it now.

## RECONCILIATION FINDINGS (2026-06-30) — the matching is the real unsolved problem
All figures from live files on Mini A this session (cited):
- iCloud described: `photo_ledger_merged.jsonl` = **16,426**. Job-matched (`classified.jsonl`
  confidence ≠ None) = **3,567** (high 1,852 / folder 1,037 / medium 678). **12,859 (78%) unmatched.**
- Album/Google: `takeout_ledger_merged.jsonl` = **5,054**, but only **402 carry a job_ref**
  (45 distinct jobs); 4,652 blank. (Album names mostly don't parse to a job number.)
- Register: `portfolio_register.csv` = **198 jobs** w/ lat/lon + geocode_status (not all geocoded).
- GRA live sites: **70 real job_refs** (queried now), mostly `status=active` — the live overlay.
- Write key: PRESENT on Mini A at `green-roof-portal/.env.vercel.local` (GRA's own env, has
  service_role). Prereq "can Mini A write to GRA" = YES (verify project match when wiring).

**Headline:** of ~21,480 described photos, only **~4,000 (<20%) have any job link**, and the
intermediate files disagree on which. The "~5,100 allocated" claim was optimistic. The real job of
reconciliation is to establish ONE trustworthy job per photo. Blockers: (1) incomplete job
coordinates in the register → iCloud GPS photos can't match; (2) album names mostly lack a parseable
job number.

**Loop Proof Gate status:** Code proof PASS (shelf works). **Output proof would FAIL** — the corpus
is NOT yet job-joined for ~80% of photos. **Loop proof: NO** — missing rung = the join itself.
Do NOT pour the full set claiming "discoverable by job"; it isn't yet.

**Fork for Lee:** (A) invest in lifting the match first — geocode missing jobs, backfill job
coordinates from already-matched photos' GPS, better album parse — then pour; or (B) pour the clean
~4,000 (esp. the 402 album photos mapping to live GRA sites) as a first proof now, and treat the
12,859 unmatched as a scoped follow-on. Recommend B-first (gets the operator proof on live sites) +
A in parallel.

## PRODUCT VISION the index serves (Lee, repeated 2026-06-30 — do not lose again)
The carousel/labelling grid is a **starting point for a FORMAT, not an endpoint**. Target flow:
**roof photo + Lee's spoken comments → Lee's OWN repository (this spine-hosted image/knowledge plane)
→ downloadable client web pages that are a BETTER version of what GRA produces today**, enriched
with **weather + an event timeline + documents**. GRA's current portal = "what we have already"; this
is the improved version, with GRA as the downstream output/consumer surface, never the source. Same
thread as the maintenance-record-instead-of-PDF idea and the labelling loop (write record = teach
labels = produce client page, one act).

## What follows Move 1 (named so it can't sprawl)
**Labelling-by-situation** (F2): Lee teaches a couple-hundred *situations* by voice once each; the
system sprays each label to all look-alike photos; Lee reviews trays not singles; the system's
questions shrink as agreement climbs to 85% on a held-back set. Lee's effort is bounded by distinct
situations, not by 22k photos. Runs ONLY after this index proves.
