#!/usr/bin/env python3
"""Push repo_dedupe_flags.jsonl verdicts to the spine (LeeOSplus visual_observations).

Additive only: sets duplicate_of + dedupe_kind by original_path. Never deletes rows.
Runs on Mini A; creds from ~/image-plane/.env.flip. Python 3.9.
Verify-after (orchestrator, same turn): total row count stays 8488;
patched count == flags rows whose path is a spine original_path.
"""
import json
import os
import sys
import urllib.request
import urllib.parse

ENV_PATH = os.path.expanduser("~/image-plane/.env.flip")
FLAGS = os.path.expanduser("~/image-plane/grind/repo_dedupe_flags.jsonl")


def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main():
    env = load_env(ENV_PATH)
    base = env["LEEOSPLUS_URL"].rstrip("/")
    key = env["LEEOSPLUS_SERVICE_KEY"]
    headers = {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    rows = []
    with open(FLAGS) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    rows.sort(key=lambda r: r["path"])  # deterministic order

    patched, missed = 0, []
    for r in rows:
        qs = urllib.parse.urlencode({"original_path": "eq." + r["path"]})
        url = base + "/rest/v1/visual_observations?" + qs
        body = json.dumps(
            {"duplicate_of": r["duplicate_of"], "dedupe_kind": r["kind"]}
        ).encode()
        req = urllib.request.Request(url, data=body, headers=headers, method="PATCH")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                updated = json.loads(resp.read().decode() or "[]")
        except Exception as e:  # network/HTTP failure: report, never crash silently
            print("ERROR patching %s: %s" % (r["path"], e))
            sys.exit(1)
        if updated:
            patched += len(updated)
        else:
            missed.append(r["path"])

    print("flags rows: %d" % len(rows))
    print("patched spine rows: %d" % patched)
    print("flags paths not in spine (expected for non-valid-set rows): %d" % len(missed))
    for p in missed[:10]:
        print("  miss:", p)
    if len(missed) > 10:
        print("  ... %d more" % (len(missed) - 10))


if __name__ == "__main__":
    main()
