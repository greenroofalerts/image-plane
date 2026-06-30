# CLAUDE.md — image-plane (LEE-411)

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
