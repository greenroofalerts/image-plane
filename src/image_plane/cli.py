"""image-plane CLI.

    image-plane ingest <folder> [--source takeout|icloud|auto] [--db PATH]
    image-plane dedup [--threshold N] [--db PATH]
    image-plane caption [--model NAME] [--pull] [--limit N] [--db PATH]
    image-plane status [--db PATH]
    image-plane file [folder] [--stage-job REF] [--album TITLE]
    image-plane serve [--host HOST] [--port N]
    image-plane report --job REF --selection NAME
    image-plane export-pack --job REF --selection NAME
    image-plane gra-prepare --job REF --selection NAME [--event REF]
    image-plane albums-discover
    image-plane albums-ingest <folder>
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import albums
from . import caption as captionmod
from . import db as dbmod
from . import dedup as dedupmod
from . import gra
from . import ingest as ingestmod
from . import pack
from . import paths
from . import report
from . import server as servermod
from .cabinet import file_folder


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

    sp = sub.add_parser("file", help="file a folder into the Image Plane cabinet")
    sp.add_argument("folder", type=Path, nargs="?", default=paths.pancras_incoming())
    sp.add_argument("--stage-job", help="show unresolved items on this job screen (does not mint)")
    sp.add_argument("--album", help="source album title")
    sp.add_argument("--album-id", help="source album identifier")

    sp = sub.add_parser("serve", help="internal job screen")
    sp.add_argument("--host", default="0.0.0.0")
    sp.add_argument("--port", type=int, default=paths.DEFAULT_PORT)

    sp = sub.add_parser("report", help="PDF from a named saved selection")
    sp.add_argument("--job", required=True)
    sp.add_argument("--selection", required=True)
    sp.add_argument("--out", type=Path)

    sp = sub.add_parser("export-pack", help="installer pack from a named saved selection")
    sp.add_argument("--job", required=True)
    sp.add_argument("--selection", required=True)
    sp.add_argument("--out", type=Path)

    sp = sub.add_parser("gra-prepare", help="copy approved derivatives only")
    sp.add_argument("--job", required=True)
    sp.add_argument("--selection", required=True)
    sp.add_argument("--event", help="existing GRA visit / billable event ref")
    sp.add_argument("--out", type=Path)

    sub.add_parser("albums-discover", help="list unprocessed Google albums if credentials exist")
    sp = sub.add_parser("albums-ingest", help="named-folder ingest through the cabinet path")
    sp.add_argument("folder", type=Path)
    sp.add_argument("--stage-job")
    sp.add_argument("--album")
    sp.add_argument("--album-id")

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
        cab = conn.execute("SELECT identity_status, COUNT(*) c FROM cabinet_items GROUP BY 1").fetchall()
        cab_txt = ", ".join(f"{r['identity_status']}={r['c']}" for r in cab) or "empty"
        print(f"photos: {total} | captioned: {capd} | dupes: {dupe_txt} | poisoned: {poisoned}")
        print(f"cabinet: {cab_txt}")
        print(f"job screen: {paths.job_url(paths.PANCRAS_JOB)}")

    elif args.cmd == "file":
        counts = file_folder(
            conn,
            args.folder,
            stage_job=args.stage_job,
            album_title=args.album,
            album_id=args.album_id,
        )
        print(f"cabinet file complete: {counts}")
        print(f"open {paths.job_url(args.stage_job or paths.PANCRAS_JOB)}")

    elif args.cmd == "serve":
        conn.close()
        servermod.serve(host=args.host, port=args.port, db_path=args.db)
        return 0

    elif args.cmd == "report":
        dest = report.build_report_pdf(conn, args.job, args.selection, args.out)
        print(dest)

    elif args.cmd == "export-pack":
        dest = pack.export_pack(conn, args.job, args.selection, args.out)
        print(dest)

    elif args.cmd == "gra-prepare":
        payload = gra.prepare_publication(
            conn, args.job, args.selection, gra_event_ref=args.event, dest_dir=args.out
        )
        print(payload.get("blocker") or f"copied {len(payload.get('approved_copied') or [])} approved derivatives")

    elif args.cmd == "albums-discover":
        result = albums.discover_google_albums(conn)
        print(result.get("blocker") or result)

    elif args.cmd == "albums-ingest":
        result = albums.ingest_named_album(
            conn,
            args.folder,
            stage_job=args.stage_job,
            album_title=args.album,
            album_id=args.album_id,
        )
        print(result)

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
