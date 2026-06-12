"""image-plane CLI.

    image-plane ingest <folder> [--source takeout|icloud|auto] [--db PATH]
    image-plane dedup [--threshold N] [--db PATH]
    image-plane caption [--model NAME] [--pull] [--limit N] [--db PATH]
    image-plane status [--db PATH]

Every command is resumable: ingest skips unchanged files, dedup is a
pure rebuild from the DB, caption only touches rows without a caption.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import caption as captionmod
from . import db as dbmod
from . import dedup as dedupmod
from . import ingest as ingestmod


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    p = argparse.ArgumentParser(prog="image-plane", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", type=Path, default=dbmod.DEFAULT_DB, help="SQLite path")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("ingest", help="walk a folder, write metadata rows")
    sp.add_argument("folder", type=Path)
    sp.add_argument("--source", choices=["takeout", "icloud", "auto"], default="auto")
    sp.add_argument("--retry-errors", action="store_true",
                    help="re-attempt files previously logged to ingest_errors (LEE-559)")

    sp = sub.add_parser("dedup", help="find exact + near duplicates")
    sp.add_argument("--threshold", type=int, default=dedupmod.DEFAULT_THRESHOLD,
                    help="max dHash hamming distance for near-dupes (default 8)")
    sp.add_argument("--show", action="store_true", help="print duplicate pairs")

    sp = sub.add_parser("caption", help="caption uncaptioned rows via local Ollama")
    sp.add_argument("--model", help="override model (default: best installed vision model)")
    sp.add_argument("--pull", action="store_true",
                    help="allow downloading the recommended model if none installed")
    sp.add_argument("--limit", type=int, help="caption at most N images (benchmarking)")
    sp.add_argument("--max-fail-pct", type=float, default=10.0,
                    help="exit nonzero when more than this %% of attempted captions fail (LEE-559)")

    sub.add_parser("status", help="row counts and pipeline progress")

    args = p.parse_args(argv)
    conn = dbmod.connect(args.db)
    log = logging.getLogger("image_plane")

    if args.cmd == "ingest":
        counts = ingestmod.ingest_folder(conn, args.folder, source=args.source,
                                         retry_errors=args.retry_errors)
        print(f"ingest complete: {counts}")
        if counts["error"]:
            print(f"  WARNING: {counts['error']} unreadable file(s) skipped — "
                  f"see the ingest_errors table; re-attempt with --retry-errors")

    elif args.cmd == "dedup":
        stats = dedupmod.find_duplicates(conn, threshold=args.threshold)
        print(f"dedup complete: {stats}")
        if args.show:
            for r in dedupmod.report(conn):
                print(f"  [{r['kind']} d={r['distance']}] {r['dup_path']} -> keep {r['kept_path']}")

    elif args.cmd == "caption":
        model = args.model or captionmod.ensure_vision_model(auto_pull=args.pull)
        if not model:
            log.error("no vision model available — see messages above")
            return 1
        stats = captionmod.caption_pending(conn, model, limit=args.limit)
        print(f"caption complete: {stats}")
        attempted = stats["captioned"] + stats["errors"]
        print(f"  captioned {stats['captioned']}, failed {stats['errors']} "
              f"(of {attempted} attempted)")
        if stats["seconds_per_image"]:
            for n, label in [(10_000, "10k"), (50_000, "50k")]:
                hours = stats["seconds_per_image"] * n / 3600
                print(f"  estimate for {label} photos: {hours:.1f} hours")
        # LEE-559: a failed overnight run must be loud, not a quiet exit 0.
        if attempted and (stats["errors"] / attempted) * 100 > args.max_fail_pct:
            log.error("caption failure rate %.0f%% exceeds --max-fail-pct %.0f%% — failing loudly",
                      stats["errors"] / attempted * 100, args.max_fail_pct)
            conn.close()
            return 2

    elif args.cmd == "status":
        total = conn.execute("SELECT COUNT(*) c FROM photos").fetchone()["c"]
        capd = conn.execute("SELECT COUNT(*) c FROM photos WHERE caption IS NOT NULL").fetchone()["c"]
        dupes = conn.execute("SELECT kind, COUNT(*) c FROM duplicates GROUP BY kind").fetchall()
        dupe_txt = ", ".join("{}={}".format(r["kind"], r["c"]) for r in dupes) or "none recorded"
        poisoned = conn.execute("SELECT COUNT(*) c FROM ingest_errors").fetchone()["c"]
        print(f"photos: {total} | captioned: {capd} | dupes: {dupe_txt} | poisoned: {poisoned}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
