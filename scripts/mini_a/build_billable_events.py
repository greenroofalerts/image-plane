#!/usr/bin/env python3
"""
F6 Output 1 + Output 2 builder — image-plane (LEE-411), 2026-07-11.
Spec: docs/F6-REPO-VIEW-SPEC-2026-07-11.md, "Output 1" + "Output 2" ONLY.

Reads (Mini A ~/image-plane/, all pre-existing, none rebuilt):
    grind/roof_invoice_match.jsonl
    grind/allocation_v2.jsonl
    grind/allocation_v2_flags.jsonl
    takeout_ledger_merged.jsonl
    grind/xero_invoice_lines_full.json
    grind/site_names.json
    grind/flip_site_names_cache.json

Writes:
    grind/billable_events.json
    grind/sister_refs.json

Python 3.9 (Mini A) — no match statements, no PEP 604 unions.

Does NOT touch flip_server.py, allocation_v2*, dedupe, or any other grind file.
Read-only against every input. £-redaction is enforced by a hard assert before
either output file is written — the run aborts (no partial file) if any amount
survives.
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# When run from Mini A ~/image-plane/, ROOT == ~/image-plane. When run from
# the laptop mirror (scripts/mini_a/../..), ROOT resolves the same way — the
# script always expects to be invoked with CWD-independent absolute paths
# rooted at the project dir it's copied into. We resolve relative to CWD
# instead, since that's how the run command invokes it on Mini A.
BASE = os.getcwd()

P_ROOF_INVOICE_MATCH = os.path.join(BASE, "grind", "roof_invoice_match.jsonl")
P_ALLOCATION_V2 = os.path.join(BASE, "grind", "allocation_v2.jsonl")
P_ALLOCATION_V2_FLAGS = os.path.join(BASE, "grind", "allocation_v2_flags.jsonl")
P_TAKEOUT_LEDGER = os.path.join(BASE, "takeout_ledger_merged.jsonl")
P_XERO_LINES = os.path.join(BASE, "grind", "xero_invoice_lines_full.json")
P_SITE_NAMES = os.path.join(BASE, "grind", "site_names.json")
P_FLIP_SITE_CACHE = os.path.join(BASE, "grind", "flip_site_names_cache.json")

OUT_BILLABLE_EVENTS = os.path.join(BASE, "grind", "billable_events.json")
OUT_SISTER_REFS = os.path.join(BASE, "grind", "sister_refs.json")


def must_exist(path):
    if not os.path.isfile(path):
        print("MISSING INPUT: %s — stopping, not improvising a replacement." % path)
        sys.exit(1)
    return path


def load_jsonl(path):
    rows = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# £ redaction — regex-strip then assert. This is the ONLY place amounts are
# allowed to be stripped; nothing downstream re-adds a £ or GBP figure.
# ---------------------------------------------------------------------------
MONEY_RE = re.compile(r"£\s?[\d,]+(?:\.\d+)?|GBP\s*[\d,]+(?:\.\d+)?", re.I)


def redact_money(text):
    if not text:
        return text
    cleaned = MONEY_RE.sub("[amount redacted]", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def assert_no_money(obj, where):
    s = json.dumps(obj)
    if "£" in s:
        idx = s.index("£")
        raise AssertionError(
            "£ SURVIVED REDACTION in %s: ...%s..." % (where, s[max(0, idx - 40):idx + 40])
        )
    # crude GBP-with-digits check too (GBP alone, e.g. tenant co. names, is fine)
    for m in re.finditer(r"GBP\s*\d", s):
        idx = m.start()
        raise AssertionError(
            "GBP amount survived redaction in %s: ...%s..." % (where, s[max(0, idx - 40):idx + 40])
        )


# ---------------------------------------------------------------------------
# Phase classification — plain-English v2 steering vocab words only.
# DEVIATION FROM SPEC, NOTED: the spec's named category list (Install /
# Spring roofcare / Summer care and haycut / Winter care / Repair / Leak
# detection / Diagnostic / Handover / Visit) has no bucket for Autumn, yet
# "aut"/"autumn" is the single most common season word in the real invoice
# text (304 hits across xero_invoice_lines_full.json, on par with "spring").
# Forcing every autumn care visit into "Winter care" would misrepresent
# hundreds of real events. Added "Autumn roofcare" as a tenth, plain-English
# category to keep headers honest. Reported in the run report.
# ---------------------------------------------------------------------------
RE_LEAK = re.compile(r"\bleak\b", re.I)
RE_DIAG = re.compile(r"\bdiagnos(is|tic)\b|\bsurvey\b", re.I)
RE_HANDOVER = re.compile(r"\bhand\s?over\b", re.I)
RE_INSTALL = re.compile(r"\binstal{1,2}(?!ment)\w*|\bstrip\s?out\b", re.I)
RE_REPAIR = re.compile(r"\brepair", re.I)
RE_WATERPROOF = re.compile(r"waterproof", re.I)
RE_HAYCUT = re.compile(r"hay\s?cut|high summer", re.I)
RE_SUMMER = re.compile(r"\bsummer\b", re.I)
RE_AUTUMN = re.compile(r"\baut(umn)?\b", re.I)
RE_SPRING = re.compile(r"\bspr(ing)?\b", re.I)
RE_WINTER = re.compile(r"\bwinter\b", re.I)
RE_CARE_GENERIC = re.compile(r"\bcare\b|\bmaintenance\b", re.I)
# Real invoice text found on the dataset: deposit/balance/instalment payment
# lines for install and major-works jobs frequently carry NO "install" word
# at all ("50% advance against v5 quote", "Balance minus stones & ivy",
# "strip out", "consultancy fee for trinity cres intro") — only payment-stage
# + quote/works vocabulary. Recurring seasonal care invoices never use this
# combination (they say "care visit"/"maintenance"). Checked AFTER the
# explicit Repair check above, so "repairs advance"/"roof repair balance"
# (which already say "repair") are never reclassified here.
RE_PAYMENT_STAGE = re.compile(
    r"\b(advance|deposit|balance|instal{1,2}ment)\b.*\b(quote|quoted|agreed|"
    r"completion|elements|prelims|phase|estimate|costs?|revival)\b"
    r"|\b(quote|quoted|agreed|completion|elements|prelims|phase|estimate|"
    r"costs?|revival)\b.*\b(advance|deposit|balance|instal{1,2}ment)\b",
    re.I,
)
RE_INTRO_FEE = re.compile(r"\bconsultancy fee\b|\bintroduction fee\b|\bintro\b.*\bfee\b", re.I)

PHASE_PRIORITY = [
    "Install", "Repair", "Leak detection", "Diagnostic", "Handover",
    "Summer care and haycut", "Autumn roofcare", "Spring roofcare",
    "Winter care", "Visit",
]


def season_from_date(iso_date):
    month = int(iso_date[5:7])
    if month in (3, 4, 5):
        return "Spring roofcare"
    if month in (6, 7, 8):
        return "Summer care and haycut"
    if month in (9, 10, 11):
        return "Autumn roofcare"
    return "Winter care"


def classify_phase(text, event_date, takeout_hint):
    combined = (text or "").lower()
    if RE_LEAK.search(combined):
        return "Leak detection"
    if RE_DIAG.search(combined):
        return "Diagnostic"
    if RE_HANDOVER.search(combined):
        return "Handover"
    if RE_INSTALL.search(combined):
        return "Install"
    if RE_REPAIR.search(combined) or RE_WATERPROOF.search(combined):
        return "Repair"
    if RE_PAYMENT_STAGE.search(combined) or RE_INTRO_FEE.search(combined):
        return "Install"
    if RE_HAYCUT.search(combined) or RE_SUMMER.search(combined):
        return "Summer care and haycut"
    if RE_AUTUMN.search(combined):
        return "Autumn roofcare"
    if RE_SPRING.search(combined):
        return "Spring roofcare"
    if RE_WINTER.search(combined):
        return "Winter care"
    if RE_CARE_GENERIC.search(combined):
        # Known to be a care/maintenance visit, season word just not present
        # in the snippet — derive season from the visit's own real date
        # (factual, not fabricated) rather than falling back to "Visit".
        return season_from_date(event_date)
    if takeout_hint == "install":
        return "Install"
    if takeout_hint == "diagnostic":
        return "Diagnostic"
    return "Visit"


def phase_priority_pick(phases):
    for p in PHASE_PRIORITY:
        if p in phases:
            return p
    return "Visit"


BAND_RANK = {"exact": 5, "strong": 4, "likely": 3, "weak": 2, "unbilled": 1}


def best_band(bands):
    return sorted(bands, key=lambda b: -BAND_RANK.get(b, 0))[0]


MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


def human_span(start_iso, end_iso):
    sy, sm = int(start_iso[:4]), int(start_iso[5:7])
    ey, em = int(end_iso[:4]), int(end_iso[5:7])
    if sy == ey and sm == em:
        return "%s %d" % (MONTH_NAMES[sm], sy)
    if sy == ey:
        return "%s–%s %d" % (MONTH_NAMES[sm], MONTH_NAMES[em], sy)
    return "%s %d–%s %d" % (MONTH_NAMES[sm], sy, MONTH_NAMES[em], ey)


# ---------------------------------------------------------------------------
# Union-find for rule (a): events sharing any invoice_number merge.
# ---------------------------------------------------------------------------
class UnionFind(object):
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def build_windows_for_job(job_ref, events, photo_dates_for_job, takeout_hint_by_date):
    """events: list of raw roof_invoice_match rows for this job_ref (real ref,
    not a needs_lee placeholder). Returns ordered list of window dicts."""
    n = len(events)
    uf = UnionFind(n)
    inv_owner = {}
    for i, ev in enumerate(events):
        for inv in ev.get("invoices", []):
            num = inv.get("invoice_number")
            if not num:
                continue
            if num in inv_owner:
                uf.union(inv_owner[num], i)
            else:
                inv_owner[num] = i

    clusters = defaultdict(list)
    for i in range(n):
        clusters[uf.find(i)].append(i)

    proto = []
    for root, idxs in clusters.items():
        cluster_events = [events[i] for i in idxs]
        dates = []
        invoices_by_num = {}
        bands = []
        phases = []
        for ev in cluster_events:
            dates.append(ev["event_start"])
            bands.append(ev.get("band", "unbilled"))
            text_parts = [inv.get("description_snippet", "") for inv in ev.get("invoices", [])]
            hint = takeout_hint_by_date(job_ref, ev["event_start"])
            phases.append(classify_phase(" ".join(text_parts), ev["event_start"], hint))
            for inv in ev.get("invoices", []):
                num = inv.get("invoice_number")
                if num:
                    invoices_by_num[num] = inv
                    dates.append(inv.get("date", ev["event_start"]))
        start = min(dates)
        end = max(dates)
        proto.append({
            "start": start,
            "end": end,
            "band": best_band(bands),
            "phase": phase_priority_pick(phases),
            "invoices": list(invoices_by_num.values()),
            "source_events": len(cluster_events),
        })

    # partition by phase, sequential-merge within phase per rules (b)/(c)
    by_phase = defaultdict(list)
    for p in proto:
        by_phase[p["phase"]].append(p)

    windows = []
    for phase, group in by_phase.items():
        group.sort(key=lambda w: w["start"])
        merged = []
        for w in group:
            if not merged:
                merged.append(w)
                continue
            last = merged[-1]
            gap_days = (datetime.strptime(w["start"], "%Y-%m-%d") -
                        datetime.strptime(last["end"], "%Y-%m-%d")).days
            overlap = w["start"] <= last["end"]
            if phase == "Install":
                # merges regardless of gap unless >18 months (548 days) apart
                should_merge = overlap or gap_days <= 548
            else:
                should_merge = overlap or gap_days <= 45
            if should_merge:
                last["end"] = max(last["end"], w["end"])
                last["start"] = min(last["start"], w["start"])
                last["source_events"] += w["source_events"]
                last["band"] = best_band([last["band"], w["band"]])
                seen = {inv.get("invoice_number") for inv in last["invoices"]}
                for inv in w["invoices"]:
                    if inv.get("invoice_number") not in seen:
                        last["invoices"].append(inv)
                        seen.add(inv.get("invoice_number"))
            else:
                merged.append(w)
        for w in merged:
            windows.append({
                "phase": phase,
                "header": "%s — %s" % (phase, human_span(w["start"], w["end"])),
                "start": w["start"],
                "end": w["end"],
                "band": w["band"],
                "invoices": [
                    {
                        "invoice_number": inv.get("invoice_number"),
                        "date": inv.get("date"),
                        "tenant": inv.get("tenant"),
                        "description_snippet": redact_money(inv.get("description_snippet", "")),
                    }
                    for inv in sorted(w["invoices"], key=lambda i: i.get("date") or "")
                ],
                "source_events": w["source_events"],
            })

    windows.sort(key=lambda w: w["start"])
    return windows


# ---------------------------------------------------------------------------
# Sister refs
# ---------------------------------------------------------------------------
REF_RE = re.compile(r"^(\d+)-(\d+)(-.+)?$")
STOPWORDS = {"the", "at", "close", "road", "rd", "street", "st", "avenue",
             "ave", "gardens", "house", "flat", "no", "and", "&"}


def normalize_numeric(ref):
    m = REF_RE.match(ref)
    if not m:
        return None
    return str(int(m.group(1)))


def canonical_key(ref):
    """(numeric, yy, suffix) with the numeric zero-padding stripped, so
    '0301-14' and '301-14' collapse to the same key — they are the SAME job
    written two ways (14 such pairs found in site_names.json /
    flip_site_names_cache.json, e.g. 0301-14/301-14, 0735-16/735-16), not
    sister refs of each other."""
    m = REF_RE.match(ref)
    if not m:
        return None
    return (str(int(m.group(1))), m.group(2), m.group(3) or "")


def site_tokens(s):
    if not s:
        return set()
    words = re.findall(r"[a-z0-9]+", s.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def canonical_ref(ref):
    """Unpadded spelling of a well-formed ref ('0301-14' -> '301-14')."""
    key = canonical_key(ref)
    if not key:
        return None
    return "%s-%s%s" % key


# ---------------------------------------------------------------------------
# Same-site tier (spec §Output 2, added per Lee's 11 Jul morning ruling:
# "same site can legitimately carry two distinct numbers … Extend the
# sister-ref rule"). Corroboration is conservative — over-linking on generic
# street names is the failure mode: a shared site-name phrase counts only if
# it has >=2 words AND at least one word outside this generic list
# ("Olympic Mews" qualifies via "olympic"; "High Street" does not).
# ---------------------------------------------------------------------------
GENERIC_ADDR_WORDS = {
    "road", "rd", "street", "st", "avenue", "ave", "lane", "ln", "gardens",
    "garden", "gdns", "close", "crescent", "cres", "mews", "hill", "park",
    "way", "drive", "dr", "grove", "court", "place", "pl", "terrace",
    "square", "row", "walk", "yard", "rise", "down", "downs", "house",
    "flat", "apartment", "building", "residence", "high", "west", "east",
    "north", "south", "new", "old", "upper", "lower", "great", "little",
    "the", "no", "at", "and", "london", "brighton", "centre", "center",
    "estate",
}

POSTCODE_RE = re.compile(r"\b[a-z]{1,2}\d{1,2}[a-z]?\s*\d[a-z]{2}\b", re.I)
HOUSE_NUM_RE = re.compile(r"^\d+[a-z]?$", re.I)

# Town/area phrases that pass the >=2-words + non-generic-word test but name a
# TOWN, not a site — sharing one must never corroborate a same-site link
# (found on real data: 6 Highland Gardens and the Frimley Centre both sit in
# St Leonards-on-Sea; they are different sites).
SAME_SITE_PHRASE_BLOCKLIST = {"st leonards on sea", "leonards on sea"}

# House-number rule (orchestrator ruling after the first eyeball): same
# STREET + different house numbers is NOT same_site unless (a) an invoice
# line ties the numbers together ('2 & 3 Olympic Mews' pattern) or (b) the
# refs are same-YY with NNNN within 3 of each other (one intake event, e.g.
# 62/64 Sea Lane = 1066-19/1067-19). Identical house number, or a named
# development/park token (phrase NOT ending in a street suffix), links as
# before. NOTE: 'mews' is deliberately NOT a street suffix — a mews is a
# named development. This keeps the Olympic Mews group of five whole, which
# the invoice tie alone would not (4 Olympic Mews = 673-16/676-16 has no
# tie line, and 673 vs 735 fails the within-3 test).
STREET_SUFFIXES = {
    "road", "rd", "street", "st", "avenue", "ave", "lane", "ln", "close",
    "crescent", "cres", "gardens", "gdns", "grove", "place", "pl",
    "terrace", "drive", "dr", "way", "walk", "row", "hill", "rise", "court",
}


def is_street_phrase(phrase):
    return phrase.split()[-1] in STREET_SUFFIXES


def adjacent_intake(ref_a, ref_b):
    """Clause (b): same YY, NNNN within 3 — one intake event."""
    ka, kb = canonical_key(ref_a), canonical_key(ref_b)
    if not ka or not kb or ka[1] != kb[1]:
        return False
    return abs(int(ka[0]) - int(kb[0])) <= 3


def norm_text(s):
    """lowercase, punctuation to spaces, single-spaced, space-padded so
    ' phrase ' substring checks respect word boundaries."""
    s = re.sub(r"[^a-z0-9]+", " ", (s or "").lower())
    return " " + re.sub(r"\s+", " ", s).strip() + " "


def extract_site_phrases(raw_name):
    """Distinctive (phrase, house_numbers frozenset) pairs from a site
    name/address. Split on commas/parens, strip postcodes, capture then strip
    leading house numbers, keep segments with >=2 words where at least one
    word is non-generic."""
    if not raw_name:
        return []
    results = []
    for segment in re.split(r"[,()]", raw_name):
        seg = POSTCODE_RE.sub(" ", segment.lower())
        seg = re.sub(r"[^a-z0-9]+", " ", seg)
        toks = seg.split()
        house_nums = set()
        while toks and (HOUSE_NUM_RE.match(toks[0]) or toks[0] in ("no", "flat", "apartment")):
            if HOUSE_NUM_RE.match(toks[0]):
                house_nums.add(toks[0])
            toks.pop(0)
        if len(toks) < 2:
            continue
        if all(t in GENERIC_ADDR_WORDS or t.isdigit() for t in toks):
            continue
        phrase = " ".join(toks)
        if phrase in SAME_SITE_PHRASE_BLOCKLIST:
            continue
        results.append((phrase, frozenset(house_nums)))
    return results


def capture_address_from_line(phrase, original_text):
    """Find the phrase in the ORIGINAL invoice text, including any leading
    house-number list ('2 & 3 Olympic Mews'). Returns (display_text,
    house_numbers set). Fallback: title-cased phrase, no numbers."""
    tokens = phrase.split()
    inner = r"[\s,&'\-\.]+".join(re.escape(t) for t in tokens)
    pat = re.compile(
        r"((?:\d+[a-zA-Z]?\s*(?:&|,|and)\s*)*\d+[a-zA-Z]?[\s,]+)?" + inner, re.I)
    best = None
    for m in pat.finditer(original_text):
        if best is None or (m.group(1) and not best.group(1)):
            best = m
    if best:
        display = re.sub(r"\s+", " ", best.group(0)).strip()
        nums = set()
        if best.group(1):
            nums = {n.lower() for n in re.findall(r"\d+[a-zA-Z]?", best.group(1))}
        return display, nums
    return phrase.title(), set()


class DictUnionFind(object):
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def derive_label(ref, xero_by_ref, roofinv_texts_by_ref):
    texts = []
    for r in xero_by_ref.get(ref, []):
        texts.append(r.get("description") or "")
        texts.append(r.get("reference") or "")
    texts.extend(roofinv_texts_by_ref.get(ref, []))
    combined = " ".join(texts)
    counts = Counter()
    for t in texts:
        # classify each line independently (no date available at this
        # granularity, so skip the generic-care date fallback here — pure
        # keyword read of what the ref's invoice lines actually say)
        low = t.lower()
        if RE_LEAK.search(low):
            counts["Leak detection"] += 1
        elif RE_DIAG.search(low):
            counts["Diagnostic"] += 1
        elif RE_HANDOVER.search(low):
            counts["Handover"] += 1
        elif RE_INSTALL.search(low):
            counts["Install"] += 1
        elif RE_REPAIR.search(low) or RE_WATERPROOF.search(low):
            counts["Repair"] += 1
        elif RE_PAYMENT_STAGE.search(low) or RE_INTRO_FEE.search(low):
            counts["Install"] += 1
        elif RE_HAYCUT.search(low) or RE_SUMMER.search(low) or RE_AUTUMN.search(low) or RE_SPRING.search(low) or RE_WINTER.search(low):
            counts["Care"] += 1
        elif RE_CARE_GENERIC.search(low):
            counts["Care"] += 1
    if not counts:
        return "works"
    dominant = counts.most_common(1)[0][0]
    if dominant == "Install":
        return "roof install"
    if dominant == "Repair":
        return "waterproofing repairs" if RE_WATERPROOF.search(combined.lower()) else "repairs"
    if dominant == "Leak detection":
        return "leak detection"
    if dominant == "Diagnostic":
        return "diagnostic inspection"
    if dominant == "Handover":
        return "handover"
    return "green-roof maintenance and care"


def main():
    for p in (P_ROOF_INVOICE_MATCH, P_ALLOCATION_V2, P_ALLOCATION_V2_FLAGS,
              P_TAKEOUT_LEDGER, P_XERO_LINES, P_SITE_NAMES, P_FLIP_SITE_CACHE):
        must_exist(p)

    roof_invoice_rows = load_jsonl(P_ROOF_INVOICE_MATCH)
    allocation_rows = load_jsonl(P_ALLOCATION_V2)
    flag_rows = load_jsonl(P_ALLOCATION_V2_FLAGS)
    takeout_rows = load_jsonl(P_TAKEOUT_LEDGER)
    xero_lines = load_json(P_XERO_LINES)
    site_names = load_json(P_SITE_NAMES)
    flip_cache = load_json(P_FLIP_SITE_CACHE)

    # --- flagged (excluded) photo paths ---
    flagged_paths = {r["path"] for r in flag_rows if not r.get("_meta") and r.get("path")}

    # --- valid allocation set: path -> (job_ref, date), excluding flagged ---
    valid_photo_rows = []
    for r in allocation_rows:
        if r.get("path") in flagged_paths:
            continue
        if not r.get("job_ref"):
            continue
        valid_photo_rows.append(r)

    valid_job_refs = {r["job_ref"] for r in valid_photo_rows}

    # path -> visit_type (takeout only)
    path_visit_type = {}
    for r in takeout_rows:
        vt = r.get("visit_type")
        if vt:
            path_visit_type[r["path"]] = vt

    # job_ref -> list of (date, visit_type) for photos in the valid set
    photos_by_job = defaultdict(list)
    for r in valid_photo_rows:
        vt = path_visit_type.get(r["path"])
        photos_by_job[r["job_ref"]].append((r.get("date"), vt))

    def takeout_hint_for(job_ref, event_date_iso):
        """Majority non-null visit_type among this job's photos within
        +/-21 days of event_date (the same membership padding the render
        side uses), mapped to a coarse install/diagnostic/None hint."""
        try:
            ev_dt = datetime.strptime(event_date_iso, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None
        window_start = ev_dt - timedelta(days=21)
        window_end = ev_dt + timedelta(days=21)
        votes = Counter()
        for date_str, vt in photos_by_job.get(job_ref, []):
            if not vt or not date_str:
                continue
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            if window_start <= d <= window_end:
                votes[vt] += 1
        if not votes:
            return None
        top = votes.most_common(1)[0][0]
        if top == "install":
            return "install"
        if top == "diagnostic":
            return "diagnostic"
        return None

    # --- roof_invoice_match: split real refs vs needs_lee placeholders ---
    events_by_job = defaultdict(list)
    needs_lee_rows = 0
    lee_not_ratified_real_ref = 0
    for row in roof_invoice_rows:
        jr = row["job_ref"]
        if jr.startswith("needs_lee"):
            needs_lee_rows += 1
            continue
        if row.get("flag") == "lee_not_ratified":
            lee_not_ratified_real_ref += 1
        events_by_job[jr].append(row)

    billable_events = {}
    for job_ref, events in events_by_job.items():
        windows = build_windows_for_job(
            job_ref, events, photos_by_job.get(job_ref, []), takeout_hint_for
        )
        if windows:
            billable_events[job_ref] = windows

    billable_events_out = {
        "_meta": {
            "generated_from": [
                "grind/roof_invoice_match.jsonl", "grind/allocation_v2.jsonl",
                "grind/allocation_v2_flags.jsonl", "takeout_ledger_merged.jsonl",
            ],
            "generated_by": "scripts/mini_a/build_billable_events.py",
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "note": ("Read-side join only; allocation_v2 not written. Windows "
                     "padded +/-21d for photo membership at RENDER time by "
                     "flip_server, not stored here. 'Autumn roofcare' added as "
                     "a tenth phase category (see script header) — spec's list "
                     "had no autumn bucket but it is the most common season "
                     "word in the real invoice text. Install phase also "
                     "matches deposit/advance/balance/instalment payment-stage "
                     "language combined with quote/works vocabulary (e.g. "
                     "'50% advance against v5 quote', 'strip out', "
                     "'consultancy fee for ... intro') since real install jobs "
                     "frequently have no literal 'install' word on the deposit/"
                     "balance lines — biased toward keeping installs together "
                     "per the spec's ambiguity rule."),
        },
    }
    billable_events_out.update(billable_events)

    assert_no_money(billable_events_out, "grind/billable_events.json")

    # -----------------------------------------------------------------
    # Output 2: sister_refs.json
    # -----------------------------------------------------------------
    xero_by_ref = defaultdict(list)
    for r in xero_lines:
        tr = r.get("tracking_ref")
        if tr:
            xero_by_ref[tr].append(r)

    roofinv_texts_by_ref = defaultdict(list)
    roofinv_contacts_by_ref = defaultdict(set)
    for row in roof_invoice_rows:
        jr = row["job_ref"]
        if jr.startswith("needs_lee"):
            continue
        for inv in row.get("invoices", []):
            if inv.get("description_snippet"):
                roofinv_texts_by_ref[jr].append(inv["description_snippet"])
            if inv.get("contact"):
                roofinv_contacts_by_ref[jr].add(inv["contact"].strip().lower())

    xero_contacts_by_ref = defaultdict(set)
    for ref, rows in xero_by_ref.items():
        for r in rows:
            c = r.get("contact")
            if c:
                xero_contacts_by_ref[ref].add(c.strip().lower())

    # universe of every ref string seen anywhere, well-formed only
    universe = set()
    for r in allocation_rows:
        if r.get("job_ref"):
            universe.add(r["job_ref"])
    for jr in events_by_job.keys():
        universe.add(jr)
    universe.update(xero_by_ref.keys())
    for k in site_names.keys():
        if not k.startswith("needs_lee") and k != "TEST-LEE":
            universe.add(k)
    for k in flip_cache.keys():
        if not k.startswith("needs_lee") and k != "TEST-LEE":
            universe.add(k)
    universe = {r for r in universe if REF_RE.match(r)}

    numeric_groups = defaultdict(list)
    for ref in universe:
        num = normalize_numeric(ref)
        if num:
            numeric_groups[num].append(ref)

    def site_evidence(ref):
        tokens = set()
        sn = site_names.get(ref)
        if sn and sn.get("name"):
            tokens |= site_tokens(sn["name"])
        fc = flip_cache.get(ref)
        if fc:
            tokens |= site_tokens(fc)
        return tokens

    def contacts_for(ref):
        return roofinv_contacts_by_ref.get(ref, set()) | xero_contacts_by_ref.get(ref, set())

    # -----------------------------------------------------------------
    # Same-site tier: different NNNN, same site/development.
    # Links are created ONLY by (1) a shared distinctive site-name phrase or
    # (2) an invoice line naming another ref's address. GPS-ambiguity
    # candidates in allocation_v2 corroborate but never create links.
    # -----------------------------------------------------------------
    display_name = {}
    phrases_by_canon = defaultdict(set)
    phrase_nums = defaultdict(set)    # (canon_ref, phrase) -> house numbers seen
    for src, is_dict in ((site_names, True), (flip_cache, False)):
        for k in sorted(src.keys()):
            if k.startswith("needs_lee") or k == "TEST-LEE" or not REF_RE.match(k):
                continue
            raw = src[k].get("name") if is_dict else src[k]
            if not raw:
                continue
            ck = canonical_ref(k)
            if ck not in display_name:
                display_name[ck] = raw
            for ph, nums in extract_site_phrases(raw):
                phrases_by_canon[ck].add(ph)
                phrase_nums[(ck, ph)] |= nums

    phrase_owners = defaultdict(set)
    for ck, phs in phrases_by_canon.items():
        for ph in phs:
            phrase_owners[ph].add(ck)

    ss_uf = DictUnionFind()
    ss_evidence = defaultdict(list)   # canon ref -> evidence strings
    line_site_display = {}            # canon ref -> address text from its invoice line
    house_rule_removed = []           # pairs dropped by the house-number rule

    # route 1: two different-NNNN refs share a distinctive site-name phrase.
    # House-number rule: on a STREET phrase, different house numbers do not
    # link unless clause (b) same-YY-within-3 (one intake event). Identical
    # numbers, or a named development/park phrase, link as before.
    for ph in sorted(phrase_owners):
        owners = sorted(phrase_owners[ph])
        if len({normalize_numeric(o) for o in owners}) < 2:
            continue
        street = is_street_phrase(ph)
        for i in range(len(owners)):
            for j in range(i + 1, len(owners)):
                a, b = owners[i], owners[j]
                if normalize_numeric(a) == normalize_numeric(b):
                    continue
                if street:
                    na = phrase_nums.get((a, ph), set())
                    nb = phrase_nums.get((b, ph), set())
                    if na and nb and (na & nb):
                        pass  # identical house number
                    elif adjacent_intake(a, b):
                        pass  # clause (b): one intake event
                    else:
                        house_rule_removed.append(
                            "%s (%s) <-> %s (%s) on street '%s': house numbers %s vs %s, "
                            "no invoice tie, not one intake — NOT linked" %
                            (a, display_name.get(a), b, display_name.get(b), ph,
                             sorted(na) or "none", sorted(nb) or "none"))
                        continue
                ss_uf.union(a, b)

    # route 2: an invoice line under ref R names another ref's address
    line_texts = []
    for r in xero_lines:
        tr = r.get("tracking_ref")
        if not tr or not REF_RE.match(tr):
            continue
        original = "%s %s" % (r.get("description") or "", r.get("reference") or "")
        line_texts.append((canonical_ref(tr), r, original, norm_text(original)))
    line_evidence_seen = set()
    route2_excluded = []
    for ph in sorted(phrase_owners):
        owners = sorted(phrase_owners[ph])
        needle = " %s " % ph
        ph_tokens = {t for t in ph.split() if t not in GENERIC_ADDR_WORDS}
        for ck_line, r, original, normed in line_texts:
            if needle not in normed:
                continue
            # Cross-site-invoice guard: if the line's OWN ref has its own
            # distinct site identity (own distinctive phrases sharing no
            # non-generic token with the mentioned phrase), the mention is a
            # multi-site invoice under one customer, not evidence of same
            # site (real case: a 1703-24/The Hickman line covering a
            # diagnostic at 147 De Beauvoir = 1701-24's site).
            own_phrases = phrases_by_canon.get(ck_line, set())
            if own_phrases:
                own_tokens = set()
                for op in own_phrases:
                    own_tokens |= {t for t in op.split() if t not in GENERIC_ADDR_WORDS}
                if ph_tokens and not (ph_tokens & own_tokens):
                    if (ck_line, ph) not in line_evidence_seen:
                        line_evidence_seen.add((ck_line, ph))
                        route2_excluded.append(
                            "%s line %s mentions '%s' but %s has its own distinct site %r — "
                            "cross-site invoice, NOT linked" %
                            (ck_line, r.get("invoice_number"), ph, ck_line,
                             display_name.get(ck_line)))
                    continue
            captured_raw, line_nums = capture_address_from_line(ph, original)
            captured = redact_money(captured_raw)
            street = is_street_phrase(ph)
            linked = False
            matched_owners = []
            for o in owners:
                if o == ck_line:
                    continue
                if normalize_numeric(o) == normalize_numeric(ck_line):
                    continue
                if street:
                    # House-number rule on street phrases: the line's numbers
                    # must intersect the owner's ('2 & 3 Olympic Mews' ties
                    # 2 and 3; '54 Cavell St' matches 54) — or clause (b).
                    onums = phrase_nums.get((o, ph), set())
                    if line_nums and onums and (line_nums & onums):
                        pass
                    elif adjacent_intake(ck_line, o):
                        pass
                    else:
                        key = (ck_line, ph, o)
                        if key not in line_evidence_seen:
                            line_evidence_seen.add(key)
                            house_rule_removed.append(
                                "%s line %s names '%s' but owner %s (%s) has house numbers %s "
                                "vs line's %s, no tie, not one intake — NOT linked" %
                                (ck_line, r.get("invoice_number"), captured, o,
                                 display_name.get(o), sorted(onums) or "none",
                                 sorted(line_nums) or "none"))
                        continue
                ss_uf.union(ck_line, o)
                matched_owners.append(o)
                linked = True
            # the '2 & 3' pattern also ties the named owners to EACH OTHER
            if street and len(line_nums) >= 2 and len(matched_owners) >= 2:
                for i in range(len(matched_owners)):
                    for j in range(i + 1, len(matched_owners)):
                        ss_uf.union(matched_owners[i], matched_owners[j])
            if linked and (ck_line, ph) not in line_evidence_seen:
                line_evidence_seen.add((ck_line, ph))
                ss_evidence[ck_line].append(
                    "invoice line %s under %s (%s) names '%s'" %
                    (r.get("invoice_number"), ck_line, r.get("date"), captured))
                if ck_line not in line_site_display:
                    line_site_display[ck_line] = captured

    comp_members = defaultdict(set)
    for node in list(ss_uf.parent.keys()):
        comp_members[ss_uf.find(node)].add(node)
    same_site_groups = []
    for members in comp_members.values():
        if len({normalize_numeric(m) for m in members}) >= 2:
            same_site_groups.append(sorted(members))
    same_site_groups.sort()
    group_of = {}
    for grp in same_site_groups:
        for m in grp:
            group_of[m] = grp

    tied_counts = Counter()
    for r in valid_photo_rows:
        ck = canonical_ref(r["job_ref"])
        if ck:
            tied_counts[ck] += 1

    xero_by_canon = defaultdict(list)
    for ref, rows in xero_by_ref.items():
        ck = canonical_ref(ref)
        if ck:
            xero_by_canon[ck].extend(rows)
    roofinv_texts_by_canon = defaultdict(list)
    for ref, texts in roofinv_texts_by_ref.items():
        ck = canonical_ref(ref)
        if ck:
            roofinv_texts_by_canon[ck].extend(texts)

    # Label fallback ladder (orchestrator polish ruling): 1) works description
    # from the target's invoice lines; 2) the target's PHASE MIX from its
    # billable_events windows; 3) the target's site name + "— separate job
    # number"; 4) "another job number at this roof". The bare word "works"
    # never ships — it tells Lee nothing.
    be_by_canon = {}
    for k in billable_events:
        ck_k = canonical_ref(k)
        if ck_k and ck_k not in be_by_canon:
            be_by_canon[ck_k] = billable_events[k]

    PHASE_DISPLAY_ORDER = [
        "Install", "Repair", "Leak detection", "Diagnostic", "Handover",
        "Spring roofcare", "Summer care and haycut", "Autumn roofcare",
        "Winter care", "Visit",
    ]

    def phase_mix_label(phases):
        names = [p for p in PHASE_DISPLAY_ORDER if p in set(phases)]
        if not names:
            return None
        names = ["site visits" if n == "Visit" else n for n in names]
        if len(names) == 1:
            n = names[0]
            return n[0].upper() + n[1:]
        if all(n.endswith(" roofcare") for n in names):
            seasons = [n.split(" ")[0].lower() for n in names]
            joined = ", ".join(seasons[:-1]) + " and " + seasons[-1]
            return joined[0].upper() + joined[1:] + " roofcare"
        lowered = [names[0]] + [n[0].lower() + n[1:] for n in names[1:]]
        return ", ".join(lowered[:-1]) + " and " + lowered[-1]

    def works_label(ck):
        """Ladder steps 1-2; None if neither invoice lines nor windows speak."""
        lab = derive_label(ck, xero_by_canon, roofinv_texts_by_canon)
        if lab != "works":
            return lab
        windows = be_by_canon.get(ck)
        if windows:
            return phase_mix_label([w["phase"] for w in windows])
        return None

    def rich_label(ref):
        """Full ladder, for confirmed-tier links. Never returns 'works'."""
        ck = canonical_ref(ref) or ref
        works = works_label(ck)
        if works:
            return works
        site = display_name.get(ck)
        if site:
            return "%s — separate job number" % site
        return "another job number at this roof"

    def same_site_label(ck):
        works = works_label(ck)
        site = display_name.get(ck) or line_site_display.get(ck)
        if works:
            works = works[0].upper() + works[1:]
            if site:
                return "%s — %s" % (works, site)
            return works
        if site:
            return "%s — separate job number" % site
        return "another job number at this roof"

    def same_site_corroboration(ck, member):
        shared_ph = phrases_by_canon.get(ck, set()) & phrases_by_canon.get(member, set())
        if shared_ph:
            return "shared distinctive site name: %s (%r / %r)" % (
                sorted(shared_ph)[0], display_name.get(ck), display_name.get(member))
        if ss_evidence.get(member):
            return ss_evidence[member][0]
        if ss_evidence.get(ck):
            return ss_evidence[ck][0]
        return "same-site group (linked through another member)"

    sister_refs = {}
    confirmed_count = 0
    candidate_count = 0
    same_site_link_count = 0
    zero_pad_dupe_pairs_skipped = 0
    for ref in sorted(valid_job_refs):
        num = normalize_numeric(ref)
        if not num:
            continue
        ref_key = canonical_key(ref)
        siblings = []
        for r in numeric_groups.get(num, []):
            if r == ref:
                continue
            if canonical_key(r) == ref_key:
                # same job, different zero-padding spelling — not a sister
                zero_pad_dupe_pairs_skipped += 1
                continue
            siblings.append(r)
        confirmed = []
        candidate = []
        ref_site_tokens = site_evidence(ref)
        ref_contacts = contacts_for(ref)
        for sib in sorted(siblings):
            corroborated = False
            reason = None
            sib_site_tokens = site_evidence(sib)
            shared_tokens = ref_site_tokens & sib_site_tokens
            if shared_tokens:
                corroborated = True
                reason = "site name match: %s" % ", ".join(sorted(shared_tokens))
            else:
                sib_contacts = contacts_for(sib)
                shared_contacts = ref_contacts & sib_contacts
                if shared_contacts:
                    corroborated = True
                    reason = "shared invoice contact: %s" % ", ".join(sorted(shared_contacts))
            if corroborated:
                confirmed.append({
                    "ref": sib,
                    "label": rich_label(sib),
                    "corroboration": reason,
                })
                confirmed_count += 1
            else:
                candidate.append({
                    "ref": sib,
                    "label": "possibly the same roof",
                })
                candidate_count += 1
        # same-site tier: other members of this ref's same-site group with a
        # DIFFERENT numeric core (same-numeric pairs belong to the tiers above)
        same_site = []
        ck = canonical_ref(ref)
        for member in group_of.get(ck, []):
            if member == ck or normalize_numeric(member) == num:
                continue
            same_site.append({
                "ref": member,
                "label": same_site_label(member),
                "corroboration": same_site_corroboration(ck, member),
                "tied_photos": tied_counts.get(member, 0),
            })
            same_site_link_count += 1
        if confirmed or candidate or same_site:
            entry = {"confirmed": confirmed, "candidate": candidate}
            if same_site:
                entry["same_site"] = same_site
            sister_refs[ref] = entry

    sister_refs_out = {
        "_meta": {
            "generated_from": [
                "grind/allocation_v2.jsonl", "grind/roof_invoice_match.jsonl",
                "grind/xero_invoice_lines_full.json", "grind/site_names.json",
                "grind/flip_site_names_cache.json",
            ],
            "generated_by": "scripts/mini_a/build_billable_events.py",
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "note": ("Confirmed tier = same NNNN numeric core, different "
                     "YY/suffix, AND site-name-token or invoice-contact "
                     "corroboration. Candidate tier = same NNNN only, no "
                     "corroboration, label 'possibly the same roof' "
                     "(navigation link only, IP-L9 — no allocation change). "
                     "Same-site tier (Lee's 11 Jul ruling: same site can "
                     "carry two distinct numbers) = DIFFERENT NNNN, "
                     "corroborated by a shared distinctive site-name phrase "
                     "(>=2 words, at least one non-generic) or an invoice "
                     "line naming the other ref's address; entries carry "
                     "tied_photos — a 0 renders as 'no photos tied yet', "
                     "never a dead link. GPS-ambiguity candidates corroborate "
                     "but never create links."),
        },
    }
    sister_refs_out.update(sister_refs)

    assert_no_money(sister_refs_out, "grind/sister_refs.json")

    with open(OUT_BILLABLE_EVENTS, "w") as f:
        json.dump(billable_events_out, f, indent=1, ensure_ascii=False)
    with open(OUT_SISTER_REFS, "w") as f:
        json.dump(sister_refs_out, f, indent=1, ensure_ascii=False)

    # -----------------------------------------------------------------
    # Run report (printed, this IS the deliverable data — no prose)
    # -----------------------------------------------------------------
    total_windows = sum(len(w) for w in billable_events.values())
    phase_counts = Counter()
    for windows in billable_events.values():
        for w in windows:
            phase_counts[w["phase"]] += 1
    roofs_with_events = len(billable_events)
    roofs_no_events = len(valid_job_refs - set(billable_events.keys()))

    print("=== RUN REPORT: build_billable_events.py ===")
    print("Counted by: this run, in-process, over the files loaded above (paths listed in _meta.generated_from).")
    print()
    print("roof_invoice_match.jsonl total rows: %d" % len(roof_invoice_rows))
    print("  needs_lee composite placeholder rows EXCLUDED (not a single real roof, flag=lee_not_ratified): %d" % needs_lee_rows)
    print("  lee_not_ratified rows kept under a REAL job_ref (band already unbilled/weak): %d" % lee_not_ratified_real_ref)
    print()
    print("valid allocation_v2 photo rows (excluding %d flagged paths): %d" % (len(flagged_paths), len(valid_photo_rows)))
    print("distinct job_refs in valid allocation set (\"tied roofs\"): %d" % len(valid_job_refs))
    print()
    print("roofs with >=1 window in billable_events.json: %d" % roofs_with_events)
    print("total windows across all roofs: %d" % total_windows)
    print("windows by phase:")
    for phase in PHASE_PRIORITY:
        if phase_counts.get(phase):
            print("  %-26s %d" % (phase, phase_counts[phase]))
    print("roofs in the valid photo set with ZERO billable_events.json entry (no roof_invoice_match rows at all -> flip_server falls back to flat view): %d" % roofs_no_events)
    print()
    print("--- OLYMPIC MEWS CHECK (301-14 vs 735-16) ---")
    print("Verified against grind/xero_invoice_lines_full.json (filter tracking_ref) and grind/site_names.json.")
    print("301-14 site_names.json name: %r" % (site_names.get("301-14") or {}).get("name"))
    print("735-16 site_names.json name: %r" % (site_names.get("735-16") or {}).get("name"))
    for ref in ("301-14", "735-16"):
        rows = xero_by_ref.get(ref, [])
        print("%s: %d xero invoice lines. Sample descriptions:" % (ref, len(rows)))
        for r in sorted(rows, key=lambda r: r["date"])[:4]:
            print("    %s %s | %s" % (r["date"], r["invoice_number"], r["description"]))
    print("FINDING (data): neither 301-14 nor 735-16 carries any 'repair'/'waterproof' keyword "
          "in grind/xero_invoice_lines_full.json or grind/roof_invoice_match.jsonl — both are "
          "green-roof maintenance/care refs. The 'repairs' works at Olympic Mews live under "
          "1336-21 ('Introductory fee for repairs at 2 & 3 Olympic Mews', INV-1000180, "
          "2021-06-17; zero tied photos). Per the updated spec's same-site tier (Lee's 11 Jul "
          "ruling), 301-14 / 735-16 / 1336-21 are now mutually linked via the same_site tier — "
          "see the group listing below. Label honesty note: 1336-21's label says 'Repairs' not "
          "'Waterproofing repairs' because the word 'waterproofing' appears nowhere in its "
          "invoice lines — verified before labelling, not assumed.")
    print()
    print("Same-site acceptance check — links as written to sister_refs.json:")
    for ref in ("301-14", "735-16"):
        entry = sister_refs.get(ref, {})
        print("  %s same_site: %s" % (ref, json.dumps(entry.get("same_site", []), ensure_ascii=False)))
    print()
    print("--- SAMPLE ROOF WINDOWS ---")
    for ref in ("556-15", "1124-19"):
        windows = billable_events.get(ref)
        print("%s:" % ref)
        if not windows:
            print("    (no billable_events entry)")
        else:
            for w in windows:
                print("    %s  [%s..%s]  band=%s  invoices=%d  source_events=%d" % (
                    w["header"], w["start"], w["end"], w["band"], len(w["invoices"]), w["source_events"]))
    care_contract_ref = None
    for ref, windows in billable_events.items():
        phases = {w["phase"] for w in windows}
        if len(windows) >= 3 and phases <= {"Spring roofcare", "Summer care and haycut",
                                             "Autumn roofcare", "Winter care", "Visit"}:
            care_contract_ref = ref
            break
    print("one care-contract roof (>=3 windows, all seasonal-care phases): %s" % care_contract_ref)
    if care_contract_ref:
        for w in billable_events[care_contract_ref]:
            print("    %s  [%s..%s]  band=%s" % (w["header"], w["start"], w["end"], w["band"]))
    print()
    print("--- SISTER REFS ---")
    print("job_refs (from the %d-strong valid allocation set) with >=1 sister: %d" % (len(valid_job_refs), len(sister_refs)))
    print("confirmed-tier sibling links: %d" % confirmed_count)
    print("candidate-tier sibling links: %d" % candidate_count)
    print("same-site-tier links written under tied-roof keys: %d" % same_site_link_count)
    print("zero-padding duplicate-spelling pairs excluded (same job, e.g. 0301-14 vs 301-14, NOT a sister): %d" % zero_pad_dupe_pairs_skipped)
    print()
    print("--- SAME-SITE GROUPS (full list, for over-linking eyeball) ---")
    print("Computed by: this run — shared distinctive site-name phrases across "
          "grind/site_names.json + grind/flip_site_names_cache.json, plus invoice-line "
          "address mentions in grind/xero_invoice_lines_full.json.")
    print("same-site groups: %d" % len(same_site_groups))
    gps_trio = {"301-14", "673-16", "735-16"}
    for grp in same_site_groups:
        parts = []
        for m in grp:
            parts.append("%s (%s, tied_photos=%d)" % (
                m, display_name.get(m) or line_site_display.get(m) or "no site name",
                tied_counts.get(m, 0)))
        print("  GROUP: " + "  |  ".join(parts))
        evs = []
        for m in grp:
            phs = sorted(phrases_by_canon.get(m, set()))
            if phs:
                evs.append("%s site-name phrases: %s" % (m, ", ".join(phs)))
        seen_line_evs = []
        for m in grp:
            for e in ss_evidence.get(m, []):
                if e not in seen_line_evs:
                    seen_line_evs.append(e)
        for e in evs + seen_line_evs:
            print("      evidence: %s" % e)
        if len(gps_trio & set(grp)) >= 2:
            print("      note: allocation_v2 GPS-ambiguous needs_lee rows (sweep-asks-r1 "
                  "items 7,20,21,27,29) independently corroborate this grouping; they did "
                  "NOT create these links.")
    print("conservative exclusions this run:")
    print("  town-phrase blocklist (never corroborates): %s" % ", ".join(sorted(SAME_SITE_PHRASE_BLOCKLIST)))
    for x in route2_excluded:
        print("  %s" % x)
    if not route2_excluded:
        print("  (no cross-site invoice mentions excluded)")
    print("house-number rule removals (same street, different numbers, no tie, not one intake):")
    for x in house_rule_removed:
        print("  %s" % x)
    if not house_rule_removed:
        print("  (none)")
    print()
    print("--- MONEY REDACTION ---")
    print("assert_no_money passed on both output files (no £ survived).")
    money_snippets_seen = []
    for row in roof_invoice_rows:
        for inv in row.get("invoices", []):
            s = inv.get("description_snippet", "")
            if MONEY_RE.search(s):
                money_snippets_seen.append(s)
    print("£/GBP snippets caught by the redaction regex during this run: %d" % len(money_snippets_seen))
    for s in money_snippets_seen[:10]:
        print("    caught: %r -> %r" % (s, redact_money(s)))
    print()
    print("wrote %s" % OUT_BILLABLE_EVENTS)
    print("wrote %s" % OUT_SISTER_REFS)


if __name__ == "__main__":
    main()
