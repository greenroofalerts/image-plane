# DELTA CHECK — IMAGE PLANE (LEE-411) — 2026-07-10

Read-only audit: what Lee asked for vs what actually exists, with a fix plan.
Method: every session record on this machine was scanned (129 files, 1.7GB); the 115 that
touch the image plane were read completely by extraction agents pulling only Lee's typed and
dictated words. Project docs, spine-capture ground-truth files, and Linear (team LEE) were
swept the same way. 646 verbatim items were found and grouped into 65 canonical asks.
Every status below was checked against the artefact itself (file on disk, row count, live
URL, SQL row, or page text) — session reports claiming "done" were given no weight.

Sources of evidence cited below:
- Mini A sweep 2026-07-10 08:13 (read-only ssh; full table in
  `~/leeos-private/spine-capture/2026-07-10/delta-image-plane/evidence-minia.txt`)
- Laptop checks (this repo, ~/glenross, ~/green-roof-portal), run 2026-07-10
- LeeOSplus SQL (visual_observations count, nightly audit rows), run 2026-07-10
- Linear LEE-411 / 624 / 627 / 633 / 658 / 659 / 559 / 567
- Supporting data (all 646 quotes + the 65 clusters):
  `~/leeos-private/spine-capture/2026-07-10/delta-image-plane/asks_all.jsonl` + `clusters.json`

---

## PART 1 — WHAT LEE ASKED FOR (his words, dated, cited)

Session IDs are the first 8 chars of files in `~/.claude/projects/-Users-Lee/`.
Full quote corpus with every member item: `asks_all.jsonl` (646 items: 270 asks, 187 rules,
171 corrections, 18 rejections). The canonical asks, each with a representative verbatim quote:

### The product

- **A35 Core vision** (10 Jun–2 Jul): "how are ytou rpopsing from this point on we get to the
  poiint that the programme is able to know wh`t i would say is in every photo and every future
  opne?" — 30 Jun, `4398a734`.
- **A22 Per-roof record page** (8 Jun–9 Jul, 27 mentions — the biggest product ask): photos +
  Lee's spoken comments become the maintenance record and the client surface. "can this line be
  centred with events alterntating either side of the line… 'summer care visit (Hay Cut)'" —
  3 Jul, `74b7c7f5`.
- **A28 Replace the GRA spineline** (3 Jul): "i think this should repalce the current spineline
  in the GRA, do you have visibilit on how to do that?" — 3 Jul, `38b7de72`. (= LEE-633)
- **A36 End-uses list** (30 Jun): tag search, subcontractor project packs, GRA first-tier photo
  triage, before/after, next-visit recommendations "and how urgent, and with what caveats" —
  30 Jun, `4398a734`.
- **A38 Plant knowledge cards** (1 Jul–9 Jul): "every time we idea of plant we should have…
  what conditions it grows in… flowering period… because they're British wildflowers" +
  folklore/etymology — 9 Jul, `4ae79425`.
- **A43 Constellation surface** (9 Jul): "something like a movable navigable constellation of
  images. It's not just a list" — 9 Jul, `4ae79425`.
- **A42 Marketing engine** (9 Jul): "tell me how you can make automated marketing campaigns
  using AI curated videos… don't lose this as a job to be done" — 9 Jul, `4ae79425`. (= LEE-658)
- **A40 Flash-card decks** (9 Jul): 7 install cards requested, then "hold off on this, pin it
  we'll come nback to it" — 9 Jul, `4ae79425`. (= LEE-659)
- **A41 Installer project packs** (9 Jul): "has images pulled for installer to show what each
  termination sohould look like" — 9 Jul, `8c7a3d75`.
- **A39 Estimating app cross-link** (8 Jul): "it would need to draw upon images of what right
  looks like from image [plane" — 8 Jul, `84b978df`.
- **A25 Client PDF export gap** (29 Jun–2 Jul): "is it possible to make those pages downloable
  as pdf…?" — 29 Jun, `4398a734`.
- **A26 Weather layer** (29 Jun–9 Jul): "use the weather monitoiring by location… to help make
  more meaningful explanations of why a roof looks like it did" — 1 Jul, `ae5ee9a2`.

### The pipeline

- **A5 Exhaustive allocation** (24 Jun–5 Jul): every photo to job+date, using the method
  already proven in Glengarry/Glenross: "its inexplicable to me that you could actually do this
  work and not ha[ve used it]" — 1 Jul, `ae5ee9a2`.
- **A7 Xero-anchored matching** (30 Jun–2 Jul): "i need an intel that forms grouping of pics
  around billable events" — 1 Jul, `ae5ee9a2`.
- **A8 Reassignment mechanism** (1 Jul): "lets add a subtask to linear to make reassignment
  options in the way thet we can weith glenross" — 1 Jul, `ae5ee9a2`. (= LEE-624)
- **A1 Dedup policy** (10 Jun–3 Jul): exact dupes go, near-dupes quarantined until the detector
  is proven; later: collapse takeout re-encodes corpus-wide.
- **A2 HEIC→JPEG derivatives** (10 Jun, 24 Jun): "convert them all from heic and reduce file
  size for future manageability" — 24 Jun, `4398a734`.
- **A4 Takeout as source** (12 Jun–30 Jun); **A37 email mining next** (1 Jul): "all grteen roof
  emails are available in lee@or" — 1 Jul, `ae5ee9a2`.
- **A33 Reports as a source** (29 Jun): "ingest all of the reports I've ever done and then use
  those as a way of seeing… what is in a lot of these pictures" — 29 Jun, `4398a734`.
- **A34 Extraction repair** (8 Jul): "get every stat here to 90% before you come to me again
  pls" — 8 Jul, `ceddcce0`.
- **A31/A32 Plant-ID model** (29 Jun–9 Jul): "WAVES OF PASSES OF IDENTIFICATION" — 29 Jun;
  "get the plant model we're a plant business" — 1 Jul, `ae5ee9a2`; pay for a quality outside
  model rather than rely on qwen — 8 Jul, `6b28446d`.
- **A30 GLM contest** (8 Jul): try GLM 5.2 on non-sensitive photos before paying.
- **A3/A56 Repo scaffold + synthetic-only** (10 Jun): real photo bytes never go to the cloud or
  the repo; dev/test on synthetic images only.

### The review loops

- **A18/A19 Sheet loops** (29 Jun–9 Jul, 196 member items): Lee describes a batch, agents fan
  out, he answers by number. His dictated verdicts across ~10 sheets are the ground truth corpus.
- **A15 Spread from one verdict** (30 Jun–1 Jul): "fan out subagents… isolate images with
  identifiable plants… make that slow and maximally accurate" — 1 Jul, `ae5ee9a2`.
- **A20 Widening loop** (30 Jun–9 Jul): trust the model progressively; measure agreement before
  widening.
- **A14 Not all 22k need his eye** (24 Jun–30 Jun): stop signal = bundles coming through with
  almost no changes.
- **A21 Tick-pass** (1 Jul): superseded same week by picture-commentary on known-type sites —
  closed by Lee himself.
- **A16 Dictation must not be lost** (29 Jun): "where did the dictated text go?" — 29 Jun.

### Vocabulary and taxonomy

- **A10 Visit types** (1 Jul–8 Jul): evolved 7 types → v4 canon (Prestart · Spring RoofCare ·
  Supervised Self Install · Shingle pregrown vs plug/seed · RoofCare HayBase · Diagnostic
  vegetation/leaks; no revival type; bulbs never a visit type).
- **A11 Condition vocabulary** (2 Jul): v1 withdrawn by Lee — "let's start again with… what are
  the ways in which we likely to want to search this?"; condition is written about in prose, not
  tags; his 5 problem terms are canonical.
- **A12 Component vocabulary** (2 Jul): mine HIS collateral (HayBase, Honesty Box, handover
  sheets) for the build-up/furniture words.
- **A13 Invasives canon** (8–9 Jul): "rye grass canadian fleabane willow couch grass creeping
  thistle bramble buddleia dock sycamore fat hen that the list of invasives to always remove".

### Standing rules (each voiced as a rule, most more than once)

- **A17** Never invent captions/comments; his words verbatim only ("stop fucking hallucinating" —
  2 Jul, `3038fb4d`).
- **A56** Real photos/captions/EXIF never leave local machines (Lee-approved exceptions only).
- **A57** Personal/out-of-scope photos removed from the corpus.
- **A58** GRA is a window, not the authority; the job universe is Drive + Xero.
- **A59** Don't reinvent what Glengarry/Glenross solved.
- **A60** Rich dictation is the record; tags are only the index.
- **A61/A64** Image Plane = the image element of the memory spine; ONE memory per ROOF, photos
  as peers alongside money/words/weather/species.
- **A62** Names not codes on anything Lee reads; sub-refs where GRA has them; zero-pad rules.
- **A63** Live counts only, with citations.
- **A65** (NEW, 8–9 Jul, said ~10×): every plant-name claim carries a picture next to it —
  "let's get something next to [the name]" — and individual sedum species ID'd, always with
  confidence.

### Ops asks

- **A44** Park/capture-only status — overtaken by Lee doing the work anyway; epic moved
  In Progress 3 Jul.
- **A46/A47/A51** Local working location; scale across the minis; sequence other jobs around
  the grind; caffeinate.
- **A55** "harness sonnet sub agents and check their work to reduce token spend ok?" — 2 Jul.
- **A23** GRA roof-care history backfill for all sites (8 Jun, pre-dates the corpus work).
- **A24** Report-photo handling contract for GRA PDF reports (12 Jun).
- **A27** The Fawe Park / New North Rd PDF report loop (30 Jun–2 Jul).
- **A29** Flyover hero images on GRA site entries (3 Jul — GRA-side, tracked there).
- **A52/A54** Recurring meta-asks: evaluate methodology against the vision canon; how far from
  full voice-dictation-to-record automation.

### UNCONFIRMED — claims of what Lee wanted that exist only in assistant writing

These 37 items (20 groups) came only from assistant-authored docs (END-USES canon, MOVE-1 spec,
DELIVERY-MAP, README, handovers) with no Lee quote found in any session record. Confirm or bin:

1. The specific 22-end-use enumeration and its grouping (END-USES doc) — Lee voiced ~8 of the
   uses directly (A36); the rest of the list is synthesis.
2. The four-foundations build order as a Lee ruling (doc frames it as agreed; no quote found).
3. "Installer vetting test" as an end-use (doc only).
4. "Sell the compliance tool" / diagnosis API as Lee asks (doc only).
5. MOVE-1 photo-index spec details (shard sizes, index fields) as Lee requirements.
6. "Free legal/record-bundle win first" as Lee's chosen first move (doc only).
7. The delivery-map phase gates and percentages (doc only).
8. Scaffold README architecture choices (SQLite store etc.) as Lee decisions — Lee approved
   direction 10 Jun but the specifics are the assistant's.
9. Remaining 12 groups: minor doc-only attributions listed in `clusters.json → unconfirmed`.

None of these contradict a confirmed ask; they are unproven attributions, not errors found.

---

## PART 2 — WHAT EXISTS (checked against the artefact, today)

Corpus baseline (disk-verified 8–10 Jul): ledger 16,426 · keeps 12,338 · drops 3,203 ·
quarantine 885 · allocated 7,099 (58% of keeps) · knowledge_notes 235 rows
(sha256 87ee47a6…f14d480, matching the 8 Jul record — nothing lost since).

**BUILT AND PROVEN** (artefact + real run/click/row seen):

| Ask | Proof |
|---|---|
| A4 ingest from Takeout+iCloud | ledgers on Mini A: classified.jsonl 16,426 rows; takeout_ledger 5,054 rows |
| A33 reports ingested | `~/image-plane/reports_corpus.jsonl` (89 reports); register grew 91→129 geocoded jobs |
| A57 scope exclusions | drop 3,203 + quarantine 885 in ledger; 1848-26 personal bundle excluded 3 Jul |
| A1 dedupe | dedupe_report_20260703.json: 239 takeout re-encodes collapsed, no deletes, backups kept |
| A2 JPEG derivatives | jpeg_derivative_pass_report.json: 11,926/11,926 ok, 0 fail, 9 Jul |
| A7 Xero-anchored matching | roof_invoice_match.jsonl 665 dated events; full-lines pull 2,868 lines (the tracking-only bug Lee caught was fixed at data layer 3 Jul); "400 unbilled" collapsed to 78 |
| A9 identity corrections | Trinity = 1124-19 fix (83 photos), Cosbycote→Lambeth (37), OM house map applied; apply-specs + re-verified reruns on Mini A docs/ |
| A10 visit types v4 | visit_types_v4.jsonl 721 events / 227 named, zero label-without-evidence (re-counted); canon doc in spine-capture 07-08 |
| A13 invasives | invasive_findings.jsonl + 11-card watch-list canon; invasive-first encoded in specs |
| A16/A19 dictation captured + sheets applied | knowledge_notes 235 rows sha-verified; invoice-gap 20/20, visit-sheet 23/23, guess-sheet 20/20, sweep-asks 1–56 + 57–77 captured; durable copies in spine-capture |
| A18 review hub | http://192.168.178.61:8787/verdicts.html → HTTP 200 today (also tailnet URL 200); LaunchDaemon active, survives reboot |
| A34 extraction repair | final_scorecard.json 8 Jul: attributed 91%, extracted 100%, searchable 91%, vision-confirmed 96.4% of visual-expected |
| A30 GLM contest | plantid_contest_full.json; GLM failed (3/100 agreement, 0/6 on eye-adjudications) — ruled out |
| A32 model tier decided | claude_vision_results.jsonl 9 Jul; Claude-vision beats qwen; hybrid architecture ruled with Lee paying API |
| A22 record page (format) | trinity-crescent-1124-19.html rebuilt 9 Jul 01:10 with `.pre_v3punch_20260709` backup — v3 punch VERIFIED IN PAGE TEXT today: "Project Surgery" present, "consultancy fee" gone, "Where things stand today… As of the last visit — late-summer inspection, 26 Aug–9 Sep 2025" |
| A26 weather (Trinity) | trinity_weather_facts.json; weather claims re-derived by independent SQL 3 Jul; superlatives now judicious (5 mentions on page) |
| A47/A51 machine scaling | 3-machine dist grind ran; boot_grind @reboot in crontab; caffeinate rule in skill |
| LEE-627 nightly self-audit | SQL today: 10 nightly_audit rows, latest 2026-07-10 05:40 — running unattended 8 nights past the 2-night proof bar |
| A55 cheap-model execution | operating rule held through 2–9 Jul runs (sonnet/haiku executed, Fable verified) — and this delta check ran the same way |
| A3/A56 scaffold + synthetic-only | this repo: tests, benchmark, LEE-559 merged (cb7dd8b); no real photo bytes in repo |

**BUILT BUT UNPROVEN** (code exists, never seen working live):

| Ask | State |
|---|---|
| A34 ingest-time tagging | `ingest_lib.py` + test built 9 Jul per INGEST-WIRE-SPEC — but nothing in the live capture path calls it yet; every new dictation still needs a manual rebuild |
| A15 spread beyond 2 buckets | vocab_v2 spread ran only on sedum-maintenance + install buckets; machinery exists, corpus-wide spread never run |
| sibling_verify | spec + output (sibling_checks.jsonl) exist on Mini A; the script itself is missing — result unreproducible as-is |

**PARTLY BUILT**:

| Ask | Built | Missing |
|---|---|---|
| A5 exhaustive allocation | 7,099 of 12,338 keeps allocated (58%) | ~5,200 keeps homeless; 163 undated residue; 411 "keep" rows point at paths missing on disk (kept_missing_on_disk.json — awaiting Lee look) |
| A22 record pages (rollout) | Trinity page proven; 153 job pages exist but in the OLD site-view format, not the record-page format | per-roof record pages for every roof; "earned handover product" |
| A62 names-not-codes | site_names.json seeded (7 names) + rule canon | coverage across all 153 job pages/sheets; join file is thin |
| A36 end-uses delivered | search layer 91% + record page + plant loop exist | most end-uses (triage in GRA, project packs, before/after surfaces) have no surface yet |
| A40 flash cards | invasive deck done; install card 1 drafted (artifact) | 6 remaining install cards + diagnostic deck — paused by Lee ("pin it") |
| A23 GRA history backfill | site_events import ran 3 Jul (33 sites, portal_ready flipped off pending Lee) | full-history backfill across all sites; GRA admin defects queued |
| A24/A27 PDF reports | Fawe Park + New North Rd shipped through the full loop | automation (LEE-565 backlog); each report is still a hand-driven session |

**NOT BUILT**:

| Ask | Evidence of absence |
|---|---|
| A28 GRA spineline replacement (LEE-633) | `green-roof-portal/src/components/RoofCareHistoryTimeline.js` untouched since 2 Jun; zero image-plane references in portal src; issue Backlog |
| A8 reassignment mechanism (LEE-624) | no artefact; edge cases were handled by one-off sheet loops instead; issue Backlog |
| A38 plant knowledge-card library | no card artefacts anywhere on Mini A/laptop; Vision Canon ruled PROPOSE-first 9 Jul — proposal not yet written |
| A43 constellation surface | idea captured only; Fable owes a tool recommendation |
| A42 marketing engine (LEE-658) | idea captured in Linear; Fable owes the how-to proposal |
| A41 installer project packs | no generator, no pack artefacts (LEE-484 also Backlog) |
| A39 estimating cross-link | estimating room is designing (other project); no image-plane hookup |
| A37 email mining | zero gmail-derived artefacts in grind/ — named "the missing source" by Lee 3 Jul, still untouched |
| A25 client PDF export of record pages | no export path exists for the HTML record pages |
| A65 reference-image-per-claim sheets | rule given 8–9 Jul; NO ID sheet has been produced since — nothing newer than closeup-retest (9 Jul 01:33) and plantid-approval exists without exemplar images |
| A61/A64 spine integration | SQL today: `visual_observations` = **0 rows**; no entity join; the whole pipeline lives in local files — Lee blessed the spike (his 29 Jun Linear comment) but the reconciliation he flagged has never been scheduled |
| Camera→pipeline ingest (LEE-567) | Backlog, no artefact — new photos taken today have no route into the corpus |

**Open items that are Lee's, not build gaps**: sweep-asks 57 (996-19 portfolio-or-billable),
60 (Spencer Park billing), 69 (De Beauvoir vs Lambeth photo); micro-moment default ratify;
summer-care visit-type name (Ryedale Aug); Xero re-tag execution (14 invoices, list ready);
411 missing-on-disk keeps; GRA 33-site portal visibility.

---

## PART 3 — THE DELTA AND THE PLAN

### Delta summary

Of 65 canonical asks: **24 built-and-proven · 3 built-unproven · 7 partly built · 12 not
built · 19 rules/process/meta (mostly held, three flagged below)**. The pipeline and review
loops are real and proven. What's missing is almost entirely the OUTPUT layer — the things
Lee actually asked the corpus FOR: record pages on every roof, the GRA swap, search he can
touch, plant cards, packs, marketing. The engine is built; the product mostly isn't.

### Rule-disobedience (rule already written, not held) — fix first, cheapest

| # | Rule | Breach | Fix |
|---|---|---|---|
| D1 | A61/A64 image plane = spine element, one memory per roof | visual_observations 0 rows; corpus is a parallel local architecture; reconcile flagged 29 Jun, never scheduled | Lee decision + one publish job (see F5) |
| D2 | A63/A6 live counts, honest totals | "largely done" claimed at 57% allocated (Lee caught it 8 Jul) | enforcement by construction: every report of corpus numbers must embed the re-query line; add to skill + sheet templates (F1) |
| D3 | A17 verbatim only, never invent | hallucinated captions happened (1301-21, Fawe Park); rules now written but nothing enforces them | template guard: caption fields in sheet/page builders may only render from knowledge_notes/GRA fields, never free text (F1) |
| D4 | A65 picture-next-to-every-plant-name | rule said ~10× on 8–9 Jul; no compliant sheet exists yet (not yet violated — armed) | make the exemplar-image slot structural in the sheet builder before the next ID sheet ships (F1) |

### Fix plan, ordered by what unblocks the most

**F1 — Disobedience batch: encode the three guards (D2, D3, D4).**
Involves: sheet/page builder templates on Mini A get (a) mandatory re-queried count lines,
(b) captions render only from ground-truth fields, (c) a reference-image slot per species name;
skill updated. Depends on: nothing. Cost: ~100k tokens, no Lee time.
Seen by: next sheet on the hub carries exemplar pictures and a counts footer.

**F2 — Finish allocation (A5).** The single biggest unblock — record pages, search, packs all
sit on it. Involves: machine passes for the ~5,200 homeless keeps (GPS-neighbour, album joins,
filename-order pass for the 163 undated), then carousel sheets for the residue; resolve the 411
missing-on-disk rows. Depends on: F1 (sheets carry the new guards). Cost: grind is free (local
qwen); orchestration ~500k–1M tokens; Lee answers residue sheets at his pace.
Seen by: hub index shows "X of 12,338 allocated" climbing to ~100% with the honest counter.

**F3 — Record pages for every roof (A22), then the GRA swap (A28/LEE-633).**
Involves: per-roof record JSON published from the pipeline; Trinity template applied to the
~150 roofs; then the portal component swap in green-roof-portal (own window, client-facing,
Vercel deploy, no amounts client-side, routing-proof rule applies — the link a customer opens
must render the new page). Depends on: F2 for completeness (can start on allocated roofs now).
Cost: ~500k–1M tokens + one deploy window. Seen by: any roof on the hub in Trinity format;
then the same on the live GRA site behind a customer link.

**F4 — Make the search layer touchable + wire ingest (A34/A36).**
Involves: a search page on the hub over tag_index.json (91% searchable already, zero UI);
call ingest_lib.tag_new_notes() from the capture scripts so new dictation tags itself.
Depends on: nothing. Cost: ~150k tokens.
Seen by: type "skylight" on the hub, get the photos.

**F5 — Spine reconciliation decision (D1) — Lee gate.**
The one open architecture breach. Options: publish per-roof/per-photo index rows into the spine
(counts + refs, raw addresses stay local), or formally re-rule that the corpus is Mini-A-local
with the spine holding pointers. One page of options, Lee picks, one publish job follows.
Cost: proposal ~50k; publish ~100k. Seen by: visual_observations (or ruled equivalent) non-zero,
queryable from spine tools.

**F6 — Vision-canon proposals Fable owes (A38, A42, A43).**
PROPOSE-first per the 9 Jul canon: knowledge-card pilot (10 cards incl. folklore/etymology),
constellation tool recommendation, LEE-658 marketing-engine proposal. Depends on: nothing.
Cost: ~300–500k. Seen by: three one-page proposals on the hub for Lee's verdict.

**F7 — Email mining (A37).** The named missing source for record-page prose. Depends on: F3
format so mined text has somewhere to land. Cost: ~500k + Gmail scopes already held.
Seen by: a roof's record page quoting what was said at the time, sourced from email.

**F8 — Lee's own queue** (no build): items 57/60/69, micro-moment ratify, summer-care name,
Xero re-tags, 411 missing-on-disk look, GRA 33-site visibility. All sit on the hub already.

Deliberately NOT in the plan until Lee says so: LEE-624 reassignment mechanism (sheet loops
are covering it), flash-card decks (Lee pinned), LEE-567 camera ingest (worth raising after F3).

---

## RECEIPT

- **Records read**: 129 session files in `~/.claude/projects/-Users-Lee/` scanned; 115
  keyword-matched sessions read completely (1,658 Lee messages); 14 non-matching sessions not
  read beyond keyword scan; 0 unreadable files. 23 project/spine-capture docs + this repo +
  Mini A docs listing + 8 Linear issues read.
- **Asks found**: 646 verbatim items → 65 canonical asks (+ 20 unconfirmed groups, 37 items).
- **Unconfirmed for Lee**: the 9 doc-only attribution groups in Part 1 — confirm or bin.
- **Statuses**: 24 proven · 3 built-unproven · 7 partly · 12 not built · 19 rules/meta.
  4 disobedience flags (D1–D4), all cheaper than construction.
- **Cost**: ~3.6M tokens this run (~3.4M on sonnet extraction/clustering/evidence agents,
  remainder Fable orchestration + verification).
- **Commit**: `95c6367fb71fc13fcb0512c9a2730909033eb713` (this doc; hash stamped in a follow-up commit).
- **STOP**: per the brief, nothing in Part 3 runs until Lee reads this and says go.

*Fable this run: scoping, briefs, artefact verification (Mini A/spine/portal/Trinity page),
delta authoring; extraction, clustering and the evidence sweep ran on sonnet.*
