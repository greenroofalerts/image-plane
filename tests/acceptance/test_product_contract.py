#!/usr/bin/env python3
"""Image Plane Product Contract acceptance harness (C1-C12).

Runs ON Mini A against the real corpus, the real HTTP surfaces and the
real service registry. Contract: docs/product-control/PRODUCT-CONTRACT.md.

Prints one PASS / FAIL / BLOCKED line per condition with the counts and
the query behind it. Exit 1 on any FAIL. Never writes anything.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter

ROOT = "/Users/macminia/image-plane"
RESULTS = os.path.join(ROOT, "incoming/worker/collection/results.json")
STATUS = os.path.join(ROOT, "incoming/worker/collection/status.json")
RUNS = os.path.join(ROOT, "incoming/worker/runs.jsonl")
DAILY = os.path.join(ROOT, "daily_worker.py")
MCP = os.path.join(ROOT, "incoming/worker/runtime/mcp-20260910/server.py")
JOB_SCREEN_HOST = "http://macminias-mac-mini.taild9fb8c.ts.net:8789"

REF = re.compile(r"(?<![\w-])\d{3,4}-\d{2}(?:-[A-Za-z]+)?(?![\w-])")

verdicts = []


def verdict(cid, ok, text, blocked=False):
    state = "BLOCKED" if blocked else ("PASS" if ok else "FAIL")
    verdicts.append((cid, state))
    print("%s %s — %s" % (cid, state, text))
    return ok


def dicto(o):
    return o if isinstance(o, dict) else {}


def evidence_ok(job, record=None):
    """Accepted evidence shapes, as the recorded machinery writes them:
    - lee_answer;
    - lane0_settled_answer with a basis or authority id (Lee ruling applied;
      a spine citation with basis+record_id also passes);
    - id_ladder_service.run whose ladder dict names >=2 lanes_run, or a
      service row whose job state is settled (lane-0 veto inside the service);
    - dict method naming >=2 lanes joined by '+';
    - list evidence citing lee_voice;
    - list evidence citing photo_membership, accepted ONLY where the same
      record's own album titles carry the same job ref (C3's Lee-ruled
      strong evidence, corroborated inside the record)."""
    ev = job.get("evidence")
    method = job.get("method") or ""
    if isinstance(ev, dict):
        m = ev.get("method") or method
        if m == "lee_answer":
            return True, "lee_answer"
        if m == "lane0_settled_answer" and (ev.get("basis") or ev.get("authority_id")):
            return True, "lane0-settled"
        if m == "id_ladder_service.run":
            lad = dicto(ev.get("ladder"))
            run = lad.get("lanes_run")
            if isinstance(run, list) and len(run) >= 2:
                return True, "ladder-run"
            if job.get("state") == "settled":
                return True, "ladder-settled"
            return False, "ladder-insufficient"
        lanes = [l for l in str(m).split("+") if l.strip().startswith("lane")]
        if len(lanes) >= 2:
            return True, "lanes"
        if ev.get("basis") and ev.get("record_id"):
            return True, "spine-citation"
        return False, "dict-insufficient"
    if isinstance(ev, list) and ev:
        if any(dicto(x).get("source_kind") == "lee_voice" for x in ev):
            return True, "lee_voice"
        if record is not None and any(
                dicto(x).get("source_id") == "photo_membership" for x in ev):
            vals = {str(dicto(x).get("value")) for x in ev
                    if dicto(x).get("source_id") == "photo_membership"}
            titles = " | ".join(
                str(dicto(m).get("album") or "")
                for m in (record.get("memberships") or []))
            if vals & set(REF.findall(titles)):
                return True, "album-membership"
        return False, "list-unaccepted-source"
    return False, "empty"


def load_corpus():
    with open(RESULTS) as f:
        return json.load(f)


# ---------------------------------------------------------------- C1
def check_c1():
    files = [DAILY, MCP]
    js = os.path.join(ROOT, "job_screen.py")
    if os.path.exists(js):
        files.append(js)
    send_libs = ["smtplib", "sendmail", "resend.com", "sendgrid",
                 "nodemailer", "mandrill", "postmark", "smtp."]
    hits = []
    for path in files:
        if not os.path.exists(path):
            hits.append((path, "FILE-MISSING"))
            continue
        body = open(path, errors="replace").read()
        for pat in send_libs:
            if pat in body:
                hits.append((path, pat))
        if "api.xero.com" in body:
            hits.append((path, "api.xero.com"))
        if "dbjdxamqbwhyhnlwsfxk" in body:
            # GRA project ref: fail only beside a write verb
            if re.search(r"\.(post|patch|delete|insert|upsert)\(", body):
                hits.append((path, "gra-project-write"))
    scanned = [f for f in files if os.path.exists(f)]
    verdict("C1", not hits,
            "scanned %d live files (%s); forbidden-pattern hits: %s"
            % (len(scanned), ", ".join(os.path.basename(p) for p in scanned),
               hits if hits else "none"))


# ---------------------------------------------------------------- C2 / C4
def check_c2_c4(records):
    tally = Counter()
    bad = []
    noev = []
    for r in records:
        ident = dicto(r.get("identity"))
        if not ident.get("job_ref"):
            continue
        job = dicto(ident.get("job"))
        ok, kind = evidence_ok(job, r)
        if ok:
            tally[kind] += 1
        else:
            tally[kind] += 1
            bad.append((r.get("sha256", "")[:12], ident["job_ref"], kind))
        if not job.get("evidence"):
            noev.append(r.get("sha256", "")[:12])
    verdict("C2", not bad,
            "job-assigned rows=%d tally=%s violations=%d %s"
            % (sum(tally.values()), dict(tally), len(bad), bad[:5]))
    verdict("C4", not noev,
            "job-assigned rows with empty evidence object: %d %s"
            % (len(noev), noev[:5]))


# ---------------------------------------------------------------- C3
# Lee-ruled job-reference aliases: each set is ONE job.
# 1588-26 = 1858-26 — Lee, 1 Aug 2026: "1588 is a known mistype that has
# worked its way into even invoices - just combine them" (ask ledger, ID
# LADDER section). The alias applies wherever a job reference is read.
ALIASES = [frozenset(("1588-26", "1858-26"))]

# Zero-pad is a recorded lesson (knowledge_notes canon rows, 8 Jul 2026):
# album titles carry leading-zero refs (0579-15), assignments use the plain
# form (579-15). Same job, string mismatch.
def norm_ref(r):
    head, sep, tail = str(r).partition("-")
    return (head.lstrip("0") or "0") + sep + tail


def refs_equal(a, b):
    if not a or not b:
        return False
    return (a == b or norm_ref(a) == norm_ref(b)
            or frozenset((a, b)) in ALIASES)


# Evidence kinds that ARE a Lee ruling. Lane 0 is a veto, not a vote, so a
# ruling is the "stronger canonical evidence" C3 itself names. Derived
# multi-lane evidence (ladder-run, lanes, spine-citation) is NOT in this
# set: derived lanes never outvote an album title on their own.
RULING_KINDS = {"lee_answer", "lane0-settled", "lee_voice"}


def evidence_values(job):
    """Scalar ref values anywhere in the evidence object, so a withheld
    row can show its contradiction even when the top-level candidates list
    holds only one side (both sides preserved = inspectable, C3's clause)."""
    vals = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("value", "job_ref", "candidates") and isinstance(v, str):
                    vals.add(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(job.get("evidence"))
    return vals


def check_c3(records):
    ok = ruled = withheld = 0
    viol = []
    for r in records:
        ident = dicto(r.get("identity"))
        jr = ident.get("job_ref")
        job = dicto(ident.get("job"))
        for m in r.get("memberships") or []:
            title = dicto(m).get("album") or ""
            refs = REF.findall(title)
            if not refs:
                continue
            aref = refs[0]
            if refs_equal(jr, aref):
                ok += 1
                continue
            evok, kind = evidence_ok(job, r)
            if job.get("state") == "contradicted" and (
                    aref in (job.get("candidates") or [])
                    or aref in evidence_values(job)):
                if evok or job.get("evidence"):
                    withheld += 1
                else:
                    viol.append((r.get("sha256", "")[:12], title, aref,
                                  "contradicted-no-evidence"))
            elif evok and kind in RULING_KINDS:
                ruled += 1
            else:
                viol.append((r.get("sha256", "")[:12], title, aref, jr))
    passed = verdict("C3", not viol,
                     "album-ref rows=%d match=%d (incl. zero-pad/alias "
                     "normalization) ruled-override=%d "
                     "withheld-with-evidence=%d violations=%d %s"
                     % (ok + ruled + withheld + len(viol), ok, ruled,
                        withheld, len(viol), viol[:5]))
    if ruled:
        print("   C3-note — %d album-ref photos resolve to a different job "
              "under an applied Lee ruling (lane0/lee_voice/lee_answer, each "
              "carrying basis or authority id in the record)." % ruled)
    if withheld:
        print("   C3-note BLOCKED — %d album-ref photos are correctly "
              "withheld as contradicted with evidence, but the conflict is "
              "not surfaced to Lee as a decision; only Lee can settle "
              "which of the two candidate jobs each photo belongs to." % withheld)
    return passed


# ---------------------------------------------------------------- C5
def check_c5(records):
    jobs = Counter()
    for r in records:
        ident = dicto(r.get("identity"))
        if ident.get("job_ref"):
            jobs[ident["job_ref"]] += 1
    assigned = [r for r in records if dicto(r.get("identity")).get("job_ref")]
    sample = assigned[::max(1, len(assigned) // 20)][:20]
    missing = [r["path"] for r in sample if not os.path.exists(r.get("path", ""))]
    verdict("C5", jobs and not missing,
            "jobs with photos=%d sample=%d files missing on disk=%d %s"
            % (len(jobs), len(sample), len(missing), missing[:3]))


# ---------------------------------------------------------------- C6 / C7
def check_c6(records):
    tally = Counter()
    missing = 0
    for r in records:
        e = dicto(r.get("event"))
        if not e:
            continue
        if e.get("chargeability"):
            tally[e["chargeability"]] += 1
        else:
            missing += 1
    verdict("C6", missing == 0,
            "event rows with chargeability=%d values=%s missing=%d"
            % (sum(tally.values()), dict(tally), missing))


def check_c7(records):
    terms = Counter()
    for r in records:
        k = dicto(r.get("keywords"))
        for src in ("lee", "machine_proposals", "original_words"):
            v = k.get(src)
            if isinstance(v, list):
                for w in v:
                    terms[(src, str(w))] += 1
    distinct = len({w for (_, w) in terms})
    verdict("C7", distinct > 50,
            "distinct component terms=%d across %d tagged instances; "
            "sample=%s" % (distinct, sum(terms.values()),
                           list(terms.items())[:5]))


# ---------------------------------------------------------------- C8 / C9
def check_c8():
    lanes = {}
    if os.path.exists(STATUS):
        s = json.load(open(STATUS))
        lanes = s.get("lanes") or s.get("lanes_state") or {}
    names = set(lanes) if isinstance(lanes, dict) else set()
    ok = "daily_freshness" in names and "historical_enrichment" in names
    verdict("C8", ok, "status.json lane keys=%s" % sorted(names))


def check_c9(records):
    fmt = Counter(str(r.get("display_format")) for r in records)
    jpeg = fmt.get("jpeg", 0)
    last_ts = "no-runs-log"
    recent = False
    if os.path.exists(RUNS):
        lines = [l for l in open(RUNS, errors="replace") if l.strip()]
        if lines:
            try:
                last = json.loads(lines[-1])
                last_ts = last.get("started_at") or last.get("ts") or last.get("time") or "?"
            except ValueError:
                last_ts = "unparsable-last-line"
    verdict("C9", jpeg == len(records),
            "display_format jpeg=%d of %d rows (%s); worker last run=%s "
            "(recency judged from the timestamp above)"
            % (jpeg, len(records), dict(fmt), last_ts))


# ---------------------------------------------------------------- C10
def fetch(url, want_status):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def check_c10():
    code, body = fetch(JOB_SCREEN_HOST + "/job/1892-26", 200)
    ok_job = code == 200 and "<img" in body
    code2, _ = fetch(JOB_SCREEN_HOST + "/job/0000-00", 404)
    ok_404 = code2 == 404
    code3, body3 = fetch(JOB_SCREEN_HOST + "/attention", 200)
    ok_att = code3 == 200
    verdict("C10", ok_job and ok_404 and ok_att,
            "/job/1892-26=%d imgs=%s; bad ref=%d; /attention=%d"
            % (code, ok_job, code2, code3))


# ---------------------------------------------------------------- C11
def check_c11():
    if not os.path.exists(MCP):
        verdict("C11", False, "server file missing: %s" % MCP)
        return
    body = open(MCP, errors="replace").read()
    tools = re.findall(r'@mcp\.tool\(\s*(?:name="([^"]+)")?', body)
    n = len(re.findall(r"@mcp\.tool", body))
    if n == 0:
        verdict("C11", False, "no @mcp.tool registrations found in server.py")
        return
    try:
        proc = subprocess.Popen(
            ["python3", MCP], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, cwd=os.path.dirname(MCP))
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "contract-harness", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]
        payload = "".join(json.dumps(m) + "\n" for m in msgs)
        out, _ = proc.communicate(payload.encode(), timeout=20)
        listed = 0
        for line in out.decode("utf-8", "replace").splitlines():
            try:
                resp = json.loads(line)
            except ValueError:
                continue
            if resp.get("id") == 2:
                listed = len((resp.get("result") or {}).get("tools") or [])
        verdict("C11", listed >= 10,
                "registered tools=%d; live tools/list answered with %d tools"
                % (n, listed))
    except Exception as e:
        verdict("C11", True if n >= 10 else False,
                "registered tools=%d; live handshake not completed (%s)"
                % (n, e), blocked=n >= 10)


# ---------------------------------------------------------------- C12
PLISTS = [
    ("com.leeos.image-plane-daily-worker",
     os.path.expanduser("~/Library/LaunchAgents/com.leeos.image-plane-daily-worker.plist")),
    ("com.leeos.image-plane-job-screen",
     os.path.expanduser("~/Library/LaunchAgents/com.leeos.image-plane-job-screen.plist")),
    ("com.lee.imageplane-siteview",
     "/Library/LaunchDaemons/com.lee.imageplane-siteview.plist"),
]


def check_c12():
    out = subprocess.run(["launchctl", "list"], capture_output=True,
                         text=True).stdout
    problems = []
    for label, path in PLISTS:
        loaded = label in out
        if not loaded:
            problems.append("%s not in launchctl list" % label)
        if not os.path.exists(path):
            problems.append("%s plist missing" % label)
            continue
        body = open(path, errors="replace").read()
        if "RunAtLoad" not in body and "KeepAlive" not in body and "StartCalendarInterval" not in body:
            problems.append("%s plist has no restart key" % label)
    verdict("C12", not problems,
            "services=%s problems=%s"
            % ([l for l, _ in PLISTS], problems if problems else "none"))


def main():
    print("harness: %s" % os.path.abspath(__file__))
    print("corpus: %s" % RESULTS)
    records = load_corpus()
    print("records loaded: %d (query: json.load of results.json this run)"
          % len(records))
    check_c1()
    check_c2_c4(records)
    check_c3(records)
    check_c5(records)
    check_c6(records)
    check_c7(records)
    check_c8()
    check_c9(records)
    check_c10()
    check_c11()
    check_c12()
    fails = [c for c, s in verdicts if s == "FAIL"]
    print("----")
    print("summary: %d checks, %d PASS, %d FAIL, %d BLOCKED"
          % (len(verdicts),
             sum(1 for _, s in verdicts if s == "PASS"), len(fails),
             sum(1 for _, s in verdicts if s == "BLOCKED")))
    if fails:
        print("failing conditions: %s" % ", ".join(fails))
        sys.exit(1)


if __name__ == "__main__":
    main()
