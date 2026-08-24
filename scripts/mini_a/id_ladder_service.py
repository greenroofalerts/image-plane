#!/usr/bin/env python3
"""THE ONE IDENTITY LADDER, CALLABLE BY ANY PRODUCT.

Master Runbook Step 11, 11 August 2026. Lee found that Glengarry had built its
own smaller identity process instead of running the agreed ladder, which is why
an email from Wissam Bettahar could sit on the board as a nameless enquiry while
his job 1882-26 sat two columns away.

WHAT THIS IS. One runner for the recorded ladder. It does not restate the rules:
the LANE ORDER comes from `public.id_ladder_lanes()` in the shared database, and
Step 0 asks the shared canon. The loaders it uses are the ones the ladder
already has in fewshot_engine.py, imported, never copied.

WHAT IT IS NOT. It is not a matcher. It never invents a job, it never picks
between two candidates, and a lane it cannot reach is reported as unreachable,
never as "nothing found" — the half-search rule, in code.

HOW A PRODUCT CALLS IT:
    echo '{"sender_email":"x@y.z","text":"...","streets":["Patten Road"]}' \
        | python3 id_ladder_service.py
It answers one JSON object on standard output and never writes anything.
"""
import csv
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fewshot_engine as ladder            # the existing ladder, reused not copied

REGISTER_CSV = Path(os.environ.get("LEEOS_JOB_REGISTER",
                    "/Users/macminia/image-plane/portfolio_register.csv"))
MAIL_INDEX = Path(os.environ.get("LEEOS_MAIL_INDEX",
                  "/Users/macminia/roof-story-archive/index.db"))
CANON_SNAPSHOT = Path(os.environ.get("LEEOS_CANON_SNAPSHOT",
                      "/Users/macminia/image-plane/grind/canon_snapshot.json"))
DOWNLOADS = Path(os.environ.get("LEEOS_DOWNLOADS", "/Users/macminia/Downloads"))

# The recorded order, used ONLY when the shared database cannot be reached. It is
# not a second definition: it is a copy of the answer the database gives, and the
# result says which of the two was used, so nobody can mistake one for the other.
RECORDED_ORDER = ["lane0_settled_answer", "lane1_job_ref", "lane2_gra_sites",
                  "lane3_project_folders", "lane4_xero", "lane5_mail",
                  "lane6_downloads", "lane7_photo_register", "lane8_address_tokens"]

JOB_REF = re.compile(r"\b(\d{3,4})-(\d{2})\b")


def is_job_ref(text):
    """A job reference, not a date. 2021-07 is a month; 1882-26 is a job."""
    m = re.fullmatch(r"(\d{3,4})-(\d{2})", str(text or "").strip())
    if not m:
        return False
    first, second = int(m.group(1)), int(m.group(2))
    return not (1900 <= first <= 2100 and 1 <= second <= 12)


def normalise(ref):
    """1059-19 and 01059-19 are the same job. Leading zeros are not identity."""
    m = re.fullmatch(r"0*(\d+)-(\d{2})", str(ref or "").strip())
    return f"{m.group(1)}-{m.group(2)}" if m else str(ref or "").strip()


def shared_credential():
    """The same credential the canon puller finds. One home, one key, no copies."""
    try:
        import pull_canon_snapshot as puller
        return puller.find_credential()[:2]
    except Exception:
        return None, None


def lane_order():
    """The canonical order, from the shared database when it answers."""
    try:
        import urllib.request
        url = os.environ.get("LEEOS_SUPABASE_URL")
        key = os.environ.get("LEEOS_SUPABASE_KEY")
        if not url or not key:
            # The same credential the canon puller finds, so the lane ORDER comes
            # from the shared database rather than from this file's copy of it.
            url, key = shared_credential()
        if not url or not key:
            return RECORDED_ORDER, "recorded-order (no shared credential on this machine)"
        req = urllib.request.Request(
            f"{url}/rest/v1/rpc/id_ladder_lanes", data=b"{}",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as answer:
            lanes = json.loads(answer.read())
        if isinstance(lanes, list) and lanes:
            return lanes, "public.id_ladder_lanes()"
    except Exception:
        pass
    return RECORDED_ORDER, "recorded-order (the shared database could not be reached)"


def known_jobs():
    """Lane 1's registry: every job reference the register actually holds."""
    found = {}
    try:
        with open(REGISTER_CSV) as handle:
            for row in csv.DictReader(handle):
                ref = normalise(row.get("job_ref"))
                if is_job_ref(ref) or re.fullmatch(r"\d+-\d{2}", ref or ""):
                    found[ref] = row.get("site") or ""
    except OSError:
        return None                      # unreachable, never "no jobs exist"
    return found


# ─── the lanes ────────────────────────────────────────────────────────────────
# Each returns (hits, note, reachable). A lane that cannot be reached returns
# reachable=False and NEVER an empty result, because those mean different things.

def lane0_settled_answer(ev, canon):
    if canon is None:
        return [], "canon could not be read", False
    tokens = [t for t in ([*ev.get("job_refs", []), *ev.get("streets", []),
                           ev.get("sender_email", "")]) if t]
    for token in tokens:
        ruling = ladder.canon_ruling(str(token).lower(), canon)
        if not ruling:
            continue
        note = "Lee settled this on %s: %s" % (ruling.get("ruled_on"), ruling.get("answer"))
        # THE ANSWER IS NOT ALWAYS A JOB. His Culverden Road ruling settles the
        # SITE of job 1059-19, not which job an email belongs to. Where the
        # ruling's own SUBJECT names a job, that job is settled and the ladder
        # stops. Where it does not, the ruling is still carried forward so the
        # product can show it — a settled fact is never dropped just because it
        # did not answer this particular question.
        for field in (ruling.get("subject"), ruling.get("answer")):
            for m in JOB_REF.finditer(str(field or "")):
                if is_job_ref(m.group(0)):
                    return [normalise(m.group(0))], note, True
        return [], note, True
    return [], "no settled ruling names this", True


def lane1_job_ref(ev, registry):
    if registry is None:
        return [], "the job register could not be read", False
    text = " ".join(str(x) for x in [ev.get("text", ""), ev.get("subject", "")])
    hits = []
    for m in JOB_REF.finditer(text):
        ref = normalise(m.group(0))
        if is_job_ref(m.group(0)) and ref in registry:
            hits.append(ref)
    return sorted(set(hits)), ("the text names it and the register holds it" if hits
                               else "the text names no job the register holds"), True


def lane2_gra_sites(ev):
    """The job universe: which job does this contact or this site already have?

    GRA's own `sites` table is not readable from this machine — the only key here
    is the anon key, which row-level security denies. The shared job registry in
    LeeOSplus IS readable, and it is the same universe the board itself serves,
    so the lane asks that and says plainly which of the two it reached.
    """
    url, key = shared_credential()
    if not url or not key:
        return [], "no shared credential on this machine, and GRA's own site table is denied to the anon key", False
    import urllib.parse
    import urllib.request

    def ask(query):
        req = urllib.request.Request(
            f"{url}/rest/v1/enquiries?{query}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=12) as answer:
            return json.loads(answer.read())

    hits, notes = [], []
    who = str(ev.get("sender_email") or "").strip().lower()
    try:
        if who:
            rows = ask("select=job_number,client_name,client_email,site_address&client_email=eq."
                       + urllib.parse.quote(who) + "&job_number=not.is.null")
            for row in rows:
                ref = normalise(row.get("job_number"))
                if is_job_ref(ref):
                    hits.append(ref)
                    notes.append(f"the job registry holds {ref} for {who}")
        for token in [t for t in ev.get("streets", []) if t][:3]:
            rows = ask("select=job_number,site_address&site_address=ilike."
                       + urllib.parse.quote(f"%{token}%") + "&job_number=not.is.null")
            for row in rows:
                ref = normalise(row.get("job_number"))
                if is_job_ref(ref):
                    hits.append(ref)
                    notes.append(f"the job registry puts {ref} at {row.get('site_address')}")
    except Exception as err:
        return [], f"the shared job registry could not be read: {err}", False
    return sorted(set(hits)), ("; ".join(notes[:3]) if notes
                               else "the job registry holds no job for this contact or site"), True


def lane3_project_folders(ev):
    root = Path("/Users/macminia/Dropbox")
    if not root.exists():
        return [], "the Dropbox project folders are not on this machine", False
    return [], "no folder names this", True


XERO_MIRROR = Path(os.environ.get("LEEOS_XERO_MIRROR",
                   "/Users/macminia/image-plane/grind/xero_invoice_lines_full.json"))


# lane4's per-answer basis: ref -> 'sender' | 'site-words'. Read by _judge.
LANE4_BASIS = {}


def lane4_xero(ev):
    """Xero, BOTH organisations, through the mirror the glenross connector built.

    THE SOURCE-SELECTION DEFECT THIS FIXES, found on the real Stephanie
    Rawlinson case, 12 August 2026: this lane said "no Xero mirror exists on
    this machine" while a two-organisation mirror (Green Roof Revival Limited
    AND Organic Roofs Ltd, 508 job references) sat in this very folder. Wrong
    path, reported as a missing source — the exact class of failure Lee told
    us to expose. The mirror's own age rides on every answer, because a stale
    mirror must never pass itself off as current Xero.
    """
    if not XERO_MIRROR.exists():
        return [], "the Xero mirror is not on this machine", False
    try:
        rows = json.loads(XERO_MIRROR.read_text())
    except (OSError, ValueError) as err:
        return [], "the Xero mirror could not be read: %s" % err, False
    import time
    age_days = round((time.time() - XERO_MIRROR.stat().st_mtime) / 86400)
    stale = " (mirror is %d days old — newer invoices are not in it)" % age_days if age_days > 7 else ""
    # WHICH FIELD a hit rests on matters as much as the hit. Found on the real
    # Filipa Teixeira case, 14 August 2026: her London enquiry (16 Victoria
    # Gardens W11) matched a BRIGHTON job (1321-21 Victoria Bowls) because the
    # street words "victoria gardens" sat in a different customer's invoice
    # description — the sender herself matched nothing. A street-words-only
    # billing hit and a street-words address-token hit are the SAME one field
    # seen twice, never two independent lanes (the never-single-field law).
    # The sender is an email AND a person. Found on the real Mark Smith
    # billable event, 14 August 2026: his invoice names "Mark Smith" while the
    # evidence carried only mark.iain.smith@gmail.com, so the contact match
    # never fired. sender_name comes from the asking product own record (GRA
    # contact, card fromName) - real evidence, not a guess.
    sender_tokens = [str(t).lower() for t in [ev.get("sender_email", ""), ev.get("sender_name", "")]
                     if t and len(str(t)) >= 4]
    site_tokens = [str(t).lower() for t in (list(ev.get("streets", [])) + [ev.get("subject", "")])
                   if t and len(str(t)) >= 4]
    hits, notes = [], []
    LANE4_BASIS.clear()
    for row in rows:
        blob = ("%s %s %s" % (row.get("contact", ""), row.get("description", ""),
                              row.get("reference", ""))).lower()
        by_sender = any(tok in blob for tok in sender_tokens)
        by_site = any(tok in blob for tok in site_tokens)
        if by_sender or by_site:
            ref = normalise(str(row.get("tracking_ref") or ""))
            for m in JOB_REF.finditer(str(row.get("tracking_ref") or "") + " " + str(row.get("reference") or "")):
                if is_job_ref(m.group(0)):
                    r = normalise(m.group(0))
                    hits.append(r)
                    if by_sender:
                        LANE4_BASIS[r] = "sender"
                    else:
                        LANE4_BASIS.setdefault(r, "site-words")
                    notes.append("%s invoice %s (%s)" % (row.get("tenant"), row.get("invoice_number"), m.group(0)))
    if hits:
        return sorted(set(hits)), ("; ".join(notes[:3]) + stale), True
    return [], "neither organisation's invoice lines name this contact or site" + stale, True


GMAIL_ENV = Path(os.environ.get("LEEOS_GMAIL_ENV",
                 "/Users/macminia/glengarry-unified-board/.env.local"))


_GMAIL_TOKEN_CACHE = {"token": None, "minted": 0.0}


def _gmail_token():
    """An access token for the ONE unified inbox (every company alias arrives
    in lee@organicroofs.co.uk), using the Gmail credential already on this
    machine. Returns None, with a reason, when it cannot."""
    import time
    # ONE exchange per process, not one per card: a 118-card board asked Google
    # for 118 tokens and blew its own time allowance. Found live, 12 August.
    if _GMAIL_TOKEN_CACHE["token"] and time.time() - _GMAIL_TOKEN_CACHE["minted"] < 2400:
        return _GMAIL_TOKEN_CACHE["token"], None
    try:
        env = {}
        for line in GMAIL_ENV.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k] = v.strip().strip('"')
        import urllib.parse
        data = urllib.parse.urlencode({
            "client_id": env["GOOGLE_CLIENT_ID"], "client_secret": env["GOOGLE_CLIENT_SECRET"],
            "refresh_token": env["GOOGLE_REFRESH_TOKEN"], "grant_type": "refresh_token"}).encode()
        import urllib.request
        got = json.loads(urllib.request.urlopen(
            urllib.request.Request("https://oauth2.googleapis.com/token", data=data), timeout=15).read())
        _GMAIL_TOKEN_CACHE.update(token=got.get("access_token"), minted=time.time())
        return got.get("access_token"), None
    except Exception as err:
        return None, str(err)


def _gmail_search(token, query, cap=8):
    import urllib.parse, urllib.request
    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages?q=%s&maxResults=%d"
        % (urllib.parse.quote(query), cap),
        headers={"Authorization": "Bearer %s" % token})
    hits = json.loads(urllib.request.urlopen(req, timeout=15).read()).get("messages") or []
    out = []
    for h in hits[:cap]:
        req = urllib.request.Request(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/%s?format=metadata"
            "&metadataHeaders=From&metadataHeaders=To&metadataHeaders=Subject&metadataHeaders=Date" % h["id"],
            headers={"Authorization": "Bearer %s" % token})
        m = json.loads(urllib.request.urlopen(req, timeout=15).read())
        heads = {x["name"]: x["value"] for x in m.get("payload", {}).get("headers", [])}
        out.append({"from": heads.get("From", ""), "to": heads.get("To", ""),
                    "subject": heads.get("Subject", ""), "date": heads.get("Date", ""),
                    "snippet": m.get("snippet", "")})
    return out


def lane5_mail(ev, registry):
    """Mail: the ONE unified inbox, LIVE, plus the archive index for history.

    12 August 2026, repairing the freshness defect the Stephanie case exposed:
    the archive index ends before current threads, so today's exchange about a
    visit date was invisible to the lane that exists to see it. The live
    search runs FIRST — freshness matters most — and the archive still
    answers for the years the live window does not cover. Original From/To
    alias identity is preserved in the note, because which company address a
    thread used is business context.
    """
    who = str(ev.get("sender_email") or "").lower().strip()
    if not who:
        return [], "no sender to search mail with", True
    live_hits, live_note = [], ""
    token, why = _gmail_token()
    if token:
        try:
            msgs = _gmail_search(token, "from:%s OR to:%s newer_than:60d" % (who, who))
            found = set()
            for m in msgs:
                blob = " ".join([m["subject"], m["snippet"]])
                for match in JOB_REF.finditer(blob):
                    if is_job_ref(match.group(0)):
                        found.add(normalise(match.group(0)))
            live_hits = sorted(found)
            if msgs:
                newest = msgs[0]
                live_note = ("LIVE unified inbox: %d current message(s), newest %s — from %s to %s. "
                             % (len(msgs), newest["date"][:22], newest["from"][:40], newest["to"][:40]))
            else:
                live_note = "LIVE unified inbox: no current messages with them. "
        except Exception as err:
            live_note = "live inbox could not be searched (%s). " % str(err)[:60]
    else:
        live_note = "live inbox credential failed (%s). " % str(why)[:60]
    if not MAIL_INDEX.exists():
        if live_note.startswith("LIVE"):
            return live_hits, live_note + "Archive index not on this machine.", True
        return [], live_note + "and the archive index is not on this machine", False
    try:
        db = sqlite3.connect(f"file:{MAIL_INDEX}?mode=ro", uri=True)
        rows = db.execute(
            "select r.ref, count(*) c from refs r join messages m on m.rowid = r.message_rowid "
            "where lower(m.from_addr) like ? or lower(m.to_addr) like ? group by 1 order by c desc",
            (f"%{who}%", f"%{who}%")).fetchall()
        db.close()
    except sqlite3.Error as err:
        return [], f"the mail archive could not be read: {err}", False
    hits = [(normalise(ref), n) for ref, n in rows if is_job_ref(ref)]
    if registry:
        hits = [(r, n) for r, n in hits if r in registry] or hits
    if not hits:
        if live_hits:
            return live_hits, live_note + "The archive names no job.", True
        return [], live_note + "their mail names no job (live or archived)", True
    top = max(n for _, n in hits)
    # ONE message is not an identity. It is reported, and it is weak on purpose.
    # Written the long way on purpose: the products start this with the system
    # python (3.9), which refuses nested quotes inside an f-string. Found live on
    # 11 August 2026, when the board reported the ladder unavailable.
    said = []
    for ref, count in hits[:4]:
        said.append("%s (%d message%s)" % (ref, count, "s" if count > 1 else ""))
    merged = sorted(set([r for r, n in hits if n == top] + live_hits))
    return merged, live_note + "archive names " + ", ".join(said), True


def lane6_downloads(ev, registry):
    if not DOWNLOADS.exists():
        return [], "the downloads folder is not on this machine", False
    tokens = [str(t).lower() for t in ev.get("streets", []) if t]
    if not tokens:
        return [], "no site words to search filenames with", True
    hits = set()
    try:
        for name in os.listdir(DOWNLOADS):
            low = name.lower()
            if any(t in low for t in tokens):
                for m in JOB_REF.finditer(name):
                    if is_job_ref(m.group(0)):
                        hits.add(normalise(m.group(0)))
    except OSError as err:
        return [], f"the downloads folder could not be read: {err}", False
    return sorted(hits), ("a downloaded file names it" if hits else "no downloaded file names it"), True


def lane7_photo_register(ev, registry):
    try:
        register = ladder.load_photo_register(
            "/Users/macminia/image-plane/grind/photo_register.jsonl")
    except Exception:
        register = None
    if not register:
        return [], "the photo register could not be read", False
    tokens = [str(t).lower() for t in ev.get("streets", []) if t]
    if not tokens:
        return [], "no site words to search the photo register with", True
    hits = {normalise(row.get("job_ref")) for row in register.values()
            if row.get("job_ref") and any(t in json.dumps(row).lower() for t in tokens)}
    hits = {h for h in hits if is_job_ref(h)}
    return sorted(hits), ("a registered photograph names it" if hits else
                          "no registered photograph names it"), True


def lane8_address_tokens(ev, registry):
    if registry is None:
        return [], "the job register could not be read", False
    tokens = [str(t).lower() for t in ev.get("streets", []) if t]
    if not tokens:
        return [], "the evidence names no site", True
    def bare(text):
        words = re.sub(r"[^a-z0-9 ]", " ", str(text).lower()).split()
        drop = {"road", "rd", "street", "st", "avenue", "ave", "lane", "ln", "close",
                "way", "court", "drive", "gardens", "place", "square", "crescent",
                "mews", "park", "hill", "walk", "terrace"}
        return " ".join(w for w in words if w not in drop and not w.isdigit())
    hits = []
    for ref, site in registry.items():
        site_bare = bare(site)
        if not site_bare:
            continue
        for token in tokens:
            token_bare = bare(token)
            if token_bare and (token_bare in site_bare or site_bare in token_bare):
                hits.append(ref)
    return sorted(set(hits)), ("the register's own site name matches" if hits else
                               "no registered site matches these words"), True






def classify_lanes(evidence):
    """REQUIRED / USEFUL / OPTIONAL, mechanically, from what the case IS.

    12 August 2026. Judgement must not wait for every possible lane: an
    unavailable OPTIONAL source never forces UNRESOLVED, an unavailable
    REQUIRED source always does. The classes come from the settled workflow
    shapes — billing evidence makes Xero required; photo evidence makes the
    photo register required — never from a guess.
    """
    blob = " ".join(str(evidence.get(k, "")) for k in ("subject", "text")).lower()
    billing = any(w in blob for w in ("invoice", "inv-", "remittance", "paid", "payment",
                                      "quote", "diagnostic", "estimate", "statement"))
    photo = any(w in blob for w in ("photo", "image", ".jpg", ".heic", "picture"))
    classes = {
        "lane0_settled_answer": "REQUIRED",
        "lane1_job_ref": "REQUIRED",
        "lane2_gra_sites": "REQUIRED",
        "lane3_project_folders": "OPTIONAL",
        "lane4_xero": "REQUIRED" if billing else "USEFUL",
        "lane5_mail": "REQUIRED",
        "lane6_downloads": "OPTIONAL",
        "lane7_photo_register": "REQUIRED" if photo else "OPTIONAL",
        "lane8_address_tokens": "USEFUL",
    }
    return classes


def lane_freshness(lane):
    """When a lane's data was last true, for the sources whose truth ages."""
    import time
    if lane == "lane4_xero" and XERO_MIRROR.exists():
        as_of = XERO_MIRROR.stat().st_mtime
        return {"data_as_of": time.strftime("%Y-%m-%d", time.localtime(as_of)),
                "fresh_enough": (time.time() - as_of) < 7 * 86400}
    if lane == "lane0_settled_answer" and CANON_SNAPSHOT.exists():
        as_of = CANON_SNAPSHOT.stat().st_mtime
        return {"data_as_of": time.strftime("%Y-%m-%d", time.localtime(as_of)),
                "fresh_enough": (time.time() - as_of) < 2 * 86400}
    if lane == "lane5_mail":
        return {"data_as_of": "live", "fresh_enough": True}
    return None

def lane_runners(canon, registry):
    """ONE map of lane name to runner, shared by every entry path."""
    return {
        "lane0_settled_answer": lambda ev: lane0_settled_answer(ev, canon),
        "lane1_job_ref": lambda ev: lane1_job_ref(ev, registry),
        "lane2_gra_sites": lane2_gra_sites,
        "lane3_project_folders": lane3_project_folders,
        "lane4_xero": lane4_xero,
        "lane5_mail": lambda ev: lane5_mail(ev, registry),
        "lane6_downloads": lambda ev: lane6_downloads(ev, registry),
        "lane7_photo_register": lambda ev: lane7_photo_register(ev, registry),
        "lane8_address_tokens": lambda ev: lane8_address_tokens(ev, registry),
    }

def run(evidence):
    order, order_from = lane_order()
    registry = known_jobs()
    try:
        canon = ladder.load_canon(CANON_SNAPSHOT)
    except Exception:
        canon = None

    runners = lane_runners(canon, registry)

    result = {"lane_order_from": order_from, "lanes_run": [], "lanes_unreachable": [],
              "hits": {}, "job_ref": None, "confidence": None, "reason": None,
              "settled": None}

    for lane in order:
        runner = runners.get(lane)
        if runner is None:
            result["lanes_unreachable"].append({"lane": lane, "why": "no runner for this lane here"})
            continue
        hits, note, reachable = runner(evidence)
        if not reachable:
            result["lanes_unreachable"].append({"lane": lane, "why": note})
            continue
        result["lanes_run"].append({"lane": lane, "found": hits, "note": note})
        if hits:
            result["hits"][lane] = hits
        # STEP 0 IS A VETO, NOT A VOTE. A settled answer stops the ladder.
        if lane == "lane0_settled_answer" and hits:
            result.update(job_ref=hits[0], confidence="settled", settled=note,
                          reason="Lee has already settled this; the lanes were not needed.")
            return result

    _judge(result)
    return result


def _judge(result):
    """The shared verdict: never single-field, a disagreement goes to Lee."""
    agreement = {}
    for lane, hits in result["hits"].items():
        for ref in hits:
            agreement.setdefault(ref, []).append(lane)
    if not agreement:
        result["reason"] = "no lane found a job. This one is unresolved."
        return result
    best = sorted(agreement.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    top_ref, top_lanes = best[0]
    tied = [r for r, lanes in best if len(lanes) == len(top_lanes)]
    if len(tied) > 1:
        result["reason"] = ("the lanes disagree: %s. A disagreement goes to Lee, never to a guess."
                            % ", ".join(tied))
        return result
    if len(top_lanes) >= 2:
        # Agreement must be INDEPENDENT. lane4 matching only on street words
        # and lane8 matching the same street words is ONE field twice — the
        # Filipa / Victoria Gardens false link, 14 August 2026. A sender-based
        # lane4 hit, or any third lane, keeps the agreement real.
        same_field = (set(top_lanes) <= {"lane4_xero", "lane8_address_tokens"}
                      and LANE4_BASIS.get(top_ref, "site-words") == "site-words")
        if same_field:
            result["reason"] = ("lane4_xero and lane8_address_tokens both rest on the same "
                                "site words for %s — one field is never an identity. "
                                "This one is unresolved." % top_ref)
            return result
        result.update(job_ref=top_ref, confidence="corroborated",
                      reason="%d lanes agree: %s" % (len(top_lanes), ", ".join(top_lanes)))
        return result
    if "lane1_job_ref" in top_lanes:
        result.update(job_ref=top_ref, confidence="named-and-registered",
                      reason="the evidence itself names this job and the register holds it")
        return result
    result["reason"] = ("only %s names %s, and one lane is never an identity. "
                        "This one is unresolved." % (top_lanes[0], top_ref))
    return result




def run_streaming(evidence, emit):
    """The same run, but each lane's outcome is emitted the moment it exists.

    Built for the identity evidence modal, 12 August 2026: Lee watches the
    search happen — WAITING, READING, READ / UNAVAILABLE — instead of taking a
    finished verdict on trust. The rules live in the SAME lanes and the SAME
    _judge as run(); nothing is restated.
    """
    order, order_from = lane_order()
    emit({"event": "start", "lane_order_from": order_from, "lanes": order})
    registry = known_jobs()
    try:
        canon = ladder.load_canon(CANON_SNAPSHOT)
    except Exception:
        canon = None
    runners = lane_runners(canon, registry)
    result = {"lane_order_from": order_from, "lanes_run": [], "lanes_unreachable": [],
              "hits": {}, "job_ref": None, "confidence": None, "reason": None, "settled": None}
    classes = classify_lanes(evidence)
    missing_required = []
    stale_required = []
    for lane in order:
        cls = classes.get(lane, "OPTIONAL")
        fresh = lane_freshness(lane)
        if cls == "OPTIONAL":
            # Judgement does not wait for every possible lane. An optional lane
            # is offered as GO LOOK, never run automatically and never able to
            # force UNRESOLVED by being unreachable.
            emit({"event": "lane", "lane": lane, "state": "not-tried", "class": cls,
                  "note": "optional for this kind of case — GO LOOK runs it on demand"})
            continue
        emit({"event": "lane", "lane": lane, "state": "reading", "class": cls})
        runner = runners.get(lane)
        if runner is None:
            result["lanes_unreachable"].append({"lane": lane, "why": "no runner for this lane here"})
            emit({"event": "lane", "lane": lane, "state": "unavailable", "class": cls, "note": "no runner here"})
            if cls == "REQUIRED":
                missing_required.append(lane)
            continue
        hits, note, reachable = runner(evidence)
        if not reachable:
            result["lanes_unreachable"].append({"lane": lane, "why": note})
            emit({"event": "lane", "lane": lane, "state": "unavailable", "class": cls, "note": note})
            if cls == "REQUIRED":
                missing_required.append(lane)
            continue
        state = "read"
        if fresh and not fresh["fresh_enough"]:
            # A STALE SOURCE NEVER WEARS A PLAIN TICK. Its data has a date, and
            # for a current case it cannot support "no match" — only "no match
            # in data current to <date>".
            state = "read-stale"
            if cls == "REQUIRED" and not hits:
                stale_required.append((lane, fresh["data_as_of"]))
        result["lanes_run"].append({"lane": lane, "found": hits, "note": note})
        if hits:
            result["hits"][lane] = hits
        emit({"event": "lane", "lane": lane, "state": state, "class": cls,
              "found": hits, "note": note, **({"freshness": fresh} if fresh else {})})
        if lane == "lane0_settled_answer" and hits:
            result.update(job_ref=hits[0], confidence="settled", settled=note,
                          reason="Lee has already settled this; the lanes were not needed.")
            emit({"event": "verdict", "job_ref": result["job_ref"],
                  "confidence": result["confidence"], "reason": result["reason"],
                  "settled": result["settled"]})
            return result
    _judge(result)
    # AN UNAVAILABLE OR STALE REQUIRED SOURCE FORCES UNRESOLVED. A no-match
    # verdict reached without a required source is not a verdict.
    if result["job_ref"] is None:
        qualifiers = []
        if missing_required:
            qualifiers.append("required source(s) unavailable: %s" % ", ".join(missing_required))
        for lane, as_of in stale_required:
            qualifiers.append("%s data is only current to %s, so 'no match' cannot be said for a current case" % (lane, as_of))
        if qualifiers:
            result["reason"] = (result["reason"] or "") + " UNRESOLVED, and it must stay so: " + "; ".join(qualifiers) + "."
    emit({"event": "verdict", "job_ref": result["job_ref"], "confidence": result["confidence"],
          "reason": result["reason"]})
    return result


def run_one_lane(evidence, lane):
    """GO LOOK: run exactly one lane, deterministically, and say what it found."""
    registry = known_jobs()
    try:
        canon = ladder.load_canon(CANON_SNAPSHOT)
    except Exception:
        canon = None
    runner = lane_runners(canon, registry).get(lane)
    if runner is None:
        return {"lane": lane, "state": "unavailable", "note": "no such lane"}
    hits, note, reachable = runner(evidence)
    return {"lane": lane, "state": "read" if reachable else "unavailable",
            "found": hits, "note": note}


if __name__ == "__main__":
    try:
        evidence = json.load(sys.stdin)
    except Exception as err:
        print(json.dumps({"error": f"the evidence could not be read: {err}"}))
        raise SystemExit(2)
    if "--stream" in sys.argv:
        run_streaming(evidence, lambda e: (sys.stdout.write(json.dumps(e) + "\n"), sys.stdout.flush()))
        raise SystemExit(0)
    if "--only-lane" in sys.argv:
        lane = sys.argv[sys.argv.index("--only-lane") + 1]
        print(json.dumps(run_one_lane(evidence, lane)))
        raise SystemExit(0)
    # A product with a board full of cards asks once, not once per card: the
    # registry, the canon and the mail index are then read a single time.
    if isinstance(evidence, list):
        print(json.dumps([dict(run(one), id=one.get("id")) for one in evidence]))
    else:
        print(json.dumps(run(evidence)))
