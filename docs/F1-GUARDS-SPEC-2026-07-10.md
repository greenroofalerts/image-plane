# F1 SPEC — Truth guards in the builders (D2/D3/D4) — 2026-07-10

Source: `DELTA-IMAGE-PLANE-2026-07-10.md` Part 3, F1 + the same-day correction. Lee's go given
10 Jul (handover pasted back with the order confirmed). Everything here runs on **Mini A**
(`macminia@192.168.178.61`, `~/image-plane/`). Raw photo data and site rows stay on Mini A;
only counts and pass/fail results come back.

Enforcement-by-construction requirement (machine-wide rule, 10 Jul): each guard must make the
breach IMPOSSIBLE at the render/data layer, not documented-against. Every receipt names the
constraint built.

## Item A — canonical counts + un-misreadable allocation data (data layer; no builder edits)

1. **`~/image-plane/counts.py`** (Mini A) — THE single source for corpus numbers. Derives, by
   the join (never a row count):
   - kept / dropped / quarantined (from `classified.jsonl` verdicts)
   - allocated keeps = keeps ∩ allocation_v2 live-with-job-ref rows (subtract excluded,
     no-ref, non-keep paths)
   - unallocated keeps, split: gps-but-no-job / no-coords / also-missing-on-disk
     (join `geolocations.jsonl`, `grind/kept_missing_on_disk.json`)
   - roofs-with-tied-photos count
   - takeout/iCloud overlap: takeout rows with and without an iCloud twin (the never-counted
     number — dedupe key: content hash if present in both ledgers, else basename+bytes;
     state the key used in the output)
   Output: human line(s) AND `--json`. Every field carries `counted_by` (the join described in
   one line) and `counted_at` (ISO timestamp). Expected magnitudes 10 Jul: 12,338 keeps ·
   6,563 allocated · 5,775 unallocated (4,966/809/407) — if your run differs, print the diff,
   do not "fix" data to match.
2. **Mark the misreadable rows**: write `grind/allocation_v2_flags.jsonl` (path/id + flag:
   `excluded` | `no_job_ref` | `non_keep_path`) so 269+82+185 rows are machine-distinguishable.
   Do NOT rewrite `allocation_v2.jsonl` itself (grind scripts read it). counts.py must consume
   the flags file. If regenerating allocation_v2 ever happens, flags regenerate with it —
   note that in a header comment.
3. **Self-test**: `counts.py --check` recomputes and asserts internal consistency
   (allocated + unallocated = keeps; splits sum). Non-zero exit on failure.

## Item B — render guards in the sheet/page builders (builder edits only; import-only
dependency on Item A's interface)

New shared module **`~/image-plane/guards.py`** (Mini A), imported by every builder that ships
a Lee- or client-facing surface. Builders in scope (all Mini A `~/image-plane/`):
`build_site_view_v2.py`, `build_job_view.py`, `build_plantid_contest_sheet_v2.py`,
`build_guess_sheet.py`, `build_closeup_retest_sheet.py`, `build_batch.py`,
`build_batch_diverse.py`, `build_roof_tick.py`, `build_maint_sedum.py` (skip any that no
longer run — say which and why in the report; do not resurrect dead builders).

1. **D3 caption guard — `guards.caption(photo) -> Caption`**. A `Caption` renders ONLY if its
   text comes from a ground-truth source: `knowledge_notes.jsonl` (Lee voice), GRA fields
   (`last_actions_at_visit` / `last_condition_notes` / `last_recommendations` via
   `grind/gra_stories.json`), or Lee's ground-truth JSONs (spine-capture format). Model text
   (qwen descriptions) may render only in a visually distinct block labelled `model` — never
   in the caption slot. There must be NO code path where free/LLM text reaches a caption slot:
   the Caption constructor takes a `source` enum and raises on anything else; builders must
   not build caption HTML by hand (grep-able: caption markup only emitted by guards.py).
   Empty is a valid caption — absence of Lee's words renders as no caption, not a model fill.
2. **D4 species reference-image guard — `guards.species_ref(name) -> RefImage`**. Every plant
   /species name rendered on a sheet gets a reference image beside it, structurally: the
   template helper that renders a species name REQUIRES a RefImage argument. Exemplar map at
   `grind/species_exemplars.json` (name → local image path). Seed it from what exists on
   Mini A: the 6 invasive watch-list flash cards (canon invasive vocab) + any Lee-confirmed
   photos in `knowledge_notes.jsonl` whose note names the species. If no exemplar exists:
   render a loud `NO REFERENCE IMAGE` placeholder AND append the name to
   `grind/species_needing_exemplar.json` (feeds Lee's queue). NEVER fetch images from the
   web; local corpus + flash cards only. Species names, not free strings: unknown name →
   placeholder path, never silent.
3. **D2 counts footer — `guards.counts_footer()`**. Calls `counts.py --json` AT RENDER TIME,
   renders the numbers + `Counted by:` + timestamp. Baked/hardcoded numbers in builder
   templates are removed. If counts.py fails, the footer says so — it never falls back to a
   cached number. (Item A pins the interface; code against `counts.py --json` even if Item A
   is still in flight.)
4. **Breach tests** (in `~/image-plane/tests_guards.py`, runnable standalone on Mini A):
   free-text caption attempt → raises; species name without RefImage → template helper
   refuses; footer with counts.py absent → renders failure text, not a number. Plus one
   rebuild of an existing real sheet (pick the smallest, e.g. closeup retest) proving output
   still renders with guards in.

## Out of scope / do-not-touch
- No GRA/portal code, no Vercel, nothing customer-facing (that's F3).
- No new tag vocab, no LLM calls, no photo processing.
- Don't modify `classified.jsonl`, `knowledge_notes.jsonl`, `allocation_v2.jsonl`,
  `photo_ledger_merged.jsonl` — read-only inputs. Back up any builder before editing
  (`.pre_guards_20260710` suffix, existing pattern).
- Vocab v2 words are steering only; this spec doesn't touch vocab.

## Done means
- Item A: counts.py output matches the 10 Jul join (or explains the drift); flags file row
  counts = 269/82/185 (or explains); --check passes; overlap number produced with its key.
- Item B: all in-scope live builders import guards; tests_guards.py passes; one real sheet
  rebuilt and rendering on the hub; species_needing_exemplar.json exists (even if empty).
- Receipts: commit hash + `Counted by:` lines for every number quoted (receipt gate enforces).
- Skill file `~/.claude/skills/green-roof-image-plane/SKILL.md` gains a short "Guards
  (F1, 10 Jul)" note naming guards.py / counts.py as mandatory for any new builder —
  done by the orchestrating window after verification, not by the agents.
