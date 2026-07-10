#!/usr/bin/env python3
"""
grind/build_allocation_v2_flags.py -- generates grind/allocation_v2_flags.jsonl
(F1 Item A.2, 2026-07-10).

Marks every allocation_v2.jsonl row that should NOT count as an "allocated keep",
so the 269 + 82 + 185 misreadable rows are machine-distinguishable without ever
rewriting allocation_v2.jsonl itself:

  excluded       -> row['excluded'] is truthy
  no_job_ref     -> row['job_ref'] is None (and not already excluded)
  non_keep_path  -> classified.jsonl verdict for this path is not 'keep', OR the
                    path is not in classified.jsonl at all (takeout paths are
                    never covered by classified.jsonl) (and not excluded/no_job_ref)

Precedence is excluded > no_job_ref > non_keep_path -- each row gets at most one flag.
Rows with none of these three problems (i.e. genuine allocated keeps) are NOT written
here; counts.py treats "not present in this file" as "allocated keep".

Regenerate this file whenever allocation_v2.jsonl regenerates -- counts.py refuses to
run if this file is missing; it will not silently fall back to a stale copy.

Does NOT modify allocation_v2.jsonl, classified.jsonl, or any other read-only input.
"""
import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def main():
    verdicts = {}
    for r in load_jsonl(_path('classified.jsonl')):
        verdicts[r['path']] = r['verdict']

    alloc_rows = load_jsonl(_path('grind', 'allocation_v2.jsonl'))

    out_path = _path('grind', 'allocation_v2_flags.jsonl')
    counts = {'excluded': 0, 'no_job_ref': 0, 'non_keep_path': 0}

    with open(out_path, 'w') as out:
        header = {
            '_meta': True,
            'generated_from': 'grind/allocation_v2.jsonl',
            'generated_by': 'grind/build_allocation_v2_flags.py',
            'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'note': ('Regenerate this file whenever allocation_v2.jsonl regenerates. '
                     'Flags are NOT computed live by counts.py -- it reads this file.'),
        }
        out.write(json.dumps(header) + '\n')

        for r in alloc_rows:
            p = r['path']
            flag = None
            detail = None
            if r.get('excluded'):
                flag = 'excluded'
                detail = r['excluded']
            elif r.get('job_ref') is None:
                flag = 'no_job_ref'
                detail = None
            else:
                v = verdicts.get(p)
                if v != 'keep':
                    flag = 'non_keep_path'
                    detail = v if v is not None else 'not_in_classified_ledger'

            if flag:
                counts[flag] += 1
                out.write(json.dumps({'path': p, 'flag': flag, 'detail': detail}) + '\n')

    print('Wrote', out_path)
    print('excluded:', counts['excluded'])
    print('no_job_ref:', counts['no_job_ref'])
    print('non_keep_path:', counts['non_keep_path'])
    print('total flagged:', sum(counts.values()))
    print('allocation_v2 total rows:', len(alloc_rows))
    print('implied allocated_keeps:', len(alloc_rows) - sum(counts.values()))


if __name__ == '__main__':
    main()
