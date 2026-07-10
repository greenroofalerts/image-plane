# CURRENT_STATE.md — image-plane (LEE-411)

**Last updated:** 2026-07-10 late eve (F1+F2 machine passes complete; canon trio RATIFIED by Lee's
"go in new window, handover"; F2 CANDIDATE PASS + F3 READINESS chain hands to a fresh window
via ~/leeos-private/HANDOVER-2026-07-10-IMAGE-PLANE-CANDIDATE-PASS.md).

## Corpus state (Counted by: `python3 ~/image-plane/counts.py --json` on Mini A, 2026-07-10 ~22:30)
- 12,338 kept photos · **8,111 tied to a roof (66%)** · 4,227 not (3,528 with GPS, 699 without)
- 238 roofs have tied photos · job map `grind/job_coords.json` = 419 refs
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
1. Fresh window runs the ratified F2 CANDIDATE PASS + F3 READINESS chain (Steps 1–4) from
   the handover; no tie count may increase; candidates quarantine-only.
2. Lee's sheet answers (any window, dictation fine).
3. F3 build (Trinity rollout to 238 roofs) gated on Lee seeing SPINELINE-READINESS.md.

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
