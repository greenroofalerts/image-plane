# IMAGE PLANE — PRODUCT CONTRACT (2026-09-25)

One repo-local acceptance document for the Image Plane. It holds the accepted
invariants, the executable test that proves each one, and the honest state of
each condition. Code, database and live behaviour are operational truth; this
contract points at them and never replaces them.

Canon sources this contract rests on:

- `~/image-plane/IMAGE-PLANE-END-USES-2026-06-30.md` (22 end-uses, 4 foundations)
- `~/.claude/skills/green-roof-image-plane/SKILL.md` (ladder laws, photo-date rule)
- `~/.claude/skills/id-ladder/SKILL.md` (eight lanes, riding laws)
- Mini A `~/image-plane/docs/LADDER-RESIDUE-SPEC-2026-07-28.md` (recorded matcher only)
- Mini A `~/image-plane/docs/IMAGE-PLANE-MCP-2026-09-10.md` (MCP surface)
- Memory spine: `project_image_plane_end_uses`, `project_image_plane_lee411`,
  `project_image_plane_daily_worker_aug24`, `project_image_plane_residue_exhausted_jul30`

Live surfaces named below all live on Mini A unless a path says otherwise.
The corpus is the retained collection
`/Users/macminia/image-plane/incoming/worker/collection/results.json`
(10,272 photo records, counted 2026-09-25 by the sweep in this session).

## The twelve conditions

### C1 — Image Plane never oversteps its boundary

Image Plane never mints job numbers, never sends customer communications,
never publishes PDFs, never hangs GRA records, and never silently changes
another product. Writes to the spine are observations only (append).
Test: pattern sweep over the live worker runtime, the MCP server and the
job screen for outbound-send and foreign-write machinery.

### C2 — The Identity Ladder is the method

Every photo-to-job identification comes from the recorded ladder lanes
(at least two lanes joined by `+`), a Lee answer, or a citation of the
guarded spine table `LeeOSplus.public.visual_observations` with a
record_id and a banded confidence. Never a single field, never an
invented matcher. `allocate_takeout_v4.py` is the only recorded matcher;
v5 is dead.
Test: every record in results.json with a job_ref must carry evidence in
one of the accepted shapes.

### C3 — An album title with a valid job code is strong evidence

PERMANENT REGRESSION TEST, Lee's own words: given a Google Photos album
whose title contains a valid job code (such as 1892-26), imported
photographs must resolve to that job unless stronger canonical evidence
explicitly contradicts it. The evidence used must remain inspectable.
A withheld assignment is acceptable ONLY where the record shows the
contradiction: state `contradicted`, the album ref among the candidates,
and preserved evidence for both sides. Ambiguity goes to Lee and is never
auto-picked.
Test: sweep of all album memberships in results.json.

### C4 — Source evidence is preserved

Every job allocation keeps its source evidence and confidence. Lee's own
voice rulings (knowledge_notes.jsonl, source_kind `lee_voice`) are the
strongest evidence and count as `lee_answer`.
Test: no record with a job_ref may carry an empty evidence object.

### C5 — Real photos are attributable and queryable

Photos carry a job/site and can be queried back by job ref, and the files
exist on disk.
Test: per-job counts computed from the corpus; a sample of photo files
opened on disk.

### C6 — Billable-event classification is stored and queryable

Every event carries a chargeability state.
Test: count of event records lacking a chargeability value.

### C7 — Component classification is stored and queryable

Keyword/component labels (Lee's words and machine proposals) are stored
with counts by component.
Test: distinct terms and per-term counts computed from the corpus.

### C8 — The two lanes stay distinct

Retrospective filing (historical_enrichment) and read-only daily Google
Photos discovery/ingest (daily_freshness) are separate lanes and never
contaminate each other.
Test: status.json lane inventory.

### C9 — HEIC conversion and ingest routes keep working

Every record serves a JPEG display format; the daily worker still runs.
Test: display_format sweep plus the worker run log timestamp.

### C10 — Lee can search a job and see its photographs

The job screen on :8789 answers a job ref with a rendered page that shows
photos; unknown refs answer 404.
Test: live HTTP fetch of /job/1892-26, /attention, and a bad ref.

### C11 — MCP exposes the capability to other mesh products

The FastMCP stdio server at
`incoming/worker/runtime/mcp-20260910/server.py` lists the reading tools
and answers a tools/list call.
Test: live stdio handshake against the server.

### C12 — Unattended operation survives restart

The daily worker, the job screen and the site view are launchd services
that come back after a restart.
Test: launchctl list plus plist RunAtLoad/KeepAlive checks.

## Execution

The harness is `tests/acceptance/test_product_contract.py`. It runs ON
Mini A against the real corpus, the real HTTP surfaces and the real
service registry — never against synthetic data alone. Deploy it with scp
and run it there. Each condition prints PASS, FAIL or BLOCKED with the
exact reason and the counts behind it. Exit code 1 on any FAIL.

Fix law: one failing condition at a time. Fix it, rerun, commit, receipt,
then move to the next. Completion is every condition passing against the
real system — never a claim built on ingestion volume.

## Honest state at writing (2026-09-25, this session's sweep)

- C1 not yet probed. C2 and C4 pass once Lee's voice rulings in
  list-shaped evidence are read correctly (first read of 4,179 rows as
  "bad" was wrong: those cite the guarded spine table with record_id).
- C3: 142 album-ref photos sit withheld as `contradicted` with both
  sides' evidence preserved — correct under the riding law, but the
  conflict is never surfaced to Lee as a decision. 4 contradicted rows
  carry no method evidence at all.
- C5-C9 measured healthy at data level. C10 partially walked (1892-26
  renders). C11, C12 probed by existence, not by live call.
