# F5 — visual_observations in roof-timeline form (schema + backfill spec)

**Date:** 2026-07-11 · **Gate:** OPEN by Lee's ledgered GO (image-plane ASK-LEDGER 11 Jul,
"can you build this now … How it integrates with the GRA portal pages … the Glengarry
enquiry-job cards"). Operating rule (Lee, 11 Jul morning): default private; at the point
of sharing, curated shots flip public; Lee is the flipper.

**Canon clause served:** every roof keeps its whole life — its photos in time order with
Lee's words on them — visible to Lee and, curated, to the customer.

## What exists already (verified this session)

`public.visual_observations` on LeeOSplus (`jrmcvuqtvrgehrthwtjz`) EXISTS, 0 rows,
RLS enabled (not forced), **zero policies** (service-role-only — fail-closed). Columns
already present: id, content_sha256, phash, picture_path, thumb_path, source,
original_path, taken_at, gps_lat/lon, exif, description, model_name, prompt,
raw_response, described_at, kept, dropped_reason, tags, lee_note, tags_source,
tagged_at, job_ref, entity_id, visit_date, match_method, match_confidence(numeric),
match_status, gra_site_id, created_at, updated_at.

Decision: **extend, don't rebuild.** The old MOVE-1 shape is a superset of what the
roof timeline needs; we add only the fields Lee's spec names.

## Migration (additive only)

```sql
alter table public.visual_observations
  add column if not exists is_public boolean not null default false,
  add column if not exists public_flipped_at timestamptz,
  add column if not exists public_flipped_by text,
  add column if not exists curated_set text,
  add column if not exists building text,
  add column if not exists activity text,
  add column if not exists allocation_batch text,
  add column if not exists allocation_confidence text,
  add column if not exists gra_media_path text;

-- ENFORCEMENT BY CONSTRUCTION (compass rule 6):
-- 1. A photo cannot be public without a curated copy already exported to GRA storage.
--    (Bytes live on Mini A; the flip exports a curated copy; no path = no flip.)
alter table public.visual_observations
  add constraint vo_public_requires_gra_media
  check (is_public = false or gra_media_path is not null);

-- 2. One index row per source photo — backfill is idempotent, dupes impossible.
create unique index if not exists vo_original_path_uidx
  on public.visual_observations(original_path);

-- 3. Timeline read path.
create index if not exists vo_job_ref_date_idx
  on public.visual_observations(job_ref, visit_date);
create index if not exists vo_public_timeline_idx
  on public.visual_observations(job_ref, visit_date) where is_public;

-- 4. Customer-side read: anon/authenticated may see ONLY flipped rows.
--    (RLS already enabled; no other policies exist; service role bypasses.)
create policy vo_public_read on public.visual_observations
  for select to anon, authenticated
  using (is_public = true);
```

No trigger flips anything automatically; `is_public` changes only by Lee's flip surface
(stage 3). Default FALSE + NOT NULL means dark-ship is the only possible ship.

## Column semantics

| column | fed from | note |
|---|---|---|
| original_path | allocation_v2 `path` | Mini A path; unique key; NOT a fetchable URL |
| job_ref | allocation_v2 `job_ref` | NNNN-YY, canonical no leading zeros |
| visit_date | allocation_v2 `date` | IP-L8: date required on every row; taken_at stays NULL (no time-of-day known at this layer — never invent one) |
| building | allocation_v2 `building` | Brighton option a per-building tag |
| activity | allocation_v2 `activity` | `inactive-24m` ⇒ mining only, never live actions |
| match_method | allocation_v2 `method` | gps_nn / album / lee_cluster_answer … |
| allocation_confidence | allocation_v2 `confidence` | text labels (high / lee_confirmed); numeric match_confidence left NULL |
| allocation_batch | allocation_v2 `batch` | audit trail to the staged append |
| gps_lat/lon | geolocations.jsonl | where present |
| content_sha256 | classified/photo ledger | where present |
| lee_note, tags, tags_source | knowledge_notes.jsonl by exact path | Lee's voice only; tags_source='lee_voice'; model text NEVER enters lee_note (guards rule) |
| source | 'allocation_v2' | provenance of the index row |
| kept | true | backfill covers tied keeps only |
| is_public | — | FALSE at backfill; Lee flips per photo |
| curated_set | — | NULL at backfill; set by flip surface |
| gra_media_path | — | NULL until flip-time export to GRA storage |

## Backfill

- Source join = the counts.py join, not raw rows (IP-L1): allocation_v2.jsonl rows whose
  path is NOT in allocation_v2_flags.jsonl. Target = **8,488 rows / 246 distinct job_ref**
  (Counted by: `python3 ~/image-plane/counts.py --json` on Mini A, this session,
  counted_at 2026-07-11T15:20:57Z).
- Export script runs on Mini A (`export_visual_observations.py`, mirrored to laptop
  `scripts/mini_a/`), emits JSONL; insert runs from the laptop with
  `~/leeos-plus/.env` service key, batched upserts on original_path.
- **No photo bytes move.** Index/metadata only. thumb_path/picture_path stay NULL —
  hub thumbnails remain a Mini A tailnet concern; GRA copies exist only after a flip.
- Verify-after (same turn, SQL named in receipt): row count == 8,488; distinct job_ref
  == 246; is_public=false count == 8,488; 5 spot rows diffed against allocation_v2.

## What this deliberately does NOT do

- No GRA-side writes (stage 2), no flip surface (stage 3), no Glengarry card read
  (stage 4), no money data anywhere near the spine (egress rule — posture numbers are
  a separate Lee-gated decision).
- Candidates/provisionals (f2_candidates, quarantine files) are NOT exported — tied
  keeps only (IP-L9).
