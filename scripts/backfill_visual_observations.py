#!/usr/bin/env python3
"""
F5 backfill insert — POSTs exported visual_observations rows to LeeOSplus Supabase.

Spec: docs/F5-VISUAL-OBSERVATIONS-ROOF-TIMELINE-2026-07-11.md

Usage:
  python3 scripts/backfill_visual_observations.py <path-to-jsonl>

Loads SUPABASE_LEEOSPLUS_URL / SUPABASE_LEEOSPLUS_SERVICE_KEY from
/Users/Lee/leeos-plus/.env (parsed directly, not sourced). Upserts in batches
of 500 on original_path (Prefer: resolution=merge-duplicates). Never prints
or logs the service key. Retries a failed batch once; two failures on the
same batch = stop and report the response body (secrets stripped).
"""
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

ENV_PATH = Path("/Users/Lee/leeos-plus/.env")
BATCH_SIZE = 500


def load_env(path):
    env = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            # strip matching surrounding quotes if present
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                val = val[1:-1]
            env[key] = val
    return env


def redact(text, secret):
    if not secret:
        return text
    return text.replace(secret, "<REDACTED>")


def post_batch(url, apikey, service_key, batch):
    endpoint = f"{url.rstrip('/')}/rest/v1/visual_observations?on_conflict=original_path"
    body = json.dumps(batch).encode("utf-8")
    req = urllib.request.Request(endpoint, data=body, method="POST")
    req.add_header("apikey", apikey)
    req.add_header("Authorization", f"Bearer {service_key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Prefer", "resolution=merge-duplicates,return=minimal")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, None
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        return e.code, body_text
    except urllib.error.URLError as e:
        return None, str(e)


def main():
    if len(sys.argv) != 2:
        print("usage: backfill_visual_observations.py <path-to-jsonl>", file=sys.stderr)
        sys.exit(1)

    jsonl_path = Path(sys.argv[1])
    rows = []
    with open(jsonl_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    print(f"Loaded {len(rows)} rows from {jsonl_path}")

    env = load_env(ENV_PATH)
    url = env.get("SUPABASE_LEEOSPLUS_URL")
    service_key = env.get("SUPABASE_LEEOSPLUS_SERVICE_KEY")
    if not url or not service_key:
        print("ERROR: SUPABASE_LEEOSPLUS_URL / SUPABASE_LEEOSPLUS_SERVICE_KEY not found in env file", file=sys.stderr)
        sys.exit(1)

    batches = [rows[i:i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
    print(f"{len(batches)} batches of up to {BATCH_SIZE}")

    succeeded = 0
    failed_batches = []

    for idx, batch in enumerate(batches):
        status, err = post_batch(url, service_key, service_key, batch)
        if status is not None and 200 <= status < 300:
            succeeded += 1
            print(f"batch {idx + 1}/{len(batches)}: OK ({len(batch)} rows)")
            continue

        print(f"batch {idx + 1}/{len(batches)}: FAILED status={status}, retrying once...", file=sys.stderr)
        status2, err2 = post_batch(url, service_key, service_key, batch)
        if status2 is not None and 200 <= status2 < 300:
            succeeded += 1
            print(f"batch {idx + 1}/{len(batches)}: OK on retry ({len(batch)} rows)")
            continue

        safe_err = redact(err2 or err or "", service_key)
        print(f"batch {idx + 1}/{len(batches)}: FAILED TWICE. status={status2}. body={safe_err}", file=sys.stderr)
        failed_batches.append({"batch_index": idx, "status": status2, "body": safe_err})

    print(json.dumps({
        "total_batches": len(batches),
        "succeeded": succeeded,
        "failed": len(failed_batches),
        "failed_batches": failed_batches,
    }, indent=2))

    if failed_batches:
        sys.exit(2)


if __name__ == "__main__":
    main()
