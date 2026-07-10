# F2 CANDIDATE PASS + F3 READINESS — execution spec — 2026-07-10 late

Mandate: Lee's verbatim order in `docs/product-control/ASK-LEDGER.md` (2026-07-10 entry).
Handover: `~/leeos-private/HANDOVER-2026-07-10-IMAGE-PLANE-CANDIDATE-PASS.md`.
Executor: Fable specs + verifies; sonnet doers execute one step each.

**Self-gate (Cherny): Step 1 = 97/100 · Step 2 = 97/100 · Step 3 = 97/100 · Step 4 = 97/100 · Chain = 97/100.**

## Chain-wide law (every doer reads this block)

- Machine: Mini A `ssh macminia@192.168.178.61`, project `~/image-plane/` (NO git there —
  mirror every new/edited script back to laptop `~/image-plane/scripts/mini_a/`).
- FORBIDDEN (read-only, never edit): `knowledge_notes.jsonl` (+ any ground-truth capture
  file), `counts.py`, `guards.py`, `tests_guards.py`, anything under `~/glenross/`,
  `~/glengarry/`, GRA Supabase writes. **NO writes to `allocation_v2.jsonl` or
  `grind/job_coords.json`** — the tie count must stay 8,111. Candidates/new addresses go to
  NEW quarantine files under `grind/` only.
- Candidates are PROVISIONAL (IP-L9): never promoted, never written as ties, never merged
  into the map.
- Every count you report: name the exact command run that turn (IP-L1; counts.py is the only
  quotable corpus source).
- Any "missing/no evidence" claim: state everywhere you looked AND everywhere you could not
  (half-search rule, IP-L2).
- No external calls except `postcodes.io` (postcode→coords) and `api.trello.com` (Step 2).
  NEVER reverse-geocode photo GPS via any external API. Photo bytes never leave Mini A.
- PYTHONHASHSEED=0 on anything that clusters or iterates path sets (IP-L6).
- 3 fails on any step = STOP, report the wall, do not improvise.
- Back up any file before editing it: `cp X X.pre_candidates_20260710`.

## STEP 1 — dates↔invoices candidate engine

New script: Mini A `~/image-plane/f2_candidate_engine.py`. Output: `grind/f2_candidates.json`
(quarantine). No other writes.

1. Derive the residual clusters FRESH using the IDENTICAL algorithm in
   `build_f2_phaseL.py` (lines ~56–105: residual set derivation + single-link 150m
   clustering, top 20 by size). Run with `PYTHONHASHSEED=0`. Copy the code path, do not
   edit the builder in this step. Sanity-gate: cluster count and top-20 sizes must match
   what the builder produced (check `grind/f2_cluster_answers_template.json`); if they
   differ, STOP and report — do not proceed on drifted membership.
2. Per cluster: compute centroid (mean lat/lon) and photo-date span (the builder already
   captures photo dates — reuse its date source; where a photo has no EXIF/ledger date,
   fall back to path-date and note it).
3. Dated job events, three sources (all local, all exist as of tonight):
   - `grind/xero_invoice_lines_full.json` (refreshed 10 Jul 20:51, carries `date` +
     `tracking_ref` + `contact` + `description`) — map lines to job_ref via tracking_ref;
     lines without tracking_ref are usable only via roof_invoice_match.
   - `grind/roof_invoice_match.jsonl` (665 lines, `job_ref` + `event_start` + band) —
     use bands exact/strong/likely; ignore weak/unbilled for candidate evidence.
   - `grind/gra_stories.json` visit/inspection dates per job_ref.
4. Candidate rule: job is a candidate for a cluster iff it has ≥1 dated event within the
   cluster's photo-date span ±14 days AND (where the job has coords in
   `grind/job_coords.json`) is within 2km of the centroid. Score = date overlap tightness
   + proximity; rank; keep max 3. A job already tied to the cluster's photos cannot occur
   (they're residual by construction) — assert that.
5. The 33 ambiguous photos (`unallocated_no_coords ∩ missing-on-disk` — the ambiguous.html
   set; membership from the builder's ambiguous derivation, files
   `f2_ambiguous_excluded*.json`): date-only candidates (no proximity leg), same ±14-day
   rule on path/ledger dates, max 3, flagged `date_only: true`.
6. Output record per cluster/ambiguous photo: cluster id, photo count, date span, centroid,
   ranked candidates each with: job_ref, site NAME (resolve `grind/site_names.json` →
   `gra_stories.json` → postcode/street from the evidence row — never a bare code),
   evidence line in operator English ("invoiced 12–18 Mar 2022, 0.4km away"), and the
   underlying evidence rows (source file + index) for spot-check.
7. Report: candidates found per cluster (0 is honest), zero-candidate clusters listed.

## STEP 2 — Trello sweep

New script: Mini A `~/image-plane/f2_trello_sweep.py`. Creds: `~/leeos-brain/.env`
(`TRELLO_API_KEY`/`TRELLO_TOKEN` — verified live tonight, 49 boards). Output:
`grind/f2_trello_quarantine.json` + rescore of `grind/f2_candidates.json` (write v2 in
place, keep `.v1` backup).

1. Pull ALL boards including closed (`/1/members/me/boards`), then all cards per board
   (`/1/boards/{id}/cards/all` — name, desc, due, dateLastActivity, labels, closed).
   Rate-limit friendly (sleep between board pulls).
2. Extract per card: job refs (`\b\d{3,4}-\d{2}\b` in name+desc), UK postcodes (standard
   regex), free-text addresses lines, dates (due, dateLastActivity, dates written in text
   if trivially parseable). Keep board name + card id for provenance.
3. Geocode extracted postcodes via postcodes.io ONLY.
4. Diff refs+addresses against `grind/job_coords.json` (419 refs): new refs, known refs
   with new address/postcode, address-only cards. ALL land in the quarantine file with
   `source: "trello"` — job_coords.json is NOT touched.
5. Re-run Step 1 scoring including Trello dated events (card dates count as job-activity
   evidence, labelled so in the evidence line: "on the OR MAIN board that month").
6. Report yield honestly: cards scanned, refs found, NEW refs vs the 419, postcodes
   geocoded, candidate changes per cluster (including zero).

## STEP 3 — rebuild sheets with candidates

Edit: Mini A `~/image-plane/build_f2_phaseL.py` (back up first:
`.pre_candidates_20260710`). Rebuild `grind/site_view/cluster-sheets-r1.html`,
`cluster-01..20.html`, `ambiguous.html`.

1. Each cluster page opens with its ranked candidates as tap/say-able options:
   "1. Litten Path — invoiced that week, 0.4km." / "2. …" / last option always
   "None of these / other". Evidence line under each in plain English. NO source enums,
   NO raw scores, NO job codes without names (Names-not-codes; code may appear after the
   name, e.g. "Litten Path (1479-21)").
2. Keep: how-to-answer blocks (IP-L3), free-dictation fallback wording, the 2 Jul
   ground-truth capture path unchanged, `guards.counts_footer()` on every page.
3. Run with `PYTHONHASHSEED=0`. Zero-candidate clusters say so plainly ("no invoice or
   board activity matches this cluster's dates — dictate freely").
4. Verify: curl every page, assert candidate block present on pages where candidates
   exist, counts footer present, thumbs still resolve. Report curl results per page.

## STEP 4 — F3 spineline readiness audit (read-only; F3 does NOT start)

New script: Mini A `~/image-plane/f3_spineline_readiness.py`. Output:
`~/image-plane/docs/SPINELINE-READINESS.md` (+ machine-readable
`grind/spineline_readiness.json`). NO other writes.

1. For each of the 238 roofs (job_refs from the allocated-keeps join — same join as
   counts.py, do NOT re-implement counting logic differently: derive the set by reading
   allocation_v2.jsonl minus flags, as counts.py describes).
2. Per photo: EXIF timestamp via `mdls -name kMDItemContentCreationDate` (batch mdls calls,
   many files per invocation). The ~407 keeps missing on disk cannot be EXIF-read:
   path-date only, flagged `no_exif_missing_on_disk`. Ledger dates
   (`photo_ledger_merged.jsonl`) may be used as corroboration, not substitute.
3. Per roof: photo count · % with usable EXIF timestamps · order-conflict flags (EXIF order
   vs album order (takeout album names) vs filename order vs known visit dates from
   `roof_invoice_match.jsonl`/`gra_stories.json` — the known 2-year album-vs-date conflict
   pattern generalises) · verdict READY or NEEDS-RULE.
4. For NEEDS-RULE roofs: PROPOSE (do not implement) the fallback ordering rule.
5. SPINELINE-READINESS.md: one table row per roof (site NAME + ref), summary header with
   counts (each with its Counted-by command), NEEDS-RULE section with proposed rules.

## Verification (Fable, after each step)

- counts.py before/after chain: allocated_keeps 8,111 → 8,111 (proof of no promotion).
- Step 1/2: spot-check 5 candidate evidence lines against real Xero rows + 5 against real
  Trello cards, quoted in final report.
- Step 3: curl checks re-run by Fable, not trusted from doer.
- Step 4: spot-check 3 roofs' EXIF ordering by hand (mdls on a few files).
- Mirror + commit: all new scripts → laptop `scripts/mini_a/`, docs → `docs/`, commit,
  push, hash in receipt.
