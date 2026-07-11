# F6 — repo view regrouped by billable event (spec)

**Date:** 2026-07-11 late eve · **Mandate (Lee, ledgered same day, verbatim):** "i need all
the photos grouped by billable event and cross ref'd with xero, all install pics together
dont break into days or weeks, dated with a phase - if there are other ref's eg differnet
works on same roof, provide a link to that set eg 2 olympic maitnenance and repairs …
remove all duplicates". Handover: `~/leeos-private/HANDOVER-2026-07-11-PHOTO-REPO-VIEW.md`.

**Canon clause served:** every roof keeps its whole life — its photos in time order with
Lee's words on them — visible to Lee and, curated, to the customer. This build reshapes
the REPO's reading order around money-events. GRA /roof (the presentation) is OUT of
scope; ~/green-roof-portal is not touched.

**Surface changed:** the flip surface only (Mini A :8788, `flip_server.py`). The :8787
site_view hub is NOT rebuilt in this pass (separate follow-up if Lee wants the same
grouping there). PERMANENT RULE: Mini A pages are Lee-internal, never customer-visible.

## Inputs (all exist, verified 2026-07-11 this session — do not rebuild any of them)

| file (Mini A ~/image-plane/) | role |
|---|---|
| `grind/roof_invoice_match.jsonl` | 721 visit-events, job_ref + event_start + band + invoices[] (number, date, tenant, contact, description_snippet — NO amounts) |
| `grind/xero_invoice_lines_full.json` | 2,868 lines both companies (phase words live in descriptions) |
| `grind/allocation_v2.jsonl` (+ `grind/allocation_v2_flags.jsonl`) | photo→roof ties; counts join per IP-L1; existing `duplicate_of`/`dedupe_status` verdicts (240 rows) are PRIOR RULINGS — respect, never re-derive |
| `photo_ledger_merged.jsonl` | sha256 per path (16,426/16,426) |
| `takeout_ledger_merged.jsonl` | visit_type + album per takeout path (phase hint) |
| `grind/site_names.json` + `grind/flip_site_names_cache.json` | names not codes |
| `src/image_plane/phash.py` (laptop repo) | dHash-64 + hamming — the ONLY phash impl to use |

## Outputs

### 1. `grind/billable_events.json` — builder `build_billable_events.py`
Keyed by job_ref. Per roof: ordered list of event windows:
`{phase, header, start, end, band, invoices:[{invoice_number, date, tenant, description_snippet}], source_events:n}`.

Rules:
- **Phase classification** (plain words, from invoice description snippets + takeout
  visit_type; keyword map in the builder, v2 steering vocab words only):
  `Install` / `Spring roofcare` / `Summer care and haycut` / `Winter care` / `Repair` /
  `Leak detection` / `Diagnostic` / `Handover` / fallback `Visit`.
- **Merging:** (a) events sharing any invoice_number merge; (b) same-phase windows that
  overlap or sit ≤45 days apart merge; (c) **Install merges regardless of gap** unless
  two install clusters are >18 months apart (then two windows — two distinct works).
  Never emit day/week splits of one phase. Deposit→balance span = one window.
- **Header:** phase + human date span, e.g. `Install — June–September 2021`,
  `Spring roofcare — April 2023`. No snake_case, no codes.
- **£ REDACTION BY CONSTRUCTION:** builder regex-strips `£\s?[\d,.]+` (and `GBP \d`)
  from every description_snippet before writing the file; a unit assert in the builder
  fails the run if any £-amount survives. Invoice numbers/dates are allowed (they ARE
  the Xero cross-ref Lee asked for); amounts are not.
- Windows padded ±21 days for photo membership (photo joins a window if its
  allocation_v2 date ∈ [start−21d, end+21d]; nearest window wins on overlap).
  Photos in no window → the honest group `Not yet matched to billing` (IP-L2: that's a
  search task, not a fact — render it last, never hide it).

### 2. `grind/sister_refs.json` — same builder or sibling script
For each of the tied roofs: other refs that are the same roof/site.
- Confirmed tier: same NNNN, different YY or company suffix (Lee's sister-ref +
  OR/GRR cross-company rule, ledgered 11 Jul morning) AND same/compatible site evidence
  (site name / GRA address / contact match). Label = works description in plain words
  (from that ref's invoice lines / phase mix), never a bare code.
- Candidate tier: same NNNN only, no corroboration → link labelled "possibly the same
  roof". Candidates are navigation links only — NO allocation change (IP-L9).
- **Same-site tier (added after the Olympic Mews check, per Lee's 11 Jul morning ruling
  "same site can legitimately carry two distinct numbers … Extend the sister-ref rule"):**
  different NNNN, same site/development — corroborated by a distinctive shared site-name
  token (≥2 words, non-generic, e.g. "Olympic Mews") or an invoice line naming both
  addresses (1336-21 names "repairs at 2 & 3 Olympic Mews"). Link text = works
  description + site. A same-site ref with zero tied photos renders as a plain note
  ("… — no photos tied yet"), never a dead link. Builder reports every same-site group
  for orchestrator review (over-linking on generic street names is the failure mode).
- **Olympic Mews acceptance check (Lee's named example):** the builder run MUST report
  what 301-14 and 735-16 each carry (which is green-roof maintenance, which is
  waterproofing repairs) from their invoice lines, and the two pages must cross-link
  with those works as link text. Verify before labelling — do not assume.

### 3. Dedupe — `build_repo_dedupe.py` → `grind/repo_dedupe_flags.jsonl`
One verdict row per collapsed photo: `{path, duplicate_of, kind, evidence}`.
- **Exact:** identical sha256 (photo_ledger_merged) within the SAME roof → collapse to
  one keeper (earliest path wins deterministically; sort before choosing — IP-L6 spirit,
  set PYTHONHASHSEED=0 on any set iteration).
- **Near (burst):** dHash from `phash.py`, hamming ≤ 8, within same roof AND same
  visit date (±1 day) → collapse behind the keeper. Thumbs for hashing via batched
  `sips -s format jpeg -Z 640` (MANY FILES PER sips INVOCATION with --out dir — one
  call per ~200 files; reuse/populate `grind/flip_thumbs/` cache keyed by spine row id
  where ids are known, else a parallel hash-thumbs dir). Long run: nohup + caffeinate
  -dimsu + progress log; exact-dupe collapse ships immediately, near-dupe flags land
  when the pass finishes (page reads the flags file live).
- **IP-L5 HARD:** iCloud↔Takeout can never be hash-deduped (re-encode). Cross-ledger
  basename+date match → `kind:"possible_twin"` — rendered as a small honest note on the
  keeper, NEVER auto-collapsed.
- Existing allocation_v2 `duplicate_of`/`dedupe_status` rows are imported as verdicts
  (kind:"prior_pass"), not recomputed.
- **Source files are NEVER deleted** (standing rule). Verdicts are flags only.
- Durable + one truth: mirror flags to laptop; then push the same verdicts to the spine —
  additive columns on `visual_observations` (`duplicate_of text` = keeper original_path,
  `dedupe_kind text`), batched PATCH by original_path, verify-after count SQL. GRA
  presentation can then collapse identically later (no GRA work now).

### 4. `flip_server.py` regroup (the visible deliverable)
- `/flip/<ref>` renders **grouped by billable event**: big phase header (header string
  from billable_events.json) + the Xero cross-ref line under it (invoice numbers +
  dates + redacted snippets, small text); photos date-ordered inside the group. All
  existing per-photo behaviour (thumb, lee_note caption, Private⇄Public flip, footer
  live counts) unchanged.
- Collapsed duplicates: keeper shows; a per-group expander row "+N similar shots —
  tap to show" reveals them (they keep their own flip buttons when expanded). Collapsed
  ≠ hidden from flipping; nothing is deleted.
- `Not yet matched to billing` group renders last with its honest explainer line.
- Sister-ref links: under the roof title — "Also this roof: <works description> →"
  (confirmed tier) and "Possibly the same roof: … →" (candidate tier).
- Index page: unchanged columns + a small "linked works" marker where sister refs exist.
- Missing-events fallback: a roof with no events file entry renders exactly as today
  (flat date order) — the page NEVER breaks on absent grind files (fail open to the
  old view, loudly labelled "No billing map yet for this roof").
- Footer stays (live counts); no model text in caption slots (guards doctrine); no £.

## Hard constraints (priced in)
- Mini A has no git — every script lands in laptop `~/image-plane/scripts/mini_a/`,
  scp'd to Mini A, and pushed. Backups before touching any jsonl (`.pre_f6_*`).
- allocation_v2 is NOT written by this build (grouping is a read-side join).
- counts.py stays the only quotable counter; every count in receipts = same-turn query.
- 3 fails on a step = STOP and report.
- Python 3.9 on Mini A (no match statements, no PEP 604 unions).
- Flip server restart line (after edit):
  `ssh macminia@192.168.178.61 "cd ~/image-plane && nohup python3 flip_server.py > flip_server.log 2>&1 & disown"`
  — kill old PID first; :8787 hub untouched.

## Verify-after (orchestrator, same turn as "built")
1. `curl` index + 3 roof pages (Trinity 1124-19, Olympic Mews both refs, one unbilled-heavy
   roof) → HTTP 200, phase headers present, install never split, unmatched group last.
2. Screenshot the Olympic Mews cross-link + one grouped page (Lee's rendered-surface bar
   still requires HIS glance — screenshots are progress, not proof).
3. Dedupe: counts of exact/near/possible-twin from the flags file (same-turn query);
   spot-open one collapsed burst and confirm the shots really are near-identical.
4. Grep rendered HTML for `£` → must be zero hits.
5. counts.py --check green; spine row count unchanged (8,488) after dedupe PATCH
   (columns added, rows never deleted).
