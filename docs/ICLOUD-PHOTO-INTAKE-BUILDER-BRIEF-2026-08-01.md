# Mini B iCloud photo intake — builder brief

Board ref 248. Controller package `pkg-20260801-152355-light`.

## Goal

Export iCloud photo originals from Mini B into checked plain folders. Copy checked files to Mini A. Do not read photo meaning.

## Ownership

This build owns file intake only.

Do not edit or run `/Users/Lee/fewshot_engine.py`.
Do not run any picture reader.
Do not run any matcher.
Do not run `allocate_takeout_v5.py` or `make_v5`.
Do not delete any file or iCloud item.

The later matcher stays `/Users/macminia/image-plane/allocate_takeout_v4.py` only.

## Files to build

1. `scripts/mini_b/export_icloud_photos.py`
2. `scripts/mini_b/photo-export-photos.command`
3. `scripts/mini_a/icloud_intake_runner.sh`
4. `tests/test_icloud_intake.py`

Keep the Python logic testable without Photos or SSH.

## Mini B paths

- Photos database: `~/Pictures/Photos Library.photoslibrary/database/Photos.sqlite`
- Output root: `~/icloud-originals/photos`
- Staging: `~/icloud-originals/photos/.staging`
- Checked assets: `~/icloud-originals/photos/assets`
- Quarantine: `~/icloud-originals/photos/quarantine`
- Receipt: `~/icloud-originals/photos/manifest.jsonl`
- Run log: `~/icloud-originals/photos/export.log`
- Lock: `~/icloud-originals/photos/.lock`

## Eligibility

Select `ZASSET` rows where:

- `ZKIND=0`
- `COALESCE(ZTRASHEDSTATE,0)=0`
- `COALESCE(ZHIDDEN,0)=0`

Use `ZUUID` as the stable item ID.

Support `--one ID`, `--limit N`, and the full default.

## Export method

Reuse the proven pattern in `/Users/macminib/photo-export-videos.command`:

- run from Mini B Terminal;
- address an item as `media item id "<UUID>/L0/001"`;
- call Photos `export ... with using originals`;
- use a bounded timeout.

Export one item per staging folder. This prevents filename collisions. Apple can emit more than one file for an item. Keep all emitted files together.

The command wrapper calls Python. Python can call `osascript` for one item at a time. A failure must not stop later items.

## Checks and receipts

After export:

- require at least one file;
- require every file to have a positive byte size;
- compute SHA-256 for every file;
- record one JSON object per item;
- include item ID, state, attempt, start time, finish time, error, and member records;
- member records include relative path, role, bytes, and SHA-256;
- infer `role=photo` for supported image extensions;
- infer `role=live_photo_motion` for video extensions;
- use `role=sidecar` for other files.

Append state records. Never rewrite old receipt lines.

A checked item moves atomically from `.staging/<id>` to `assets/<safe-id>`.

On resume:

- read the latest receipt per item;
- for a checked item, recheck all asset files and hashes;
- skip only when every check still passes;
- quarantine an existing conflicting asset folder;
- re-export an incomplete item;
- never overwrite different bytes.

Use an atomic directory lock. Refuse a second run.

Do not create `COMPLETE` on Mini B. The Mini A runner owns final completion.

## Mini A runner

The runner executes on Mini A. It must:

1. Read Mini B `manifest.jsonl` through SSH.
2. Copy checked `assets/` and the manifest with resumable `rsync`.
3. Recheck copied files against the latest checked record per item.
4. Load excluded SHA values from `~/image-plane/grind/excluded_moves_20260728.jsonl`.
5. Place excluded item folders under `~/image-plane/incoming/icloud/suppressed/`.
6. Place checked non-excluded item folders under `~/image-plane/incoming/icloud/accepted/`.
7. Put conflicts and invalid items under `~/image-plane/incoming/icloud/quarantine/`.
8. Write a new timestamped summary file. Never overwrite an old summary.
9. Write `COMPLETE` only when every eligible Mini B item has a checked receipt, every Mini A file matches, and no unresolved item remains.

The runner must support a check-only mode for tests and status.

Do not call a reader, model, matcher, database writer, or delete command.

## Text rules

Use ASD-STE100 Simplified Technical English in comments and output.
Use short sentences.
Every printed count must come from that run.
Print a `Counted by:` line with the command or query used.
Never print photo contents or secret values.

## Tests

Use temporary folders and fake export callbacks. Do not open real photos.

Test:

1. hidden and deleted items stay out;
2. duplicate filenames in different item folders stay separate;
3. one item can have photo and motion members;
4. incomplete staging resumes;
5. one failure does not stop later successes;
6. a hash conflict quarantines the item;
7. a checked item skips only after hash recheck;
8. excluded hashes stay suppressed;
9. a receipt cannot pass with a missing member;
10. repeated mirror creates no duplicate;
11. `COMPLETE` cannot exist with unresolved work;
12. source code contains no deletion call for intake paths.

Run the test suite. Do not deploy or run a real export. The orchestrator owns the real one-photo proof.