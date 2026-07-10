#!/usr/bin/env python3
"""
counts.py -- THE single source for image-plane corpus numbers (F1 Item A, 2026-07-10).

Every number below is derived by an explicit join over on-disk ledgers -- never a bare
row count. Python 3.9 compatible (Mini A runs 3.9): no match-statements, no `X | Y` type
unions.

Usage:
    python3 counts.py            human-readable report
    python3 counts.py --json     machine-readable report; every field carries
                                  counted_by (the join, one line) and counted_at (ISO ts)
    python3 counts.py --check    recomputes and asserts internal consistency
                                  (allocated + unallocated = keeps; splits sum).
                                  Exit 0 = all checks pass. Exit 1 = a check failed.

Inputs (read-only; this script never writes to any of them):
    classified.jsonl                verdict: keep/drop/quarantine, keyed by path
    grind/allocation_v2.jsonl        photo -> job_ref allocation attempts
    grind/allocation_v2_flags.jsonl  misreadable-row flags (excluded/no_job_ref/
                                     non_keep_path) -- generate/regenerate with
                                     grind/build_allocation_v2_flags.py whenever
                                     allocation_v2.jsonl regenerates. This script
                                     refuses to run if the flags file is missing --
                                     it will never silently fall back to a stale copy
                                     or recompute flags inline.
    geolocations.jsonl               lat/lon per path
    grind/kept_missing_on_disk.json  {kept_total, present, missing: [paths]}
    photo_ledger_merged.jsonl        iCloud-side sha256 per path (content-hash source)
    takeout_ledger_merged.jsonl      takeout-side sha256 per path

10 Jul 2026 recount reference magnitudes (informational only -- printed as a diff,
never used to "fix" a differing run): 12,338 keep / 3,203 drop / 885 quarantine;
allocation_v2 7,099 = 6,748 live-with-job-ref (6,585 icloud + 163 takeout) + 269
excluded + 82 no-job-ref; 185 non-keep paths; allocated keeps 6,563; unallocated
keeps 5,775 (4,966 gps-but-no-job / 809 no-coords, of which 407 are also missing
on disk); takeout ledger 5,054.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))

REFERENCE = {
    'kept': 12338,
    'dropped': 3203,
    'quarantined': 885,
    'allocation_v2_total': 7099,
    'allocation_excluded': 269,
    'allocation_no_job_ref': 82,
    'allocation_non_keep_path': 185,
    'allocated_keeps': 6563,
    'unallocated_keeps': 5775,
    'unallocated_gps_no_job': 4966,
    'unallocated_no_coords': 809,
    'unallocated_also_missing_on_disk': 407,
    'takeout_total': 5054,
}


def _path(*parts):
    return os.path.join(ROOT, *parts)


def load_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def compute():
    ts = now_iso()
    fields = {}

    # --- kept / dropped / quarantined ---------------------------------
    classified_path = _path('classified.jsonl')
    classified_rows = load_jsonl(classified_path)
    verdicts = {}
    verdict_totals = {'keep': 0, 'drop': 0, 'quarantine': 0}
    for r in classified_rows:
        verdicts[r['path']] = r['verdict']
        verdict_totals[r['verdict']] = verdict_totals.get(r['verdict'], 0) + 1
    keeps = set(p for p, v in verdicts.items() if v == 'keep')

    fields['icloud_ledger_total'] = {
        'value': len(classified_rows),
        'counted_by': 'len(classified.jsonl) rows',
        'counted_at': ts,
    }
    fields['kept'] = {
        'value': verdict_totals.get('keep', 0),
        'counted_by': "classified.jsonl rows where verdict == 'keep'",
        'counted_at': ts,
    }
    fields['dropped'] = {
        'value': verdict_totals.get('drop', 0),
        'counted_by': "classified.jsonl rows where verdict == 'drop'",
        'counted_at': ts,
    }
    fields['quarantined'] = {
        'value': verdict_totals.get('quarantine', 0),
        'counted_by': "classified.jsonl rows where verdict == 'quarantine'",
        'counted_at': ts,
    }

    # --- allocation_v2 + flags file ------------------------------------
    alloc_rows = load_jsonl(_path('grind', 'allocation_v2.jsonl'))
    alloc_total = len(alloc_rows)

    flags_path = _path('grind', 'allocation_v2_flags.jsonl')
    if not os.path.exists(flags_path):
        raise RuntimeError(
            'grind/allocation_v2_flags.jsonl is missing. counts.py will not '
            'recompute flags inline or fall back to a cached number -- run '
            'grind/build_allocation_v2_flags.py first.'
        )

    flags_by_path = {}
    flag_counts = {'excluded': 0, 'no_job_ref': 0, 'non_keep_path': 0}
    dup_flagged = []
    for r in load_jsonl(flags_path):
        if r.get('_meta'):
            continue
        p = r['path']
        if p in flags_by_path:
            dup_flagged.append(p)
        flags_by_path[p] = r['flag']
        flag_counts[r['flag']] = flag_counts.get(r['flag'], 0) + 1

    allocated_keep_paths = set()
    job_ref_by_path = {}
    for r in alloc_rows:
        p = r['path']
        if p in flags_by_path:
            continue
        allocated_keep_paths.add(p)
        job_ref_by_path[p] = r.get('job_ref')

    fields['allocation_v2_total'] = {
        'value': alloc_total,
        'counted_by': 'len(grind/allocation_v2.jsonl) rows',
        'counted_at': ts,
    }
    fields['allocation_excluded'] = {
        'value': flag_counts['excluded'],
        'counted_by': "grind/allocation_v2_flags.jsonl rows flagged 'excluded' "
                       "(source: allocation_v2.jsonl row['excluded'] truthy)",
        'counted_at': ts,
    }
    fields['allocation_no_job_ref'] = {
        'value': flag_counts['no_job_ref'],
        'counted_by': "grind/allocation_v2_flags.jsonl rows flagged 'no_job_ref' "
                       "(not excluded, job_ref is null)",
        'counted_at': ts,
    }
    fields['allocation_non_keep_path'] = {
        'value': flag_counts['non_keep_path'],
        'counted_by': "grind/allocation_v2_flags.jsonl rows flagged 'non_keep_path' "
                       "(not excluded, has job_ref, but classified.jsonl verdict for "
                       "that path is not 'keep' or the path is absent from "
                       "classified.jsonl entirely -- e.g. takeout paths, which "
                       "classified.jsonl never covers)",
        'counted_at': ts,
    }
    fields['allocated_keeps'] = {
        'value': len(allocated_keep_paths),
        'counted_by': 'allocation_v2.jsonl rows whose path is NOT present in '
                       'allocation_v2_flags.jsonl (i.e. not excluded, has a job_ref, '
                       "and classified.jsonl verdict == 'keep')",
        'counted_at': ts,
    }

    unallocated_keeps = keeps - allocated_keep_paths
    fields['unallocated_keeps'] = {
        'value': len(unallocated_keeps),
        'counted_by': 'classified.jsonl keep-verdict paths minus allocated_keeps',
        'counted_at': ts,
    }

    # --- gps split of unallocated keeps --------------------------------
    geo_rows = load_jsonl(_path('geolocations.jsonl'))
    gps = {}
    for r in geo_rows:
        gps[r['path']] = (r.get('lat'), r.get('lon'))

    gps_no_job = set()
    no_coords = set()
    for p in unallocated_keeps:
        latlon = gps.get(p)
        if latlon and latlon[0] is not None and latlon[1] is not None:
            gps_no_job.add(p)
        else:
            no_coords.add(p)

    fields['unallocated_gps_no_job'] = {
        'value': len(gps_no_job),
        'counted_by': 'unallocated_keeps with a non-null lat/lon in geolocations.jsonl',
        'counted_at': ts,
    }
    fields['unallocated_no_coords'] = {
        'value': len(no_coords),
        'counted_by': 'unallocated_keeps with no lat/lon row (or a null one) in '
                       'geolocations.jsonl',
        'counted_at': ts,
    }

    missing_data = json.load(open(_path('grind', 'kept_missing_on_disk.json')))
    missing_set = set(missing_data.get('missing', []))
    also_missing = unallocated_keeps & missing_set
    also_missing_gps = also_missing & gps_no_job
    also_missing_no_coords = also_missing & no_coords

    fields['unallocated_also_missing_on_disk'] = {
        'value': len(also_missing),
        'counted_by': "unallocated_keeps intersect grind/kept_missing_on_disk.json"
                       "['missing'] -- this is a CROSS-CUT of the gps/no-coords split "
                       "above, not a third additive partition: unallocated_gps_no_job "
                       "+ unallocated_no_coords already sum to unallocated_keeps on "
                       "their own.",
        'counted_at': ts,
    }
    fields['unallocated_also_missing_on_disk_with_gps'] = {
        'value': len(also_missing_gps),
        'counted_by': 'unallocated_also_missing_on_disk intersect unallocated_gps_no_job',
        'counted_at': ts,
    }
    fields['unallocated_also_missing_on_disk_no_coords'] = {
        'value': len(also_missing_no_coords),
        'counted_by': 'unallocated_also_missing_on_disk intersect unallocated_no_coords',
        'counted_at': ts,
    }

    # --- roofs with tied photos -----------------------------------------
    roof_refs = set()
    for p in allocated_keep_paths:
        jr = job_ref_by_path.get(p)
        if jr:
            roof_refs.add(jr)
    fields['roofs_with_tied_photos'] = {
        'value': len(roof_refs),
        'counted_by': 'distinct job_ref values among allocated_keeps (i.e. roofs with '
                       'at least one photo actually tied to them)',
        'counted_at': ts,
    }

    # --- takeout / iCloud overlap ----------------------------------------
    icloud_hash_rows = load_jsonl(_path('photo_ledger_merged.jsonl'))
    icloud_hashes = set(r['sha256'] for r in icloud_hash_rows if r.get('sha256'))
    takeout_rows = load_jsonl(_path('takeout_ledger_merged.jsonl'))
    takeout_total = len(takeout_rows)
    takeout_with_twin = 0
    for r in takeout_rows:
        h = r.get('sha256')
        if h and h in icloud_hashes:
            takeout_with_twin += 1
    takeout_without_twin = takeout_total - takeout_with_twin

    fields['takeout_total'] = {
        'value': takeout_total,
        'counted_by': 'len(takeout_ledger_merged.jsonl) rows',
        'counted_at': ts,
    }
    fields['takeout_with_icloud_twin'] = {
        'value': takeout_with_twin,
        'counted_by': "dedupe key = sha256 content hash, present on BOTH sides "
                       "(photo_ledger_merged.jsonl for iCloud, "
                       "takeout_ledger_merged.jsonl for takeout) -- per spec, content "
                       "hash is used whenever present in both ledgers, ahead of the "
                       "basename+bytes fallback. Count = takeout rows whose sha256 "
                       "also appears in the iCloud hash set.",
        'counted_at': ts,
    }
    fields['takeout_without_icloud_twin'] = {
        'value': takeout_without_twin,
        'counted_by': 'takeout_total minus takeout_with_icloud_twin -- the '
                       'never-counted number',
        'counted_at': ts,
    }

    internal = {
        'keeps': keeps,
        'allocated_keep_paths': allocated_keep_paths,
        'unallocated_keeps': unallocated_keeps,
        'gps_no_job': gps_no_job,
        'no_coords': no_coords,
        'also_missing_gps': also_missing_gps,
        'also_missing_no_coords': also_missing_no_coords,
        'dup_flagged': dup_flagged,
    }
    return fields, internal


def print_human(fields):
    print('image-plane corpus counts -- ' + fields['kept']['counted_at'])
    print('')
    print('iCloud ledger: %d total (kept %d / dropped %d / quarantined %d)' % (
        fields['icloud_ledger_total']['value'],
        fields['kept']['value'], fields['dropped']['value'],
        fields['quarantined']['value']))
    print('  Counted by: %s' % fields['kept']['counted_by'])
    print('')
    print('allocation_v2: %d rows = %d allocated keeps + %d excluded + '
          '%d no-job-ref + %d non-keep-path' % (
              fields['allocation_v2_total']['value'],
              fields['allocated_keeps']['value'],
              fields['allocation_excluded']['value'],
              fields['allocation_no_job_ref']['value'],
              fields['allocation_non_keep_path']['value']))
    print('  Counted by: %s' % fields['allocated_keeps']['counted_by'])
    print('')
    print('unallocated keeps: %d = %d gps-but-no-job + %d no-coords '
          '(%d of those %d are also missing on disk: %d with gps, %d no-coords)' % (
              fields['unallocated_keeps']['value'],
              fields['unallocated_gps_no_job']['value'],
              fields['unallocated_no_coords']['value'],
              fields['unallocated_also_missing_on_disk']['value'],
              fields['unallocated_keeps']['value'],
              fields['unallocated_also_missing_on_disk_with_gps']['value'],
              fields['unallocated_also_missing_on_disk_no_coords']['value']))
    print('  Counted by: %s' % fields['unallocated_also_missing_on_disk']['counted_by'])
    print('')
    print('roofs with tied photos: %d' % fields['roofs_with_tied_photos']['value'])
    print('  Counted by: %s' % fields['roofs_with_tied_photos']['counted_by'])
    print('')
    print('takeout ledger: %d total -- %d with an iCloud twin / %d without '
          '(never-counted number)' % (
              fields['takeout_total']['value'],
              fields['takeout_with_icloud_twin']['value'],
              fields['takeout_without_icloud_twin']['value']))
    print('  Counted by: %s' % fields['takeout_with_icloud_twin']['counted_by'])
    print('')

    diffs = []
    for key, ref_val in REFERENCE.items():
        if key in fields and fields[key]['value'] != ref_val:
            diffs.append((key, ref_val, fields[key]['value']))
    if diffs:
        print('REFERENCE DIFF vs 10 Jul recount (informational only -- not corrected):')
        for key, ref_val, actual in diffs:
            print('  %s: reference=%d actual=%d delta=%+d' % (
                key, ref_val, actual, actual - ref_val))
    else:
        print('Matches all 10 Jul recount reference magnitudes.')


def print_json(fields):
    out = {k: v for k, v in fields.items()}
    print(json.dumps(out, indent=2, sort_keys=True))


def run_check(fields, internal):
    ok = True
    problems = []

    def check(name, lhs, rhs):
        nonlocal ok
        if lhs != rhs:
            ok = False
            problems.append('%s: %d != %d' % (name, lhs, rhs))

    check('kept+dropped+quarantined == icloud_ledger_total',
          fields['kept']['value'] + fields['dropped']['value'] + fields['quarantined']['value'],
          fields['icloud_ledger_total']['value'])

    check('allocated_keeps+excluded+no_job_ref+non_keep_path == allocation_v2_total',
          fields['allocated_keeps']['value'] + fields['allocation_excluded']['value'] +
          fields['allocation_no_job_ref']['value'] + fields['allocation_non_keep_path']['value'],
          fields['allocation_v2_total']['value'])

    check('allocated_keeps+unallocated_keeps == kept',
          fields['allocated_keeps']['value'] + fields['unallocated_keeps']['value'],
          fields['kept']['value'])

    check('unallocated_gps_no_job+unallocated_no_coords == unallocated_keeps',
          fields['unallocated_gps_no_job']['value'] + fields['unallocated_no_coords']['value'],
          fields['unallocated_keeps']['value'])

    check('also_missing_with_gps+also_missing_no_coords == also_missing_on_disk',
          fields['unallocated_also_missing_on_disk_with_gps']['value'] +
          fields['unallocated_also_missing_on_disk_no_coords']['value'],
          fields['unallocated_also_missing_on_disk']['value'])

    check('takeout_with_twin+takeout_without_twin == takeout_total',
          fields['takeout_with_icloud_twin']['value'] + fields['takeout_without_icloud_twin']['value'],
          fields['takeout_total']['value'])

    if internal['dup_flagged']:
        ok = False
        problems.append('allocation_v2_flags.jsonl has %d path(s) flagged more than '
                         'once (each row must carry at most one flag): %s' % (
                             len(internal['dup_flagged']), internal['dup_flagged'][:5]))

    if ok:
        print('counts.py --check: PASS -- all internal-consistency assertions hold.')
        return 0
    else:
        print('counts.py --check: FAIL')
        for p in problems:
            print('  - ' + p)
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true', help='machine-readable output')
    parser.add_argument('--check', action='store_true',
                         help='self-test internal consistency; non-zero exit on failure')
    args = parser.parse_args()

    try:
        fields, internal = compute()
    except Exception as exc:
        if args.check:
            print('counts.py --check: FAIL -- could not compute counts: %s' % exc)
            sys.exit(1)
        else:
            print('counts.py: FAILED to compute counts: %s' % exc, file=sys.stderr)
            sys.exit(1)

    if args.check:
        sys.exit(run_check(fields, internal))
    elif args.json:
        print_json(fields)
    else:
        print_human(fields)


if __name__ == '__main__':
    main()
