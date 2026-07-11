# CURRENT_STATE.md — image-plane (LEE-411)

**11 Jul late eve — PHOTO WIRING BUILT (stages 1–3 of HANDOVER-2026-07-11-PHOTO-WIRING.md):**
- **F5 DONE**: `visual_observations` @LeeOSplus extended (is_public default FALSE +
  check constraint: public REQUIRES gra_media_path — dark-ship enforced by construction;
  anon RLS policy sees only public rows) and backfilled **8,488 rows / 246 roofs**
  (Counted by: counts.py --json same session; verified by independent SQL after insert).
  0 public. Spec: docs/F5-VISUAL-OBSERVATIONS-ROOF-TIMELINE-2026-07-11.md. Customer
  captions come ONLY from new `public_caption` column — lee_note (internal dictation)
  structurally never renders customer-facing.
- **GRA /roof timeline BUILT, branch-only** (`roof-photo-timeline` in ~/green-roof-portal,
  d06f4ff + bfca1ae, NOT merged — Lee-gated): /api/portal/roof-photos (anon spine read,
  signed URLs from new private GRA bucket `roof-photos`) + RoofStory section; empty state
  + synthetic end-to-end + RLS + negative storage tests all proven locally, screenshots
  in session scratchpad. Prod needs LEEOSPLUS_URL/LEEOSPLUS_ANON_KEY in Vercel at merge
  time (routing-proof item).
- **FLIP SURFACE LIVE (Lee-only, mesh): http://192.168.178.61:8788/** — flip_server.py on
  Mini A (mirror scripts/mini_a/, restart: nohup python3 ~/image-plane/flip_server.py
  > flip_server.log 2>&1 &). One-tap Private⇄Public per photo; flip-ON = curated copy
  (max 1600px, EXIF/GPS stripped) → GRA bucket → spine row, fail closed; flip-OFF
  revokes + deletes object (verify deletions via storage LIST api — Cloudflare caches
  GETs). Real flip ON+OFF proven on 1124-19; egress ledger in
  docs/F5-FLIP-SURFACE-SPEC-2026-07-11.md. Creds: Mini A ~/image-plane/.env.flip (600).
- **Stage 4 (Glengarry card) deliberately NOT built**: Lee's same-day ruling blocks the
  project-page design on the record-view comparison. Ammunition doc:
  ~/leeos-private/CARD-PHOTO-PRICE-AMMUNITION-2026-07-11.md (money stays local).
- Open from this build: public_caption curation UI (typing — Lee-gated design), Brighton
  per-building pages, sister-ref join on the GRA route, Vercel envs + merge (Lee gate).

**Last updated (prior):** 2026-07-10 night (F2 CANDIDATE PASS + F3 READINESS chain COMPLETE, Steps 1–4.
Cluster sheets + ambiguous.html rebuilt WITH ranked provisional candidates — browser-curled;
SPINELINE-READINESS.md written (228 READY / 10 NEEDS-RULE, orchestrator correction: all 7 "EXIF
conflicts" are 2026-06-25 export artifacts → true NEEDS-RULE = 4 low-coverage roofs). Tie count
held 8,111 → 8,111 (counts.py before/after — candidates quarantine-only, IP-L9).
New quarantine files: grind/f2_candidates.json (v2; .v1 backup) + grind/f2_trello_quarantine.json
(901 rows: 284 new refs vs the 419-map, 35 known refs w/ new postcode, source=trello).
Trello swept for the first time: 49/49 boards, 3,450 cards; OR MAIN + Revival Main are the only
job boards. F3 stays gated on Lee seeing SPINELINE-READINESS.md.)

## Corpus state (Counted by: `python3 ~/image-plane/counts.py --json` on Mini A, 2026-07-11 ~15:00; r3: c11=917-18 Lake Cottage Smallfield +27, solved via Lee's "Burstow-Smallfield" plan photo + Trello quarantine 0.36km hit)
- 12,338 kept photos · **8,355 tied to a roof (68%)** · 3,983 not (3,284 with GPS, 699 without)
- **245 roofs** have tied photos · job map `grind/job_coords.json` = 419 refs
- Round 2 promotion 11 Jul midday: +104 ties (Wales NRW 1051-19 c3=52, Raasay Olli Blair
  175-13 c5=35, Avon Tyrrell 261-13 c20=17), refs given by Lee, Xero-verified; backup
  allocation_v2.jsonl.bak_pre_f2answers_r2_20260711. NOTE: 175-13 + 261-13 map coords are
  >2km from their confirmed clusters — likely billing addresses; quarantined correction
  queued (handover Q5), job_coords NOT edited.
- **RESUME: ~/leeos-private/HANDOVER-2026-07-11-IMAGE-PLANE-NEXT.md** (case-studies×profit
  via WealthOS repo — never ibkr-history; ref-resolution c1/c2/c11/c13/c15; HayBase
  collateral; plant IDs; gated sheets rebuild).
- **11 Jul late PM — BUILD GO (ledgered): GRA roof photo timelines + Glengarry card
  photo/price layer. F5 gate OPEN in roof-timeline form. RESUME:
  ~/leeos-private/HANDOVER-2026-07-11-PHOTO-WIRING.md — fresh window, this one at 150%.**
- **11 Jul ~15:45 — Lee ruled "apply both coord corrections, brighton option a" (ledgered):**
  job_coords 175-13→Raasay GPS median, 261-13→BH23 8EE (backup .bak_pre_coordfix_20260711);
  Brighton c1+c2 → umbrella ref 307-14 with building on every row (varley-halls 67 /
  sports-centre 66), batch f2-brighton-optionA-20260711 via the staged path (0 dateless,
  0 overlap; backup allocation_v2.jsonl.bak_pre_brightonA_20260711). Counts 8,355→**8,488
  tied**, roofs 245→**246** (counts.py after flags rebuild). 307-14 tagged inactive-24m
  (latest UoB invoice 2022-05-08) — mining/knowledge only, never live actions. Off-machine
  ground-truth copies refreshed (~/Backups/image-plane-mini-a/). site_view rebuild kicked.
- **Post-answers queue window, 11 Jul afternoon (earlier same session; no allocation moves
  during it):**
  - **Q1 DONE** — case-studies×profit re-rank at
    `~/leeos-private/pricing-study/CASE-STUDIES-PROFIT-2026-07-11.md` (leeos-private
    @9cec9ff). Profit from the local Xero pull, nothing guessed. Headlines: Brighton Uni
    maintenance = new #1 (307-14, £54k income, 69% over tagged); Avon Tyrrell's existing
    case study FOUND (`~/Dropbox/Collateral/Archives - DO NOT USE/261-13 Avon Tyrrell
    Case Study/Update Boathouse Story.pdf`); HayBase named set (incl. 917-18) 55% margin
    on £63.6k; margin-by-type table built + verified (77% of tracked income honestly
    unknown-system).
  - **Q2** — Brighton Uni money-side RESOLVED: since 2014 ONE umbrella ref (307-14-M →
    307-14-COM-M) covers Checkland/Huxley/Varley/Sports Centre; tie rule is Lee's pick →
    `grind/brighton_uni_tie_proposal_20260711.json` (Mini A, quarantine). c13 lead:
    never-paid job invisible in local pull because VOIDED invoices were excluded —
    voided re-pull is the search key. c13/c15 deep sweep + Q4 plant-IDs ran as sonnet
    doers (findings docs in docs/ when landed).
  - **Q3** — HayBase collateral PROPOSAL (Lee-gated, nothing published):
    `~/leeos-private/HAYBASE-COLLATERAL-PROPOSAL-2026-07-11.md`. One-glance asks inside
    (img12 date Sept-22 vs Oct-20; honest-aesthetics line; mock go/no-go).
  - **Q5 DONE (proposal)** — coord corrections QUARANTINED
    (`grind/coord_corrections_quarantine_20260711.json`, Mini A): 175-13 pin = West
    Drayton gmail false-positive vs 35/35 photos on Raasay; 261-13 pin = solar sub's
    Kent address vs site BH23 8EE (maintenance-contract PDF). job_coords NOT edited.
- First Lee-answer promotion 11 Jul: +113 ties via cluster answers (Tony Whitbread 1156-20,
  Spyways 885-18, Royal Holloway 1103-19, Bannut House 1688-24), applied from
  grind/f2_confirmed_ties_staged.jsonl after verification; allocation backup
  allocation_v2.jsonl.bak_pre_f2answers_20260711. Cluster answers captured:
  grind/cluster-answers-raw-dictation.txt + cluster-answers-interpreted.json;
  knowledge_notes 235→388 rows (backup .pre_f2clusters_20260711).
- DO NOT rebuild the cluster sheets until Lee finishes answering (17 + 19 open) —
  a rebuild renumbers clusters mid-conversation. Not-a-job cluster exits (6,8,9,10,16,18;
  157 photos) staged in the same file, consumed at next rebuild.
- Map sources: portfolio 148 · known_entities 151 · gmail 43 · xero_contact 29 · gra 22+7 ·
  drive-folder-names 9 · site-facts 9 · xero-desc 1

## Proven / live (data-level; operator proof = Lee's glance, NOT YET)
- F1 guards live on Mini A (`guards.py`, tests 11/11): captions ground-truth-only, species
  name ⇒ reference image structurally, one-glance counts footer on every page.
- `counts.py` canon + `allocation_v2_flags.jsonl`; `--check` green.
- Hub (Mini A :8787 → `grind/site_view/`): 243 job pages + cluster sheets
  (`cluster-sheets-r1.html`, 20 clusters/613 photos) + `ambiguous.html` (33, of which 20
  missing on disk) — all with how-to-answer blocks, awaiting Lee's answers via the 2 Jul
  dictation→ground-truth loop.
- Drive ref→folder index: `grind/drive_folder_index.json` (1,230 folders, 4 trees, 18
  cross-tree ref collisions; NEVER commit — client names).

## Active proof case
Lee's cluster answers → ties climb via the capture loop (no machine promotion of
candidates — IP-L9).

## Next blocker
1. Lee answers the cluster sheets — now with ranked candidates as tap/say-able options
   (http://192.168.178.61:8787/cluster-sheets-r1.html) — via the 2 Jul dictation →
   ground-truth loop, unchanged. Ties advance ONLY through his answers.
2. F3 build (Trinity rollout to 238 roofs) gated on Lee seeing docs/SPINELINE-READINESS.md
   (incl. the export-artifact correction — proposed rule: EXIF stamped in the 2026-06 export
   window = treat as missing, use path-date).

## Unrun/parked paths (honest)
Full Drive doc read (204 indexed folders, pilot yield ~12%/ref, ~2M tokens — Lee's call);
calendar access (never connected); visual matching (speculative). 273+9 logged conflicts
+ 36 Gmail-disagreement refs parked in conflict files, unreviewed. 407 keeps missing on
disk (F8 look-list). visual_observations still 0 rows (F5 = Lee gate).

## Files changed tonight (mirrors @ laptop repo main…156fc4f, all pushed)
F1/F2 specs + run docs (`docs/F1-*.md`, `F2-*.md`), `scripts/mini_a/*` mirrors (counts,
guards, flags, builders, f2 passes), Ask Ledger, this canon trio. On Mini A: guards,
counts, flags, job_coords (+dated backups), allocation_v2 (+1,257 rows tonight, append-only),
site_view rebuild, cluster/ambiguous sheets, drive_folder_index.
