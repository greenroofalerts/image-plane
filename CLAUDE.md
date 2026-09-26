# CLAUDE.md — image-plane (LEE-411)

## ⛔ READ FIRST — this is mostly ALREADY SOLVED. Do not reinvent. (anti-amnesia)
Before geocoding, allocating, matching, or "thinking creatively" about job→site resolution,
**read the established work** — Lee has had to repeat this and is rightly fed up with re-derivation:
- **Job→site allocation source order (PROVEN):** `~/glenross/docs/product-control/GLENROSS-ALLOCATION-SOURCE-AUDIT-2026-06-23.md`. GRA `sites` are **already geocoded** (lookup, don't re-geocode); the **job universe = Xero job tracking vocabulary (527/458 NNNN-NN), NOT customer contacts** (customer/billing address ≠ site address).
- **Site-vs-billing solved:** `~/glenross/docs/product-control/GLENROSS-SITE-FACT-HARVESTER-V3-2026-06-23.md` — site = doc TOP recipient block; billing/footer/registered-office VETOED.
- **GRA = address-reference-only CONSUMER**, not authority/source; the spine (`LeeOSplus.observations`) is the knowledge store; image plane (`visual_observations`) lives in the spine. **Always re-query GRA live counts before quoting (`status=active` ≠ live; ~20 live, not 71).**
- **Boundary:** allocation runs LOCALLY (Mini A / `~/.glenross/`), raw site rows never enter cloud context — counts only.
- **Sources:** iCloud export (GPS+desc) + Google Takeout albums (album name = job_ref+site+season, strong) + Drive (canonical folders) + reports.
- **Memories:** `project_image_plane_allocation_established`, `image-plane-gra-format-vision`, `reference-gra-sites-readable-mcp`, `live-counts-cite`. **The labelling carousel + capture already exist** (`~/leeos-private/image-plane-captures/`).
- **Rule:** consult before constructing; the wheel exists — attach photos to it, don't rebuild it.

A **fully local** photo-parsing pipeline. Walks a folder of photo exports (Google Takeout /
iCloud / plain), normalises metadata into SQLite, finds exact + near duplicates, and
captions/tags each image with a **local** Ollama vision model. **No cloud calls anywhere** —
photo bytes never leave this machine. That is the project's defining constraint.

## Stack / layout
- Python package: `src/image_plane/` — `ingest.py`, `dedup.py`, `phash.py`, `caption.py`,
  `ollama_client.py`, `cli.py`, `db.py`. Tests in `tests/` (21 pass). `pyproject.toml`.
- Store: SQLite `image_plane.db` — `photos(...)`, `duplicates(...)`.
- Vision model: local Ollama `qwen2.5vl:3b` on `127.0.0.1` only (~7 s/image; disk-constrained box).
- Docs: `docs/BENCHMARK.md`, `docs/QUESTIONS-FOR-LEE.md` (decisions + agreed next steps).

## Agreed next steps (from QUESTIONS-FOR-LEE)
1. On real export landing: free-space check, then HEIC spot-test on real files.
2. Build `image-plane dedup --delete-exact` (byte-identical only; near-dupes/bursts NEVER hard-deleted).
3. Domain tagging + GRA site-matching module — **design + sign-off before building.**

## ⚠️ If this session is running on GLM / any cloud model (the `glm` toggle)
This project is local-by-design because the photos are private. When the engine is GLM (cloud,
servers in China):
- **OK:** writing/debugging code, architecture, tests, the CLI — that's source code, not photos.
- **NEVER:** feed real photo bytes, real captions/metadata, or `image_plane.db` contents to the
  model; never route captioning through the cloud. The pipeline's OWN local vision model handles
  photos. GLM helps *build the tool*; the tool *runs locally* on the photos. Keep them separate.

## Working rules
- It's a git repo (branch `main`): branch before changes; don't commit `image_plane.db`, real
  photos, or anything under a photo export path.
- Loop Proof Gate applies (skill `loop-proof-gate`): don't call work "done" without the proof
  ladder — especially "tests pass" ≠ "ran correctly on real files."
