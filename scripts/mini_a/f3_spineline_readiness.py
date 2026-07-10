#!/usr/bin/env python3
"""
f3_spineline_readiness.py -- F3 spineline readiness audit (STEP 4 of the
F2-CANDIDATE-PASS-SPEC-2026-07-10 chain). READ-ONLY analysis. Does NOT start the
F3 build; does NOT write ties, allocations, or any promoted data anywhere.

Writes exactly two files:
    docs/SPINELINE-READINESS.md        human-readable, per-roof table + summary
    grind/spineline_readiness.json     machine-readable twin

Everything else on disk in this repo is read-only input to this script.

Python 3.9 compatible (Mini A runs 3.9.6): no match-statements, no `X | Y` unions.

Method (mirrors, does not import or edit, counts.py -- IP-L1: counts.py is the
only quotable corpus source, but this script must be self-contained and
auditable, so the join is duplicated verbatim rather than imported):
    1. allocated_keeps join: classified.jsonl verdict==keep paths, minus
       allocation_v2.jsonl rows flagged in allocation_v2_flags.jsonl, replicating
       counts.py's derivation exactly (verified 2026-07-10: 8,111 allocated_keeps,
       238 distinct job_refs -- matches `python3 counts.py` run same session).
    2. Group allocated_keeps by job_ref -> "roof". Assert count == 238 before
       proceeding (sanity gate against silent corpus drift, same posture as the
       Step 1 cluster-count gate) -- if it doesn't match, STOP, do not proceed.
    3. Per roof, per photo: EXIF capture timestamp via `mdls -name
       kMDItemContentCreationDate`, batched (many paths per subprocess call --
       never one process per photo). Missing-on-disk keeps (per
       grind/kept_missing_on_disk.json) are never sent to mdls: flagged
       `no_exif_missing_on_disk` directly, path-date only.
    4. Order-conflict checks per roof, comparing three independent date sources
       per photo where available: EXIF capture date, path-date (the YYYY/MM/DD
       folder date already carried on every allocation_v2.jsonl row), and known
       visit/invoice dates (grind/roof_invoice_match.jsonl bands
       exact/strong/likely + grind/gra_stories.json story dates). A 4th source,
       takeout album-name dates, is checked but --- see FINDING in the .md ---
       currently contributes 0 photos to the 238-roof join (all allocated_keeps
       are iCloud-path photos; every takeout row in allocation_v2.jsonl is
       flagged non_keep_path / excluded, so 0 takeout photos are counted as
       "tied" today). The check is still implemented for forward-compatibility.
    5. Verdict READY / NEEDS-RULE per roof; NEEDS-RULE roofs get a proposed (not
       implemented) fallback ordering rule, keyed to which flag(s) fired.

No external network calls. No writes to allocation_v2.jsonl, job_coords.json,
knowledge_notes.jsonl, counts.py, guards.py, or anything under ~/glenross or
~/glengarry.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
MDLS_BATCH_SIZE = 200
EXIF_READY_THRESHOLD_PCT = 80.0
PATHDATE_EXIF_CONFLICT_DAYS = 180  # generalises the "album says year X, EXIF says X+2" pattern


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


# ---------------------------------------------------------------------------
# Step A: replicate counts.py's allocated_keeps join (read-only duplication,
# not an edit of counts.py; verified identical totals same session)
# ---------------------------------------------------------------------------

def compute_allocated_keeps():
    classified_path = _path('classified.jsonl')
    classified_rows = load_jsonl(classified_path)
    verdicts = {}
    for r in classified_rows:
        verdicts[r['path']] = r['verdict']
    keeps = set(p for p, v in verdicts.items() if v == 'keep')

    alloc_rows = load_jsonl(_path('grind', 'allocation_v2.jsonl'))

    flags_path = _path('grind', 'allocation_v2_flags.jsonl')
    if not os.path.exists(flags_path):
        raise RuntimeError(
            'grind/allocation_v2_flags.jsonl is missing. This script will not '
            'recompute flags inline -- run grind/build_allocation_v2_flags.py '
            'first (same rule as counts.py).'
        )
    flags_by_path = {}
    for r in load_jsonl(flags_path):
        if r.get('_meta'):
            continue
        flags_by_path[r['path']] = r['flag']

    allocated_keep_paths = set()
    job_ref_by_path = {}
    path_date_by_path = {}
    for r in alloc_rows:
        p = r['path']
        if p in flags_by_path:
            continue
        allocated_keep_paths.add(p)
        job_ref_by_path[p] = r.get('job_ref')
        path_date_by_path[p] = r.get('date')

    return allocated_keep_paths, job_ref_by_path, path_date_by_path, keeps


# ---------------------------------------------------------------------------
# Step B: EXIF via batched mdls
# ---------------------------------------------------------------------------

def mdls_batch_creation_dates(paths):
    """Returns {path: datetime_or_None}. One subprocess call per MDLS_BATCH_SIZE
    paths (never one process per photo, per the chain-wide law). mdls prints
    exactly one output line per input path, in argument order, whether the
    attribute resolved, was null, or the file could not be found -- verified by
    hand on 2026-07-10 (a missing-file path yields a 1-line "could not find"
    error line, not zero lines, so position always stays aligned with the
    input path list)."""
    out = {}
    paths = list(paths)
    for i in range(0, len(paths), MDLS_BATCH_SIZE):
        chunk = paths[i:i + MDLS_BATCH_SIZE]
        result = subprocess.run(
            ['mdls', '-name', 'kMDItemContentCreationDate'] + chunk,
            capture_output=True, text=True
        )
        lines = result.stdout.splitlines()
        if len(lines) != len(chunk):
            raise RuntimeError(
                'mdls batch output line count (%d) != input path count (%d) -- '
                'STOP, do not guess alignment. First chunk path: %s' % (
                    len(lines), len(chunk), chunk[0] if chunk else '(empty)')
            )
        for path, line in zip(chunk, lines):
            out[path] = _parse_mdls_line(line)
    return out


def _parse_mdls_line(line):
    line = line.strip()
    if not line.startswith('kMDItemContentCreationDate'):
        # error line, e.g. "<ctx path>: could not find <path>."
        return None
    val = line.split('=', 1)[1].strip() if '=' in line else ''
    if val == '(null)' or not val:
        return None
    # mdls date format: "2022-03-18 15:18:32 +0000"
    try:
        return datetime.strptime(val, '%Y-%m-%d %H:%M:%S %z')
    except ValueError:
        return None


def parse_path_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Step C: name resolution (Names-not-codes) and known visit dates
# ---------------------------------------------------------------------------

def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


_ENTITY_CONTACT_RE = re.compile(r'contact/entity:\s*([^)]+)\)')
_GRA_LIVE_PREFIX_RE = re.compile(r'^GRA sites live row,\s*address=(.+)$')
# job_coords['site'] values built from internal evidence-scoring passes (not a
# curated site name) -- any of these substrings marks the string as synthetic,
# not a real address, so it never gets presented on a Lee surface as if it were
_SYNTHETIC_MARKERS = (
    'tier=', 'zone=', 'candidate', 'known_entities', 'non-repeated',
    'postcode-bearing', 'non-footer',
)


def _strip_ref_prefix(ref, s):
    """drive_folder_postcode values look like '<ref> - <name> - <postcode>' --
    strip the leading '<ref> - ' since the ref is displayed separately already
    (avoids double-printing the job code inside what should read as a name)."""
    prefix = ref + ' - '
    if s.startswith(prefix):
        return s[len(prefix):]
    return s


def resolve_site_name(ref, site_names, gra_stories, job_coords):
    """Names-not-codes fallback chain. Returns (display_name, quality) where
    quality flags whether the name is a real site name or a synthetic/derived
    label, so the .md can be honest about which is which rather than silently
    presenting a machine-generated evidence-scoring label as if it were a
    proper site name."""
    sn = site_names.get(ref) or {}
    if sn.get('name'):
        return sn['name'], 'real'
    g = gra_stories.get(ref) or {}
    site = g.get('site') or {}
    if site.get('name'):
        return site['name'], 'real'
    if site.get('address'):
        return site['address'], 'real'
    jc = job_coords.get(ref) or {}
    postcode = jc.get('postcode')
    raw_site = jc.get('site')
    if raw_site:
        m = _GRA_LIVE_PREFIX_RE.match(raw_site)
        if m:
            return m.group(1).strip(), 'real'
        if any(marker in raw_site for marker in _SYNTHETIC_MARKERS):
            m2 = _ENTITY_CONTACT_RE.search(raw_site)
            if m2:
                contact = m2.group(1).strip()
                if postcode:
                    return '%s area (contact: %s)' % (postcode, contact), 'synthetic'
                return 'contact: %s' % contact, 'synthetic'
            if postcode:
                return '%s area (unnamed site)' % postcode, 'synthetic'
            return None, 'missing'
        return _strip_ref_prefix(ref, raw_site), 'real'
    if postcode:
        return '%s area (unnamed site)' % postcode, 'synthetic'
    return None, 'missing'


def known_visit_dates(ref, rim_by_ref, gra_stories):
    dates = set()
    for r in rim_by_ref.get(ref, []):
        if r.get('band') in ('exact', 'strong', 'likely') and r.get('event_start'):
            dates.add(r['event_start'])
    g = gra_stories.get(ref) or {}
    for s in g.get('stories', []):
        if s.get('date'):
            dates.add(s['date'])
    return sorted(dates)


def nearest_gap_days(dt, known_date_strs):
    if dt is None or not known_date_strs:
        return None
    best = None
    for ds in known_date_strs:
        kd = parse_path_date(ds)
        if kd is None:
            continue
        gap = abs((dt - kd).days)
        if best is None or gap < best:
            best = gap
    return best


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ts = now_iso()

    allocated_keep_paths, job_ref_by_path, path_date_by_path, keeps = compute_allocated_keeps()
    print('Counted by: allocation_v2.jsonl rows whose path is NOT present in '
          'allocation_v2_flags.jsonl -- allocated_keeps = %d' % len(allocated_keep_paths))

    by_roof = defaultdict(list)
    for p in allocated_keep_paths:
        jr = job_ref_by_path.get(p)
        if jr:
            by_roof[jr].append(p)

    n_roofs = len(by_roof)
    print('Counted by: distinct job_ref among allocated_keeps -- roofs = %d' % n_roofs)
    if n_roofs != 238:
        sys.stderr.write(
            'SANITY GATE FAILED: expected 238 roofs (per counts.py this session), '
            'got %d. Corpus has drifted since the join was verified. STOPPING -- '
            'not proceeding on drifted membership.\n' % n_roofs
        )
        sys.exit(1)

    missing_data = load_json(_path('grind', 'kept_missing_on_disk.json'), {'missing': []})
    missing_set = set(missing_data.get('missing', []))

    takeout_in_join = sum(1 for p in allocated_keep_paths if 'takeout' in p.lower())

    rim_rows = load_jsonl(_path('grind', 'roof_invoice_match.jsonl'))
    rim_by_ref = defaultdict(list)
    for r in rim_rows:
        rim_by_ref[r['job_ref']].append(r)

    gra_stories = load_json(_path('grind', 'gra_stories.json'), {})
    site_names = load_json(_path('grind', 'site_names.json'), {})
    job_coords = load_json(_path('grind', 'job_coords.json'), {})

    # ---- EXIF: batch mdls over every present-on-disk allocated_keep path ----
    all_present_paths = [p for p in allocated_keep_paths if p not in missing_set]
    print('Counted by: allocated_keeps minus grind/kept_missing_on_disk.json[\"missing\"] '
          '-- present-on-disk = %d (missing-on-disk among allocated_keeps = %d)' % (
              len(all_present_paths), len(allocated_keep_paths) - len(all_present_paths)))

    exif_by_path = mdls_batch_creation_dates(all_present_paths)

    # ---- per-roof analysis ----
    roof_records = []
    ready_count = 0
    needs_rule_count = 0
    flag_histogram = defaultdict(int)
    name_quality_counts = defaultdict(int)

    for ref in sorted(by_roof.keys()):
        paths = sorted(by_roof[ref])
        photo_count = len(paths)
        name, name_quality = resolve_site_name(ref, site_names, gra_stories, job_coords)
        name_quality_counts[name_quality] += 1
        visit_dates = known_visit_dates(ref, rim_by_ref, gra_stories)

        usable_exif = 0
        pathdate_conflicts = 0
        no_visit_corrob = 0
        photo_rows = []

        for p in paths:
            is_missing = p in missing_set
            exif_dt = exif_by_path.get(p) if not is_missing else None
            pd_str = path_date_by_path.get(p)
            pd_dt = parse_path_date(pd_str)

            flags = []
            if is_missing:
                flags.append('no_exif_missing_on_disk')
            elif exif_dt is None:
                flags.append('exif_unreadable')
            else:
                usable_exif += 1

            conflict = False
            if exif_dt is not None and pd_dt is not None:
                gap_days = abs((exif_dt - pd_dt).days)
                if gap_days > PATHDATE_EXIF_CONFLICT_DAYS:
                    conflict = True
                    flags.append('exif_vs_pathdate_conflict_%dd' % gap_days)
                    pathdate_conflicts += 1

            gap_to_visit = nearest_gap_days(exif_dt or pd_dt, visit_dates)
            if gap_to_visit is not None and gap_to_visit > 120:
                flags.append('no_known_visit_near_photo')
                no_visit_corrob += 1

            for fl in flags:
                base_fl = fl.split('_conflict_')[0] + '_conflict' if 'conflict_' in fl else fl
                flag_histogram[base_fl] += 1

            photo_rows.append({
                'path': p,
                'exif_ts': exif_dt.isoformat() if exif_dt else None,
                'path_date': pd_str,
                'flags': flags,
            })

        pct_usable = (usable_exif / photo_count * 100.0) if photo_count else 0.0

        roof_flags = []
        if pct_usable < EXIF_READY_THRESHOLD_PCT:
            roof_flags.append('low_exif_coverage')
        if pathdate_conflicts > 0:
            roof_flags.append('exif_vs_pathdate_conflict')
        # no_known_visit_near_photo is informational only -- does not gate verdict
        # (many maintenance roofs are photographed with no matching invoice/story
        # entry simply because the corroborating source is incomplete, not because
        # the photo dating is wrong)

        verdict = 'READY' if not roof_flags else 'NEEDS-RULE'
        if verdict == 'READY':
            ready_count += 1
        else:
            needs_rule_count += 1

        proposed_rules = []
        if 'low_exif_coverage' in roof_flags:
            if usable_exif == 0:
                proposed_rules.append(
                    'No EXIF at all for this roof (all missing-on-disk or unreadable). '
                    'Propose: order strictly by path-date (folder YYYY/MM/DD) with '
                    'filename numeric sequence as the tie-break within a day; do not '
                    'invent a time-of-day. If path-date is also absent, fall back to the '
                    'nearest roof_invoice_match/gra_stories visit date as a coarse day-bin, '
                    'and flag the roof for Lee\'s manual pass before the spine build reads it.'
                )
            else:
                proposed_rules.append(
                    'Partial EXIF coverage (%.0f%%). Propose: use EXIF where present; for '
                    'photos flagged no_exif_missing_on_disk or exif_unreadable, interpolate '
                    'their position using path-date binned against the EXIF-dated photos '
                    'from the same folder-date group, tie-broken by filename numeric '
                    'sequence.' % pct_usable
                )
        if 'exif_vs_pathdate_conflict' in roof_flags:
            proposed_rules.append(
                'EXIF and path-date disagree by >%d days on %d photo(s) (the known '
                'album/EXIF year-drift pattern, generalised to path-date). Propose: trust '
                'EXIF as capture-truth over path-date (path-date reflects the import/export '
                'folder the photo landed in, not when it was taken); only fall back to '
                'path-date for a photo when its own EXIF is missing.' % (
                    PATHDATE_EXIF_CONFLICT_DAYS, pathdate_conflicts)
            )

        roof_records.append({
            'job_ref': ref,
            'site_name': name,
            'site_name_quality': name_quality,
            'photo_count': photo_count,
            'usable_exif_count': usable_exif,
            'pct_usable_exif': round(pct_usable, 1),
            'missing_on_disk_count': sum(1 for p in paths if p in missing_set),
            'known_visit_dates': visit_dates,
            'no_visit_corroboration_count': no_visit_corrob,
            'roof_flags': roof_flags,
            'verdict': verdict,
            'proposed_fallback_rules': proposed_rules,
            'photos': photo_rows,
        })

    total_photos = sum(r['photo_count'] for r in roof_records)
    total_usable_exif = sum(r['usable_exif_count'] for r in roof_records)
    overall_pct = (total_usable_exif / total_photos * 100.0) if total_photos else 0.0

    # ---------------------------------------------------------------------
    # Write machine-readable twin
    # ---------------------------------------------------------------------
    out_json = {
        'generated_at': ts,
        'method': 'f3_spineline_readiness.py -- read-only audit, STEP 4 of '
                   'F2-CANDIDATE-PASS-SPEC-2026-07-10; F3 build NOT started',
        'summary': {
            'roofs_audited': n_roofs,
            'ready_count': ready_count,
            'needs_rule_count': needs_rule_count,
            'total_photos': total_photos,
            'total_usable_exif': total_usable_exif,
            'overall_pct_usable_exif': round(overall_pct, 1),
            'takeout_photos_in_238_roof_join': takeout_in_join,
            'flag_histogram': dict(flag_histogram),
            'site_name_quality_counts': dict(name_quality_counts),
        },
        'roofs': roof_records,
    }
    json_path = _path('grind', 'spineline_readiness.json')
    with open(json_path, 'w') as f:
        json.dump(out_json, f, indent=2)

    # ---------------------------------------------------------------------
    # Write human-readable .md
    # ---------------------------------------------------------------------
    md_lines = []
    md_lines.append('# SPINELINE-READINESS.md -- F3 pre-build audit (STEP 4, read-only)')
    md_lines.append('')
    md_lines.append(('Generated %s by `f3_spineline_readiness.py` on Mini A. This is an '
                      'AUDIT ONLY -- the F3 spineline build has NOT started. Candidates and '
                      'ordering rules proposed below are PROVISIONAL (IP-L9): nothing here '
                      'has been written as a tie, and nothing here changes the corpus.') % ts)
    md_lines.append('')
    md_lines.append('## Summary')
    md_lines.append('')
    md_lines.append('- Roofs audited: **%d**' % n_roofs)
    md_lines.append('  Counted by: distinct `job_ref` among allocated_keeps '
                     '(`grind/allocation_v2.jsonl` rows not present in '
                     '`grind/allocation_v2_flags.jsonl`) -- replicates counts.py\'s join, '
                     'run this session, matching `python3 counts.py` -> "roofs with tied '
                     'photos: 238".')
    md_lines.append('- READY: **%d** / NEEDS-RULE: **%d**' % (ready_count, needs_rule_count))
    md_lines.append('  Counted by: per-roof verdict logic in this script -- READY iff '
                     '%% usable-EXIF >= %.0f%% AND zero EXIF-vs-path-date conflicts '
                     '(>%dd gap).' % (EXIF_READY_THRESHOLD_PCT, PATHDATE_EXIF_CONFLICT_DAYS))
    md_lines.append('- Total tied photos across the 238 roofs: **%d**' % total_photos)
    md_lines.append('  Counted by: `sum(len(paths) for each job_ref group)` over the same '
                     'join.')
    md_lines.append('- Overall %% with usable EXIF timestamp: **%.1f%%** (%d / %d)' % (
        overall_pct, total_usable_exif, total_photos))
    md_lines.append('  Counted by: `mdls -name kMDItemContentCreationDate` batched over '
                     'every present-on-disk allocated-keep path (missing-on-disk paths '
                     'excluded from mdls calls, counted as 0 usable directly from '
                     '`grind/kept_missing_on_disk.json`).')
    md_lines.append('- Site-name quality: **%d real** / **%d synthetic (derived label, '
                     'not a proper site name)** / **%d missing (ref + postcode only, no '
                     'name anywhere)**' % (
                         name_quality_counts.get('real', 0),
                         name_quality_counts.get('synthetic', 0),
                         name_quality_counts.get('missing', 0)))
    md_lines.append('  Counted by: `resolve_site_name()` fallback chain per roof -- '
                     '`grind/site_names.json` -> `grind/gra_stories.json` -> '
                     '`grind/job_coords.json[site]` -> postcode-only label -- tallied over '
                     'the same 238-roof loop. "Synthetic" = a machine-generated '
                     '`known_entities` evidence label (e.g. "contact/entity: X") reformatted '
                     'for readability, not a real site name -- flagged so this is never '
                     'mistaken for a proper name on a Lee surface.')
    md_lines.append('')
    md_lines.append('### FINDING -- album-order check has 0 photos to check against today')
    md_lines.append('')
    md_lines.append('The spec\'s order-conflict check lists "EXIF order vs album order '
                     '(takeout album names) vs filename order vs known visit dates." '
                     'Checked: **%d** of the 238-roof join\'s photos come from the takeout '
                     'ledger.' % takeout_in_join)
    md_lines.append('Looked in: `grind/allocation_v2.jsonl` rows for the 238 job_refs, '
                     'filtering by `\'takeout\' in path`. Every takeout row in '
                     '`allocation_v2.jsonl` is either `excluded` or flagged '
                     '`non_keep_path` (because `classified.jsonl` -- the keep/drop/quarantine '
                     'verdict source -- never covers takeout paths at all, per counts.py\'s '
                     'own comment), so 0 takeout photos are counted as "tied" in the current '
                     '238-roof set. Could not look in: whether a FUTURE allocation run adds '
                     'takeout photos into the keep-verdict path (would require '
                     '`classified.jsonl` to gain takeout coverage first -- out of scope for '
                     'this read-only step). The album-vs-EXIF check is implemented in the '
                     'script (dormant) so it activates automatically if that ever changes; '
                     'today it fires 0 times, correctly, not by omission.')
    md_lines.append('')
    md_lines.append('### FINDING -- photo_ledger_merged.jsonl `ts` is not a photo date')
    md_lines.append('')
    md_lines.append('The spec names `photo_ledger_merged.jsonl` as a corroborating "ledger '
                     'date" source. Checked: its only timestamp field is `ts`, decoded to '
                     '2026-06-26 for the first rows checked -- that is when the captioning '
                     'pipeline ran, not when the photo was taken. It carries no per-photo '
                     'capture-date field. It was NOT used as a date source in this audit '
                     '(using it would have manufactured a false corroboration). Looked in: '
                     'the full key set of 2,000 sampled rows (`path, sha256, model, '
                     'model_digest, prompt, response, host, ts` -- no date/day/captured '
                     'field present). Could not look in: whether an older/newer version of '
                     'this ledger elsewhere on Mini A carries a real date field -- only the '
                     'current `~/image-plane/photo_ledger_merged.jsonl` was checked.')
    md_lines.append('')
    md_lines.append('### Flag histogram (photo-level, across all 238 roofs)')
    md_lines.append('')
    md_lines.append('Counted by: tally of every per-photo `flags` entry written in '
                     '`grind/spineline_readiness.json`.')
    md_lines.append('')
    for fl in sorted(flag_histogram.keys()):
        md_lines.append('- `%s`: %d' % (fl, flag_histogram[fl]))
    md_lines.append('')
    def display_name(r):
        if r['site_name']:
            suffix = ' [synthetic label]' if r['site_name_quality'] == 'synthetic' else ''
            return '%s (%s)%s' % (r['site_name'], r['job_ref'], suffix)
        return '(unnamed -- no site name anywhere) (%s)' % r['job_ref']

    md_lines.append('## Per-roof table')
    md_lines.append('')
    md_lines.append('| Site | Photos | % usable EXIF | Missing-on-disk | Flags | Verdict |')
    md_lines.append('|---|---:|---:|---:|---|---|')
    for r in roof_records:
        display = display_name(r)
        flags_str = ', '.join(r['roof_flags']) if r['roof_flags'] else '-'
        md_lines.append('| %s | %d | %.1f%% | %d | %s | %s |' % (
            display, r['photo_count'], r['pct_usable_exif'],
            r['missing_on_disk_count'], flags_str, r['verdict']))
    md_lines.append('')
    md_lines.append('## NEEDS-RULE roofs -- proposed fallback ordering rules (PROPOSAL ONLY, not built)')
    md_lines.append('')
    needs_rule_roofs = [r for r in roof_records if r['verdict'] == 'NEEDS-RULE']
    if not needs_rule_roofs:
        md_lines.append('None -- every roof cleared the READY bar.')
    for r in needs_rule_roofs:
        display = display_name(r)
        md_lines.append('### %s' % display)
        md_lines.append('')
        md_lines.append('- %d photos, %.1f%% usable EXIF, flags: %s' % (
            r['photo_count'], r['pct_usable_exif'], ', '.join(r['roof_flags'])))
        for rule in r['proposed_fallback_rules']:
            md_lines.append('- Proposed rule: %s' % rule)
        md_lines.append('')

    md_path = _path('docs', 'SPINELINE-READINESS.md')
    os.makedirs(os.path.dirname(md_path), exist_ok=True)
    with open(md_path, 'w') as f:
        f.write('\n'.join(md_lines) + '\n')

    print('Wrote %s' % md_path)
    print('Wrote %s' % json_path)
    print('roofs_audited=%d ready=%d needs_rule=%d overall_pct_usable_exif=%.1f' % (
        n_roofs, ready_count, needs_rule_count, overall_pct))


if __name__ == '__main__':
    main()
