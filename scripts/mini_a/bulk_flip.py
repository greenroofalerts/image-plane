#!/usr/bin/env python3
"""Bulk flip driver (SITE PAGES RUN 2026-07-24).

Flips every keeper spine row for the given job refs public, one by one,
through the RUNNING flip server's proven POST /flip path (localhost:8788).
No new publish logic lives here: curation, EXIF strip, upload, patch and
fail-closed rollback all stay inside flip_server.flip_on, proven 11 Jul.

Reads .env.flip ONLY to list row ids (read-only REST query). Every write
goes through the live flip server. Python 3.9 (Mini A).

Usage: python3 bulk_flip.py 1124-19 1539-22 1465-21
Exit 0 = zero failures. Exit 2 = at least one failure (listed plainly).
"""
import json
import os
import sys
import urllib.parse
import urllib.request

ROOT = os.path.expanduser("~/image-plane")
ENV_PATH = os.path.join(ROOT, ".env.flip")
FLIP_URL = "http://localhost:8788/flip"


def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def main():
    refs = sys.argv[1:]
    if not refs:
        print("usage: bulk_flip.py <job_ref> [...]")
        sys.exit(1)
    env = load_env(ENV_PATH)
    base = env["LEEOSPLUS_URL"].rstrip("/")
    key = env["LEEOSPLUS_SERVICE_KEY"]
    ok = fail = skip = 0
    for ref in refs:
        q = ("%s/rest/v1/visual_observations?job_ref=eq.%s"
             "&select=id,is_public,gra_media_path&order=visit_date.asc"
             % (base, urllib.parse.quote(ref)))
        req = urllib.request.Request(
            q, headers={"apikey": key, "Authorization": "Bearer " + key})
        rows = json.load(urllib.request.urlopen(req, timeout=30))
        print("%s: %d rows" % (ref, len(rows)))
        for r in rows:
            if r.get("is_public") and r.get("gra_media_path"):
                skip += 1
                continue
            body = json.dumps({"id": r["id"], "public": True}).encode()
            freq = urllib.request.Request(
                FLIP_URL, data=body,
                headers={"Content-Type": "application/json"}, method="POST")
            try:
                res = json.load(urllib.request.urlopen(freq, timeout=180))
            except Exception as e:
                res = {"ok": False, "error": str(e)}
            if res.get("ok"):
                ok += 1
            else:
                fail += 1
                print("  FAIL id=%s: %s" % (r["id"], res.get("error")))
    print("done: flipped %d, already public %d, failed %d" % (ok, skip, fail))
    sys.exit(0 if fail == 0 else 2)


main()
