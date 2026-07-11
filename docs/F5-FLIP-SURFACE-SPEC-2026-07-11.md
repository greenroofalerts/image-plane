# F5 stage 3 — the flip surface (Lee-only, Mini A tailnet/LAN)

**Mandate:** photo-wiring handover step 3 — "Lee-only, tailnet — per-photo public/private
toggle per roof (GRA-operator-app pattern; one tap; no key typing). This is the gate that
makes stage 2 safe to ship dark." Ruling it implements (11 Jul, ledgered): "at the point
of sharing, everything that doesn't need to be private can be flipped public."

## Shape

`flip_server.py` on Mini A, **stdlib http.server only** (no flask on the box), port
**8788**, same bind posture as the existing :8787 hub. Creds from `~/image-plane/.env.flip`
(chmod 600, placed by laptop scp — never in git, never in chat):
`LEEOSPLUS_URL`, `LEEOSPLUS_SERVICE_KEY`, `GRA_URL`, `GRA_SERVICE_KEY`.

### Pages (Lee surfaces — names not codes, one glance)
- `GET /` — roof index: the 246 roofs with tied photos, **site name first** (join
  `grind/site_names.json` if present, else GRA `sites.site_name` by job_ref, else the
  ref), photo count, public count. Tap a roof → its flip page.
- `GET /flip/<job_ref>` — every spine row for that roof (LeeOSplus REST, service key),
  date order, LARGE thumbnails (Lee's standing size rule — one per row, full content
  width), Lee's note under each where present. Each photo: one big toggle
  **Private ⇄ Public**. Current state obvious at a glance (colour + word). Building
  shown where set (Brighton). Footer: live counts line (public n of m).

### Flip ON (the only path that moves bytes)
1. Local file → curated copy: re-encode JPEG max edge 1600px, **EXIF/GPS stripped**
   (PIL re-encode; verify PIL on Mini A first, `pip3 install --user Pillow` if absent).
2. Upload to GRA storage bucket `roof-photos` (private) at `<job_ref>/<sha256-16>.jpg`
   via GRA service key.
3. PATCH spine row: `gra_media_path`, then `is_public=true`, `public_flipped_at=now`,
   `public_flipped_by='lee-flip-surface'`. (Single PATCH is fine — constraint checks
   the row state, and gra_media_path is in the same update.)
4. On any upload failure: NO spine change (fail closed).

### Flip OFF (revoke)
PATCH `is_public=false`, delete the GRA storage object, null `gra_media_path`,
null curated fields. Signed URLs die within 1h (their TTL); storage gotcha noted —
private bucket + object deleted = gone.

### Guards
- Server refuses to start without both service keys (fail closed).
- Only rows whose `original_path` exists on disk can flip ON (no path = no copy = error
  shown plainly on the page).
- No model text anywhere on the surface: captions = lee_note only (guards.py doctrine).
- Thumbnails on the flip page come from LOCAL files (`/thumb?id=` endpoint, sips/PIL
  downscale, cached under `grind/flip_thumbs/`) — the flip page never depends on GRA.

## Proof (this session)
- Index + flip page render (curl + headless screenshot via laptop).
- One REAL end-to-end flip on Trinity 1124-19: flip ON one photo → spine row public,
  object in bucket, GRA API route (stage 2, local dev) returns it; then flip OFF →
  0 public rows again, object gone. **Egress ledger line required** for the one curated
  copy (downscaled, EXIF-stripped, private bucket, deleted same session).
- Restart story: `nohup python3 ~/image-plane/flip_server.py &` documented; script
  mirrored to laptop `~/image-plane/scripts/mini_a/` and pushed (Mini A has no git).

## Out of scope
Auth beyond mesh posture (same as :8787 hub — Lee's call if he wants more), Brighton
per-building pages, bulk flip, Glengarry (stage 4).

## Built + proof results (2026-07-11, this session)

**Files:**
- Laptop (git mirror): `~/image-plane/scripts/mini_a/flip_server.py`
- Mini A (live): `~/image-plane/flip_server.py`, running as `nohup python3 flip_server.py > flip_server.log 2>&1 &`
- Restart line: `ssh macminia@192.168.178.61 "cd ~/image-plane && nohup python3 flip_server.py > flip_server.log 2>&1 & disown"`
- New data files on Mini A: `grind/flip_site_names_cache.json` (172 site_names.json entries
  covered 172/246 roofs; the other 74 resolved by a live GRA `sites.address` pull, cached here
  for GRA-outage resilience), `grind/flip_thumbs/*.jpg` (local-only downscaled 640px thumbnails,
  one per photo viewed so far — never uploaded anywhere).
- One deviation from the spec text: GRA `sites` has no `site_name` column (confirmed via schema
  probe — `sites.site_name does not exist`). Used `sites.address` instead (e.g. "25 Trinity
  Cres"), which is the project's established site-identity field per
  `~/glenross/docs/product-control/GLENROSS-SITE-FACT-HARVESTER-V3-2026-06-23.md`
  (site = doc top recipient block, i.e. the address). `grind/site_names.json` (Lee's curated
  names, e.g. "25 Trinity Crescent") still takes priority; GRA address is the fallback only.

**Proof ladder (Loop Proof Gate):**

| Stage | Result |
|---|---|
| 1 Code | PASS — server starts, fails closed without all 4 keys (tested during build via the missing-key path in `_missing` check logic), no protected files touched |
| 2 Source | PASS — LeeOSplus `visual_observations` (service key) and GRA `sites`/`roof-photos` storage (service key) are the only sources; both live-queried, not cached (except the name-resolution GRA-address cache, which is explicitly a fallback file, not a source of truth) |
| 3 Rerun | PASS — restart line above regenerates the running server from the committed file with no chat memory involved |
| 4 Output | PASS — index counts (246 roofs / 8,488 photos / 0 public) match `counts.py --json` `roofs_with_tied_photos` and `allocated_keeps` for this same session; footer counts recomputed live client-side after every flip, never cached |
| 5 Factual sample | PASS — one real photo (1124-19, IMG_9667.HEIC, Lee's own `lee_note` present) flipped ON then OFF end-to-end against the real LeeOSplus row and real GRA storage bucket, not a fixture |
| 6 Operator | PASS — Lee taps a name (not a code), sees a big photo, one big Private⇄Public button, obvious colour-coded state, live counts; no key typing, no model text anywhere on the surface |
| 7 World | NOT YET — this is a Lee-only tool; "world proof" here means Lee actually uses it to flip photos for a real customer-facing send, which hasn't happened yet |

**Loop proof achieved: NO** — stage 7 (World) is NOT YET; stages 1–6 all PASS.

**Step-by-step:**

1. **Deploy** — PASS. `flip_server.py` written locally, scp'd to Mini A, started with the
   restart line above. Two bugs caught and fixed during first boot: (a) a stray
   `&Range-Unit=items` querystring fragment in the GRA site-address fetch (PostgREST rejected
   it — `Range-Unit` is a header, not a filter; fixed), (b) a stale process left over from the
   first crashed boot attempt held port 8788 (killed before clean restart). Current PID: **83132**.
2. **Renders** — PASS. `GET /` returns HTTP 200, 246 roofs / 8,488 photos / 0 public, names
   resolved (site_names.json + GRA address fallback), sorted by name. `GET /flip/1124-19`
   returns HTTP 200, 83 photo rows, date-ordered, full-width thumbnails via `/thumb?id=`,
   Lee's own `lee_note` rendered in a labelled caption box, live footer "0 of 83 public".
   Screenshots: `flip-index.png`, `flip-1124.png` (both in the scratchpad path below).
3. **Real end-to-end flip ON** — target: row `52398057-5c46-492c-9307-78b2c958f5a8`
   (`1124-19/IMG_9667.HEIC`, dated 2021-06-30, the earliest photo on that roof carrying a
   `lee_note`). `POST /flip {id, public:true}` → HTTP 200.
   - (a) LeeOSplus row (checked ON Mini A, service key stayed there): `is_public=true`,
     `gra_media_path="1124-19/fcfb708448d8306b.jpg"`, `public_flipped_at=2026-07-11T15:53:44Z`,
     `public_flipped_by="lee-flip-surface"`, `curated_set="flip-surface-max1600-exif-stripped"`.
     **PASS**
   - (b) GRA storage object exists: authenticated cache-busted GET → HTTP 200; storage `list`
     API (bypasses Cloudflare CDN cache — see CDN gotcha below) confirms
     `1124-19/fcfb708448d8306b.jpg`, 406,150 bytes, `image/jpeg`. **PASS**
   - (c) Raw public URL (`/storage/v1/object/public/roof-photos/...`, no auth) → HTTP 400
     (private bucket blocks it outright). **PASS**
   - (d) Curated copy downloaded and inspected with PIL: size **1600×1200** (max-edge respected),
     `im.getexif()` → **empty**, `im.info` keys → only JFIF markers, no Exif/GPS. **PASS**
   - Screenshot `flip-1124-public.png` (via `?only=<id>` — a small additive query param added
     to `render_flip_page` purely so a proof screenshot can jump straight to one row instead of
     scrolling a giant page; changes nothing about what exists, only what's displayed) shows the
     photo with a green **PUBLIC** badge and "Public — tap to make Private" button.
4. **Real end-to-end flip OFF** — same row. `POST /flip {id, public:false}` → HTTP 200.
   - Row: `is_public=false`, `gra_media_path=null`, `curated_set=null`. `public_flipped_at`/
     `public_flipped_by` were left as the historical last-flip record (not cleared) — the spec
     only requires nulling `gra_media_path` and curated fields, not erasing the audit trail.
     **PASS**
   - Storage `list` for prefix `1124-19/` → `[]` (truly deleted at origin, not just
     CDN-fronted). Cache-busted authenticated GET → HTTP 400. **PASS**
   - Corpus-wide public count (`is_public=eq.true`, `Prefer: count=exact`) → **0**. **PASS**
   - Index re-fetched: footer back to "0 public". **PASS**
5. **CDN gotcha hit and handled**: an early probe on a throwaway object showed a plain
   authenticated GET returning HTTP 200 with `cf-cache-status: HIT` for tens of seconds *after*
   the object was actually deleted at origin — Cloudflare fronts the Supabase storage GET
   endpoint (matches the known gotcha in `reference_gra_storage_cdn_gotcha.md`: "private bucket
   != CDN purge"). The reliable non-CDN check is the storage **list** API (reads the Postgres
   `storage.objects` table directly) or a cache-busted querystring on the GET. Both were used
   above for the real verification steps, not the plain GET alone.
6. **Server left running** — PID 83132, listening on `:8788`, untouched (per instructions). The
   existing `:8787` hub (`python3 -m http.server`) was not touched.

**Egress ledger** (the one allowed byte movement this session):
- **What left the mesh:** one curated JPEG derived from
  `/Users/macminia/icloud-export-2026-06/2021/06/30/IMG_9667.HEIC` (job 1124-19, visit
  2021-06-30) — re-encoded to 1600×1200 max-edge, EXIF/GPS fully stripped (verified above),
  406,150 bytes.
- **Where it went:** GRA Supabase storage, private bucket `roof-photos`, object
  `1124-19/fcfb708448d8306b.jpg`, project `dbjdxamqbwhyhnlwsfxk`.
- **When:** uploaded 2026-07-11T15:53:44Z; deleted same session (flip-OFF step above), confirmed
  gone via the storage `list` API (not just a CDN-fronted GET) at ~2026-07-11T15:56Z.
- **Anything else:** no other photo bytes moved. `/thumb` thumbnails are generated and served
  from Mini A only, never uploaded. The `flip_site_names_cache.json` write is GRA `sites`
  address/job_ref metadata (already accessible to GRA's own service key), not photo bytes.

**Screenshots** (in `/private/tmp/claude-501/-Users-Lee/6719cf45-5787-4a6d-9703-d8f68e633893/scratchpad/`):
`flip-index.png`, `flip-1124.png`, `flip-1124-public.png`.

**Final LeeOSplus counts** (queried this session): 8,488 total rows, 0 public rows, 246 distinct
`job_ref`. Flip server PID 83132.
