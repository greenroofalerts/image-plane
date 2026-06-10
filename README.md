# image-plane (LEE-411)

A **fully local** photo-parsing pipeline. Walks a folder of photo exports,
normalises metadata into SQLite, finds exact and near duplicates, and
captions/tags every image with a local vision model via Ollama.
**No cloud calls anywhere** — the only network traffic this project ever
makes is downloading the Ollama runtime and model weights; photo bytes
never leave the machine.

## Findings first

- **Ingest, dedup and caption all work end-to-end on synthetic images.**
  21 tests pass; the CLI ran the full loop (generate → ingest 17 → dedup →
  caption benchmark) on this machine.
- **All development used programmatically generated images only.** No real
  photograph was opened at any point. The fixture generator
  (`scripts/generate_test_images.py`) builds deterministic gradient/shape
  scenes plus duplicate variants.
- **Disk is the binding constraint on this MacBook** (~12 GB free at build
  time). That drove the model choice: `qwen2.5vl:3b` (~3.2 GB) over the 7B
  (~6 GB). A full photo library ingest also needs scratch space — check
  free disk before pointing this at a Takeout archive.
- **Captioning speed** — see `docs/BENCHMARK.md` for the measured
  seconds-per-image on this machine and the full-library runtime estimate.

## Architecture

```
folder of images (+ Takeout JSON sidecars)
        │
        ▼
   INGEST  ── EXIF (DateTimeOriginal/DateTime, GPS IFD)
        │     sidecar (photoTakenTime, geoData) — sidecar wins
        │     sha256 + 64-bit dHash computed at ingest
        ▼
   SQLite  image_plane.db
        │   photos(path, file_hash, phash, source, taken_at,
        │          gps_lat/lon, width, height, bytes,
        │          caption, tags, caption_model, timestamps)
        │   duplicates(photo_id, dup_of, kind, distance)
        ├──▶ DEDUP    exact = identical sha256
        │             near  = dHash hamming ≤ 8 (re-encode, resize,
        │             brightness; heavy crops intentionally NOT matched)
        └──▶ CAPTION  local Ollama vision model (127.0.0.1 only),
                      JSON caption + 3–6 tags per image
```

### Source formats

- **Google Takeout**: images plus `IMG.jpg.json` /
  `IMG.jpg.supplemental-metadata.json` sidecars. Sidecar timestamp and
  GPS override EXIF (Takeout often strips GPS from EXIF). A `0.0/0.0`
  geoData is treated as "no GPS", not the Gulf of Guinea.
- **iCloud / plain export**: no sidecars; EXIF only. HEIC supported via
  `pillow-heif`.
- Source is auto-detected (sidecars present → takeout) or forced with
  `--source`.

### Resumability

Every stage can be killed and re-run safely:

- `ingest` skips files whose path+hash are already stored; changed bytes
  under a known path re-ingest and clear the stale caption.
- `dedup` is a pure, idempotent rebuild from stored hashes (no image
  reads — fast at any scale).
- `caption` only processes rows `WHERE caption IS NULL` and commits after
  each image, so a killed run loses at most one in-flight image.

## Setup

```bash
cd ~/image-plane
python3 -m venv .venv
.venv/bin/pip install -e ".[heic,dev]"

# Ollama runtime is vendored in ./bin (standalone, no system install):
./bin/ollama serve &        # localhost only
```

## Usage

```bash
.venv/bin/image-plane ingest ~/Photos/Takeout       # or --source icloud
.venv/bin/image-plane dedup --show
.venv/bin/image-plane caption --pull                # pulls qwen2.5vl:3b if needed
.venv/bin/image-plane status
```

Default DB: `~/image-plane/image_plane.db` (override with `--db`).

## Tests

```bash
.venv/bin/python -m pytest tests/ -q
```

Fixtures are generated fresh per test session — nothing binary is
committed. 21 tests cover: Takeout sidecar mapping, EXIF datetime + GPS
DMS conversion, resume/skip/update paths, empty folders, corrupt images,
corrupt sidecars, exact dupes, near-dupe variants (resize / re-encode /
brightness), crop non-matching, false-positive checks across distinct
scenes, dedup idempotency, vision-model detection and caption-response
parsing fallbacks.

## Decisions and next steps (agreed 2026-06-10)

Full record in `docs/QUESTIONS-FOR-LEE.md`. Short version:

- Parsing happens **locally on this MacBook** (external SSD if the
  library outgrows ~41 GB free). Check free space before ingesting.
- **7 s/photo sequential is fine** — overnight chunks, no sharding.
- **Exact dupes** (byte-identical): delete command approved, to build.
- **Near-dupes/bursts**: never hard-delete — best-of-group kept, rest
  moved to a quarantine folder until the detector is proven on real
  photos.
- **Purpose**: captions feed a green-roof business evidence layer.
  Planned next module — domain tagging (plant species, substrate type,
  roof system, defect types) and GPS+date site-matching against the
  GRA sites table. Personal photo streams fork later.
- **HEIC**: supported in code; must be tested on real samples as the
  first step when the export arrives.

## Hard rules honoured

- No real photos were opened, viewed or processed during development.
- No cloud APIs: caption inference is 127.0.0.1 only; stdlib HTTP client.
- Additive: new repo, vendored Ollama binary, nothing else on the
  machine touched.
