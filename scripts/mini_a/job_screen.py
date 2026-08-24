#!/usr/bin/env python3
"""
job_screen.py -- smallest durable Image Plane job screen for 1892-26.

One job page. stdlib http.server only (same family as flip_server.py).
Does not start flip_server, does not touch .env.flip, does not bind 8787.
Binds 100.94.96.32:8789 so flip_server can still own 8788 later.

The grid reads REAL CABINET ROWS ONLY: ~/image-plane/cabinet/1892-26.
The incoming folder never pads the grid (closed 24 Aug 2026 — it used
to be preferred over the cabinet). visual_observations rows for
job_ref=1892-26 enrich the cards when LeeOSplus is reachable via
.env.flip; if the DB is down the cabinet files still render with the
MATCH/dictate seeds, marked unresolved.

Identity: job 1892-26 (6 Pancras Square) is Lee's explicit ruling,
24 Aug 2026. NOT ladder-confirmed (every ladder lane found nothing).
GRA entity id stays empty. Do not create a GRA site.

Runs under launchd: ~/Library/LaunchAgents/com.leeos.image-plane-job-screen.plist
(label com.leeos.image-plane-job-screen). Manual restart:
  launchctl kickstart -k gui/$(id -u)/com.leeos.image-plane-job-screen
"""
from __future__ import print_function

import json
import os
import re
import sys
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

JOB_REF = "1892-26"
SITE_NAME = "6 Pancras Square"
ALBUM_LABEL = "6 Pancras Diagnostic 18/7/26"
VISIT_PHASE = "diagnostic"
CAPTURE_DAY = "2026-08-18"
BIND_HOST = "100.94.96.32"
PORT = 8789

ROOT = os.path.expanduser("~/image-plane")
JOB_DIR = os.path.join(ROOT, "incoming", "google", JOB_REF)
# The cabinet is the one source for the grid. Incoming never pads it.
CABINET_DIR = os.path.join(ROOT, "cabinet", JOB_REF)
ORIG_DIR = os.path.join(CABINET_DIR, "originals")
THUMB_DIR = os.path.join(CABINET_DIR, "thumbs")
MATCH_PATH = os.path.join(JOB_DIR, "MATCH-1892-26.txt")
SOURCE_PATH = os.path.join(JOB_DIR, "SOURCE.txt")
STATE_PATH = os.path.join(JOB_DIR, "job_screen_state.json")
ENV_PATH = os.path.join(ROOT, ".env.flip")
DIAGNOSTIC_PDF = os.path.join(JOB_DIR, "1892-26-diagnostic.pdf")
PACKS_DIR = os.path.join(JOB_DIR, "packs")

# Identity of this job, recorded as ruled 24 Aug 2026. Not a judgement.
IDENTITY = {
    "job_ref": JOB_REF,
    "site": SITE_NAME,
    "ruling": "Lee's explicit ruling, 24 Aug 2026",
    "match_method": "lee_answer",
    "ladder_confirmed": False,
    "gra_entity_id": "",
}

STEM_RE = re.compile(r"^(IMG_\d+)", re.I)
SAFE_NAME_RE = re.compile(r"^IMG_\d+\.(HEIC|MOV|JPG|JPEG|heic|mov|jpg|jpeg)$")
PACK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
PACK_FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]*\.(jpg|jpeg|png|txt|pdf)$", re.I)


# --------------------------------------------------------------------------
# MATCH + Lee dictate seeds (advisory; Lee words stay)
# --------------------------------------------------------------------------

def _seed(location, component, condition, caption, action="", before_after="", flags=None):
    return {
        "location": location,
        "component": component,
        "condition": condition,
        "action": action,
        "before_after": before_after,
        "caption": caption,
        "flags": flags or [],
    }


# Combined from MATCH-1892-26.txt (picture-to-Lee-note). Videos stay unwatched.
# IMG_1898 is indoor moss wall, not roof evidence.
SEEDS = {
    "IMG_1841": _seed(
        "sedum roof",
        "loose-laid sedum; log piles / hibernacula",
        "wide dry loose-laid sedum",
        "Wide dry loose-laid sedum roof. Log piles / hibernacula.",
    ),
    "IMG_1842": _seed(
        "sedum roof",
        "loose-laid sedum",
        "wide dry loose-laid sedum",
        "Wide dry loose-laid sedum roof.",
    ),
    "IMG_1843": _seed(
        "sedum roof",
        "depth hole + ruler",
        "~130mm substrate depth",
        "Depth hole + ruler (~130mm).",
    ),
    "IMG_1844": _seed(
        "sedum roof",
        "recycled aggregate / dry compost",
        "light recycled aggregate / dry compost in hand",
        "Light recycled aggregate / dry compost in hand and open.",
    ),
    "IMG_1845": _seed(
        "sedum roof",
        "recycled aggregate / dry compost",
        "light recycled aggregate / dry compost in hand",
        "Light recycled aggregate / dry compost in hand and open.",
    ),
    "IMG_1846": _seed(
        "sedum roof",
        "drainage tray + filter fleece",
        "fleece pulled back; holes visible",
        "Drainage tray + filter fleece pulled back (holes).",
        action="filter fleece pulled back",
    ),
    "IMG_1847": _seed(
        "sedum roof",
        "recycled aggregate / dry compost",
        "light recycled aggregate / dry compost in hand",
        "Light recycled aggregate / dry compost in hand and open.",
    ),
    "IMG_1849": _seed(
        "sedum roof",
        "log piles / hibernacula",
        "",
        "Log piles / hibernacula.",
    ),
    "IMG_1850": _seed(
        "sedum roof",
        "loose-laid sedum; log piles / hibernacula",
        "wide dry loose-laid sedum",
        "Wide dry loose-laid sedum roof. Log piles / hibernacula.",
    ),
    "IMG_1851": _seed(
        "sedum roof",
        "sedum + stones / ballast",
        "",
        "Sedum + stones / ballast.",
    ),
    "IMG_1852": _seed(
        "sedum roof / edge",
        "sedum + stones / ballast; edge divider",
        "edge / divider issue at stone vs plant",
        "Sedum + stones / ballast. Edge / divider issue at stone vs plant.",
    ),
    "IMG_1855": _seed(
        "sedum roof",
        "depth hole + ruler",
        "~55mm substrate depth",
        "Depth hole + ruler (~55mm).",
    ),
    "IMG_1858": _seed(
        "terrace",
        "habitats / mobile planters",
        "",
        "Terrace for habitats / mobile planters.",
    ),
    "IMG_1860": _seed(
        "sedum roof",
        "sedum + stones / ballast",
        "",
        "Sedum + stones / ballast.",
    ),
    "IMG_1866": _seed(
        "plant-bed roof (floor not labelled)",
        "plant-bed",
        "failed / sparse",
        "Plant-bed roof looking failed/sparse (floor not labelled in picture).",
    ),
    "IMG_1869": _seed(
        "sedum roof",
        "sedum + stones / ballast",
        "",
        "Sedum + stones / ballast.",
    ),
    "IMG_1870": _seed(
        "sedum roof",
        "loose-laid sedum; log piles / hibernacula",
        "wide dry loose-laid sedum",
        "Wide dry loose-laid sedum roof. Log piles / hibernacula.",
    ),
    "IMG_1872": _seed(
        "sedum roof",
        "loose-laid sedum",
        "wide dry loose-laid sedum",
        "Wide dry loose-laid sedum roof.",
    ),
    "IMG_1874": _seed(
        "",
        "video",
        "unwatched",
        "Video not watched.",
        flags=["unwatched", "video"],
    ),
    "IMG_1878": _seed(
        "sedum roof",
        "vent / drain + mesh stones",
        "",
        "Vent / drain + mesh stones.",
    ),
    "IMG_1880": _seed(
        "sedum roof",
        "kit on roof",
        "",
        "Kit sitting on the roof.",
    ),
    "IMG_1882": _seed(
        "sedum roof",
        "kit on roof",
        "",
        "Kit sitting on the roof.",
    ),
    "IMG_1886": _seed(
        "plant-bed roof / ledge (floor not labelled)",
        "plant-bed; ruler and trowel",
        "failed / sparse",
        "Plant-bed roof looking failed/sparse (floor not labelled). Ruler and trowel on the ledge.",
    ),
    "IMG_1888": _seed(
        "ledge",
        "depth hole + ruler; trowel",
        "~80mm substrate depth",
        "Depth hole + ruler (~80mm). Ruler and trowel on the ledge.",
    ),
    "IMG_1893": _seed(
        "",
        "video",
        "unwatched",
        "Video not watched.",
        flags=["unwatched", "video"],
    ),
    "IMG_1896": _seed(
        "terrace",
        "habitats / mobile planters",
        "",
        "Terrace for habitats / mobile planters.",
    ),
    "IMG_1898": _seed(
        "indoor",
        "moss wall / map pin",
        "not roof evidence",
        "Indoor moss wall / map pin — not a roof note.",
        flags=["not_roof", "indoor"],
    ),
}


# --------------------------------------------------------------------------
# Tiny helpers
# --------------------------------------------------------------------------

def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_env(path):
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                v = v[1:-1]
            out[k.strip()] = v
    return out


def _load_state():
    blank = {"selection": [], "approvals": {}}
    if not os.path.exists(STATE_PATH):
        return blank
    try:
        data = json.load(open(STATE_PATH))
    except Exception:
        return blank
    if not isinstance(data, dict):
        return blank
    sel = data.get("selection") or []
    appr = data.get("approvals") or {}
    if not isinstance(sel, list):
        sel = []
    if not isinstance(appr, dict):
        appr = {}
    out = dict(data)  # keep every other stored key (findings review state etc.)
    out["selection"] = [str(x) for x in sel]
    out["approvals"] = appr
    return out


def _save_state(state):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, STATE_PATH)


def _stem(name):
    m = STEM_RE.match(os.path.basename(name) or "")
    return m.group(1) if m else os.path.splitext(os.path.basename(name))[0]


def _http(method, url, headers=None, data=None, timeout=20):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.getheaders()), resp.read()
    except urllib.error.HTTPError as e:
        body = e.read()
        return e.code, dict(e.headers or {}), body


def fetch_visual_observations():
    """Live rows for this job only. Never logs keys. Empty list on any failure."""
    env = _load_env(ENV_PATH)
    url = os.environ.get("LEEOSPLUS_URL") or env.get("LEEOSPLUS_URL")
    key = os.environ.get("LEEOSPLUS_SERVICE_KEY") or env.get("LEEOSPLUS_SERVICE_KEY")
    if not url or not key:
        return [], "no-env"
    url = url.rstrip("/")
    headers = {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Range-Unit": "items",
        "Range": "0-199",
    }
    q = "select=*&job_ref=eq.%s&order=taken_at.asc.nullslast" % JOB_REF
    try:
        status, _, body = _http("GET", url + "/rest/v1/visual_observations?" + q, headers=headers)
    except Exception as e:
        return [], "db-error:%s" % type(e).__name__
    if status not in (200, 206):
        return [], "db-http-%s" % status
    try:
        rows = json.loads(body or b"[]")
    except Exception:
        return [], "db-bad-json"
    return rows, "db-ok"


def patch_row_approved(row_id):
    """Mark GRA-eligible on the spine without flipping public."""
    env = _load_env(ENV_PATH)
    url = os.environ.get("LEEOSPLUS_URL") or env.get("LEEOSPLUS_URL")
    key = os.environ.get("LEEOSPLUS_SERVICE_KEY") or env.get("LEEOSPLUS_SERVICE_KEY")
    if not url or not key or not row_id:
        return False, "no-db"
    url = url.rstrip("/")
    headers = {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    # Pull current tags, add approved. Do not touch is_public.
    try:
        q = "select=id,tags,is_public&id=eq.%s" % urllib.parse.quote(str(row_id))
        status, _, body = _http("GET", url + "/rest/v1/visual_observations?" + q, headers=headers)
        if status not in (200, 206):
            return False, "get-%s" % status
        rows = json.loads(body or b"[]")
        tags = list((rows[0].get("tags") or []) if rows else [])
        if "approved" not in tags:
            tags.append("approved")
        patch = {"tags": tags}
        status, _, body = _http(
            "PATCH",
            url + "/rest/v1/visual_observations?id=eq.%s" % urllib.parse.quote(str(row_id)),
            headers=headers,
            data=json.dumps(patch).encode("utf-8"),
        )
        if status not in (200, 204):
            return False, "patch-%s" % status
        return True, "ok"
    except Exception as e:
        return False, type(e).__name__


def _parse_maybe_json(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s or s[0] not in "{[":
        return None
    try:
        obj = json.loads(s)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _first_text(*vals):
    for v in vals:
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            v = ", ".join(str(x) for x in v if x)
        s = str(v).strip()
        if s:
            return s
    return ""


def list_cabinet_files():
    """The one file source for the grid: cabinet originals only."""
    files = []
    if not os.path.isdir(ORIG_DIR):
        return files
    for name in sorted(os.listdir(ORIG_DIR)):
        if not STEM_RE.match(name):
            continue
        path = os.path.join(ORIG_DIR, name)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext not in (".heic", ".mov", ".jpg", ".jpeg"):
            continue
        files.append(name)
    return files


def build_payload():
    state = _load_state()
    approvals = state.get("approvals") or {}
    selection = state.get("selection") or []
    db_rows, db_status = fetch_visual_observations()

    by_stem = {}
    for row in db_rows:
        paths = [
            row.get("original_path") or "",
            row.get("picture_path") or "",
            row.get("thumb_path") or "",
        ]
        stem = None
        for p in paths:
            stem = _stem(p)
            if stem and stem.startswith("IMG_"):
                break
        if stem and stem.startswith("IMG_"):
            by_stem.setdefault(stem, row)
        # Rows with no cabinet file never pad the grid.

    # Cabinet-only grid: one card per cabinet original, enriched by its
    # VO row when one matches. Nothing else may add a card.
    items = []
    cabinet = list_cabinet_files()
    for name in cabinet:
        stem = _stem(name)
        items.append(_card_for(stem, name, by_stem.get(stem), approvals))

    items.sort(key=lambda c: c["id"])
    return {
        "job_ref": JOB_REF,
        "site": SITE_NAME,
        "album": ALBUM_LABEL,
        "visit_phase": VISIT_PHASE,
        "capture_date": CAPTURE_DAY,
        "identity": dict(IDENTITY),
        "source": "cabinet-only",
        "db_status": db_status,
        "db_rows": len(db_rows),
        "cabinet_files": len(cabinet),
        "selection": selection,
        "items": items,
    }


def _card_for(stem, filename, row, approvals):
    ext = os.path.splitext(filename)[1].lower()
    kind = "video" if ext == ".mov" else "photo"
    seed = SEEDS.get(stem) or _seed("", "", "", "")
    row = row or {}
    parsed = _parse_maybe_json(row.get("description")) or {}
    raw = _parse_maybe_json(row.get("raw_response")) or {}

    location = _first_text(
        parsed.get("location"), parsed.get("roof_zone"), parsed.get("zone"),
        raw.get("location"), raw.get("roof_zone"),
        row.get("building"), seed.get("location"),
    )
    component = _first_text(
        parsed.get("component"), parsed.get("subject"),
        raw.get("component"), raw.get("subject"),
        seed.get("component"),
    )
    condition = _first_text(
        parsed.get("condition"), parsed.get("defect"),
        raw.get("condition"), raw.get("defect"),
        seed.get("condition"),
    )
    action = _first_text(
        parsed.get("action"), parsed.get("action_required"), parsed.get("action_completed"),
        raw.get("action"), seed.get("action"),
    )
    before_after = _first_text(
        parsed.get("before_after"), parsed.get("relationship"),
        raw.get("before_after"), seed.get("before_after"),
    )
    caption = _first_text(
        row.get("lee_note"), row.get("public_caption"), row.get("description"),
        parsed.get("caption"), parsed.get("observation"),
        seed.get("caption"),
    )
    phase = _first_text(row.get("activity"), parsed.get("phase"), VISIT_PHASE)
    taken = _first_text(row.get("taken_at"), row.get("visit_date"), CAPTURE_DAY)

    flags = list(seed.get("flags") or [])
    tags = list(row.get("tags") or [])
    approved_rec = approvals.get(stem) or {}
    approved = bool(approved_rec.get("approved")) or ("approved" in tags)
    is_public = bool(row.get("is_public"))
    if is_public:
        status = "published"
    elif approved:
        status = "approved"
    else:
        status = "private"

    unresolved = not bool(row.get("id"))
    thumb_name = stem + ".jpg"
    has_thumb = os.path.isfile(os.path.join(THUMB_DIR, thumb_name))
    has_original = os.path.isfile(os.path.join(ORIG_DIR, filename))

    return {
        "id": stem,
        "filename": filename,
        "kind": kind,
        "job_ref": JOB_REF,
        "site": SITE_NAME,
        "album": ALBUM_LABEL,
        "capture_date": taken,
        "visit_phase": phase,
        "location": location,
        "component": component,
        "condition": condition,
        "action": action,
        "before_after": before_after,
        "caption": caption,
        "status": status,
        "approved": approved,
        "is_public": is_public,
        "unresolved": unresolved,
        "flags": flags,
        "tags": tags,
        "row_id": row.get("id"),
        "thumb": ("/thumb/" + thumb_name) if has_thumb else "",
        "media": ("/media/" + filename) if has_original else "",
        "has_thumb": has_thumb,
        "has_original": has_original,
    }


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

def _html_esc(s):
    return (str(s or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _static_cards_html(payload):
    parts = []
    for it in payload.get("items") or []:
        flags = "".join(
            '<span class="badge %s">%s</span>' % (_html_esc(f), _html_esc(f.replace("_", " ")))
            for f in (it.get("flags") or [])
        )
        if it.get("kind") == "video":
            media = (
                '<video controls playsinline preload="metadata" poster="%s" src="%s"></video>'
                % (_html_esc(it.get("thumb")), _html_esc(it.get("media")))
            )
        elif it.get("thumb"):
            media = '<img src="%s" alt="%s">' % (_html_esc(it.get("thumb")), _html_esc(it.get("id")))
        else:
            media = '<div class="empty">no thumb</div>'
        unres = " unresolved" if it.get("unresolved") else ""
        unres_badge = '<span class="badge unresolved">unresolved</span>' if it.get("unresolved") else ""
        vid_badge = '<span class="badge">video</span>' if it.get("kind") == "video" else ""
        parts.append(
            '<article class="card%s" data-id="%s">'
            '<div class="mediawrap">'
            '<input class="pick" type="checkbox" data-id="%s">'
            "%s"
            '<div class="badges">%s<span class="badge %s">%s</span>%s%s</div>'
            "</div>"
            '<div class="body">'
            '<div class="fn">%s</div>'
            '<div class="kv">capture <b>%s</b> · %s</div>'
            '<div class="kv">zone <b>%s</b></div>'
            '<div class="kv">subject <b>%s</b></div>'
            '<div class="kv">condition <b>%s</b></div>'
            '<div class="kv">action <b>%s</b></div>'
            '<div class="kv">before/after <b>%s</b></div>'
            '<div class="caption">%s</div>'
            "</div></article>"
            % (
                unres, _html_esc(it.get("id")), _html_esc(it.get("id")), media,
                unres_badge, _html_esc(it.get("status")), _html_esc(it.get("status")),
                vid_badge, flags,
                _html_esc(it.get("filename")),
                _html_esc(it.get("capture_date")), _html_esc(it.get("visit_phase")),
                _html_esc(it.get("location") or "—"),
                _html_esc(it.get("component") or "—"),
                _html_esc(it.get("condition") or "—"),
                _html_esc(it.get("action") or "—"),
                _html_esc(it.get("before_after") or "—"),
                _html_esc(it.get("caption")),
            )
        )
    return "\n".join(parts) if parts else '<div class="empty">No incoming files yet.</div>'


def render_page():
    try:
        payload = build_payload()
        cards = _static_cards_html(payload)
        dbmeta = "source: cabinet-only · %s · %s VO rows · %s cabinet files" % (
            payload.get("db_status"), payload.get("db_rows"), payload.get("cabinet_files")
        )
    except Exception:
        traceback.print_exc()
        cards = '<div class="empty">Failed to build job cards.</div>'
        dbmeta = "source: error"
    return (PAGE
            .replace('<div id="grid" class="grid"></div>',
                     '<div id="grid" class="grid">\n' + cards + '\n</div>')
            .replace('<span id="dbmeta"></span>',
                     '<span id="dbmeta">' + _html_esc(dbmeta) + "</span>"))


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>1892-26 · 6 Pancras Square</title>
<style>
:root { --bg:#12110f; --card:#1c1a17; --ink:#efe6d6; --muted:#9a8f7c; --line:#3a342b; --acc:#c4a35a; --ok:#7d9a5a; --warn:#c47a4a; --bad:#a35a5a; }
* { box-sizing:border-box; }
html,body { margin:0; background:var(--bg); color:var(--ink); font:14px/1.4 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif; }
header { padding:18px 20px 10px; border-bottom:1px solid var(--line); position:sticky; top:0; background:var(--bg); z-index:5; }
h1 { margin:0; font-size:20px; font-weight:620; letter-spacing:.02em; }
.sub { color:var(--muted); margin-top:4px; }
.meta { display:flex; flex-wrap:wrap; gap:8px 16px; margin-top:8px; color:var(--muted); font-size:12px; }
.toolbar { display:flex; flex-wrap:wrap; gap:8px; align-items:center; padding:10px 20px; border-bottom:1px solid var(--line); position:sticky; top:86px; background:#161410; z-index:4; }
input[type=search], select { background:#0e0d0b; color:var(--ink); border:1px solid var(--line); border-radius:6px; padding:6px 8px; }
input[type=search] { min-width:220px; flex:1; }
button { background:var(--acc); color:#1a1408; border:0; border-radius:6px; padding:7px 12px; font-weight:650; cursor:pointer; }
button.ghost { background:transparent; color:var(--ink); border:1px solid var(--line); }
button:disabled { opacity:.45; cursor:not-allowed; }
#selcount { color:var(--muted); min-width:7em; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:12px; padding:16px 20px 40px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px; overflow:hidden; display:flex; flex-direction:column; }
.card.hidden { display:none; }
.card.selected { border-color:var(--acc); box-shadow:0 0 0 1px var(--acc) inset; }
.card.unresolved { border-style:dashed; }
.mediawrap { position:relative; background:#000; aspect-ratio:4/3; }
.mediawrap img, .mediawrap video { width:100%; height:100%; object-fit:cover; display:block; }
.pick { position:absolute; top:8px; left:8px; width:18px; height:18px; }
.badges { position:absolute; top:8px; right:8px; display:flex; gap:4px; flex-wrap:wrap; justify-content:flex-end; }
.badge { font-size:10px; padding:2px 6px; border-radius:999px; background:#2a261f; color:var(--ink); text-transform:uppercase; letter-spacing:.04em; }
.badge.private { background:#2a261f; color:var(--muted); }
.badge.approved { background:#2a3a1c; color:#cfe3b0; }
.badge.published { background:#1c2f3a; color:#b7d4e3; }
.badge.unresolved { background:#3a2618; color:#f0c09a; }
.badge.unwatched, .badge.not_roof { background:#3a1c1c; color:#f0b0b0; }
.body { padding:10px 12px 12px; display:flex; flex-direction:column; gap:4px; }
.fn { font-weight:650; }
.kv { color:var(--muted); font-size:12px; }
.kv b { color:var(--ink); font-weight:550; }
.caption { font-size:13px; margin-top:4px; }
.empty { padding:40px 20px; color:var(--muted); }
</style>
</head>
<body>
<header>
  <h1>1892-26 · 6 Pancras Square</h1>
  <div class="sub">Image Plane job screen · internal GRA-eligible approve, not public · <a href="/job/1892-26/1892-26-diagnostic.pdf" style="color:#c4a35a">diagnostic PDF</a> · <a href="/job/1892-26/packs/drainage-v1/" style="color:#c4a35a">drainage pack v1</a></div>
  <div class="meta">
    <span>album: 6 Pancras Diagnostic 18/7/26</span>
    <span>visit: diagnostic</span>
    <span>capture: 18 Aug 2026</span>
    <span>identity: Lee's explicit ruling (24 Aug 2026) · not ladder-confirmed · GRA entity: none</span>
    <span id="dbmeta"></span>
  </div>
</header>
<div class="toolbar">
  <input type="search" id="q" placeholder="Search filename, zone, component, condition, caption">
  <select id="status"><option value="">all status</option><option>private</option><option>approved</option><option>published</option></select>
  <select id="kind"><option value="">all media</option><option>photo</option><option>video</option></select>
  <select id="zone"><option value="">all locations</option></select>
  <select id="unres"><option value="">all rows</option><option value="unresolved">unresolved only</option><option value="resolved">has VO row</option></select>
  <button class="ghost" id="all">select visible</button>
  <button class="ghost" id="none">clear</button>
  <span id="selcount">0 selected</span>
  <button id="approve">Approve selection</button>
</div>
<div id="grid" class="grid"></div>
<script>
const JOB = "1892-26";
const LS = "ip.job.1892-26.selection";
let DATA = {items:[], selection:[]};
const selected = new Set();

function loadLocal() {
  try { return JSON.parse(localStorage.getItem(LS) || "[]"); } catch (e) { return []; }
}
function saveLocal() {
  localStorage.setItem(LS, JSON.stringify(Array.from(selected)));
}
function esc(s) {
  return String(s || "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function badge(cls, text) { return `<span class="badge ${cls}">${esc(text)}</span>`; }

function render() {
  const q = document.getElementById("q").value.trim().toLowerCase();
  const st = document.getElementById("status").value;
  const kind = document.getElementById("kind").value;
  const zone = document.getElementById("zone").value;
  const unres = document.getElementById("unres").value;
  const grid = document.getElementById("grid");
  grid.innerHTML = "";
  let shown = 0;
  (DATA.items || []).forEach(it => {
    const hay = [it.id, it.filename, it.location, it.component, it.condition, it.action, it.before_after, it.caption, it.status, it.visit_phase, (it.flags||[]).join(" ")].join(" ").toLowerCase();
    let hide = false;
    if (q && hay.indexOf(q) < 0) hide = true;
    if (st && it.status !== st) hide = true;
    if (kind && it.kind !== kind) hide = true;
    if (zone && it.location !== zone) hide = true;
    if (unres === "unresolved" && !it.unresolved) hide = true;
    if (unres === "resolved" && it.unresolved) hide = true;
    const card = document.createElement("article");
    card.className = "card" + (it.unresolved ? " unresolved" : "") + (selected.has(it.id) ? " selected" : "");
    card.dataset.id = it.id;
    if (hide) card.classList.add("hidden");
    else shown += 1;
    const flags = (it.flags || []).map(f => badge(f, f.replace("_"," "))).join("");
    const media = it.kind === "video"
      ? `<video controls playsinline preload="metadata" poster="${esc(it.thumb)}" src="${esc(it.media)}"></video>`
      : (it.thumb ? `<img src="${esc(it.thumb)}" alt="${esc(it.id)}">` : `<div class="empty">no thumb</div>`);
    card.innerHTML = `
      <div class="mediawrap">
        <input class="pick" type="checkbox" ${selected.has(it.id) ? "checked" : ""} data-id="${esc(it.id)}">
        ${media}
        <div class="badges">
          ${it.unresolved ? badge("unresolved","unresolved") : ""}
          ${badge(it.status, it.status)}
          ${it.kind === "video" ? badge("","video") : ""}
          ${flags}
        </div>
      </div>
      <div class="body">
        <div class="fn">${esc(it.filename)}</div>
        <div class="kv">capture <b>${esc(it.capture_date)}</b> · ${esc(it.visit_phase)}</div>
        <div class="kv">zone <b>${esc(it.location) || "—"}</b></div>
        <div class="kv">subject <b>${esc(it.component) || "—"}</b></div>
        <div class="kv">condition <b>${esc(it.condition) || "—"}</b></div>
        <div class="kv">action <b>${esc(it.action) || "—"}</b></div>
        <div class="kv">before/after <b>${esc(it.before_after) || "—"}</b></div>
        <div class="caption">${esc(it.caption) || ""}</div>
      </div>`;
    grid.appendChild(card);
  });
  if (!shown) grid.innerHTML = '<div class="empty">No items match the current search/filters.</div>';
  document.getElementById("selcount").textContent = selected.size + " selected";
}

function persistSelection() {
  saveLocal();
  fetch("/api/job/1892-26/selection", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ids: Array.from(selected)})
  }).catch(() => {});
}

function fillZones() {
  const sel = document.getElementById("zone");
  const zones = Array.from(new Set((DATA.items||[]).map(i => i.location).filter(Boolean))).sort();
  zones.forEach(z => {
    const o = document.createElement("option");
    o.value = z; o.textContent = z; sel.appendChild(o);
  });
}

async function boot() {
  const res = await fetch("/api/job/1892-26");
  DATA = await res.json();
  const serverSel = DATA.selection || [];
  const localSel = loadLocal();
  (localSel.length ? localSel : serverSel).forEach(id => selected.add(id));
  localSel.forEach(id => selected.add(id));
  serverSel.forEach(id => selected.add(id));
  document.getElementById("dbmeta").textContent =
    "source: cabinet-only · " + (DATA.db_status || "?") + " · " + (DATA.db_rows||0) + " VO rows · " + (DATA.cabinet_files||0) + " cabinet files";
  fillZones();
  render();
  persistSelection();
}

document.getElementById("grid").addEventListener("change", e => {
  const t = e.target;
  if (!t.classList.contains("pick")) return;
  if (t.checked) selected.add(t.dataset.id);
  else selected.delete(t.dataset.id);
  const card = t.closest(".card");
  if (card) card.classList.toggle("selected", t.checked);
  document.getElementById("selcount").textContent = selected.size + " selected";
  persistSelection();
});
["q","status","kind","zone","unres"].forEach(id => {
  document.getElementById(id).addEventListener("input", render);
  document.getElementById(id).addEventListener("change", render);
});
document.getElementById("all").onclick = () => {
  document.querySelectorAll(".card:not(.hidden)").forEach(c => selected.add(c.dataset.id));
  render(); persistSelection();
};
document.getElementById("none").onclick = () => { selected.clear(); render(); persistSelection(); };
document.getElementById("approve").onclick = async () => {
  const ids = Array.from(selected);
  if (!ids.length) return;
  const btn = document.getElementById("approve");
  btn.disabled = true;
  try {
    const res = await fetch("/api/job/1892-26/approve", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ids})
    });
    const out = await res.json();
    DATA = await (await fetch("/api/job/1892-26")).json();
    render();
    btn.textContent = "Approved " + (out.approved || ids.length);
    setTimeout(() => { btn.textContent = "Approve selection"; }, 1600);
  } finally { btn.disabled = false; }
};
boot();
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------
# Findings workspace (24 Aug 2026) — the evidence finding is the object Lee
# reviews, not the photograph. Base findings live in findings_1892_26.json;
# review state (confirm/correct/reject/merge/split/private) lives in
# job_screen_state.json so it survives reload and service restart.
# Machine readings come from qwen_readings.jsonl (qwen3-vl, recorded route).
# --------------------------------------------------------------------------

FINDINGS_PATH = os.path.join(JOB_DIR, "findings_1892_26.json")
QWEN_LEDGER = os.path.join(JOB_DIR, "qwen_readings.jsonl")

STATUS_LABELS = {
    "open": "open",
    "confirmed": "confirmed",
    "corrected": "corrected",
    "rejected": "rejected",
    "private": "kept private",
}


def load_findings_base():
    try:
        with open(FINDINGS_PATH) as f:
            data = json.load(f)
    except Exception:
        return {"findings": [], "sources": {}}
    if not isinstance(data, dict):
        return {"findings": [], "sources": {}}
    return data


def load_qwen_readings():
    out = {}
    if not os.path.exists(QWEN_LEDGER):
        return out
    try:
        with open(QWEN_LEDGER) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("stem"):
                    out[rec["stem"]] = rec
    except Exception:
        pass
    return out


def _findings_state(state):
    fr = state.get("findings_review")
    if not isinstance(fr, dict):
        fr = {}
    edits = state.get("finding_edits")
    if not isinstance(edits, dict):
        edits = {}
    splits = state.get("split_findings")
    if not isinstance(splits, list):
        splits = []
    return fr, edits, splits


def effective_findings():
    """Base findings + split findings, with merge/image edits applied."""
    base = load_findings_base()
    state = _load_state()
    review, edits, splits = _findings_state(state)
    findings = [dict(f) for f in (base.get("findings") or [])]
    for s in splits:
        findings.append({
            "id": s.get("id"),
            "title": s.get("title") or "Split finding",
            "location": s.get("location") or "unknown",
            "images": list(s.get("images") or []),
            "dictate_fragments": [],
            "documents": [],
            "establishes": "Split out of %s by review action." % s.get("from"),
            "uncertain": "",
            "split_from": s.get("from"),
        })
    out = []
    for f in findings:
        fid = f.get("id")
        e = edits.get(fid) or {}
        imgs = [i for i in (f.get("images") or []) if i not in set(e.get("removed_images") or [])]
        for i in (e.get("added_images") or []):
            if i not in imgs:
                imgs.append(i)
        f["images"] = imgs
        f["merged_into"] = e.get("merged_into") or ""
        r = review.get(fid) or {}
        f["status"] = r.get("status") or "open"
        f["review_note"] = r.get("note") or ""
        f["review_at"] = r.get("at") or ""
        out.append(f)
    return base, out


def _stem_file(stem):
    for ext in (".jpg", ".jpeg", ".HEIC", ".heic", ".JPG", ".MOV", ".mov"):
        if os.path.isfile(os.path.join(ORIG_DIR, stem + ext)):
            return stem + ext
    return None


def build_findings_payload():
    base, findings = effective_findings()
    qwen = load_qwen_readings()
    payload_cards = {it["id"]: it for it in build_payload()["items"]}
    for f in findings:
        cards = []
        for stem in f.get("images") or []:
            card = dict(payload_cards.get(stem) or {"id": stem})
            q = qwen.get(stem)
            card["qwen"] = {
                "response": q.get("response"),
                "model": q.get("model"),
                "prompt_version": q.get("prompt_version"),
                "seconds": q.get("seconds"),
                "ts": q.get("ts"),
            } if q else None
            cards.append(card)
        f["cards"] = cards
    read_count = len(qwen)
    return {
        "job_ref": JOB_REF,
        "site": SITE_NAME,
        "identity": dict(IDENTITY),
        "sources": base.get("sources") or {},
        "qwen_read_count": read_count,
        "findings": findings,
    }


def apply_finding_action(data):
    """One review action. Returns (ok, message)."""
    fid = str(data.get("finding_id") or "").strip()
    action = str(data.get("action") or "").strip()
    note = str(data.get("note") or "").strip()
    if not fid or action not in (
            "confirm", "correct", "reject", "private", "reopen", "merge", "split"):
        return False, "bad action"
    state = _load_state()
    review, edits, splits = _findings_state(state)
    now = _utc_now()
    known = {f.get("id") for f in load_findings_base().get("findings") or []}
    known |= {s.get("id") for s in splits}
    if fid not in known:
        return False, "unknown finding"
    if action in ("confirm", "reject", "private", "reopen"):
        status = {"confirm": "confirmed", "reject": "rejected",
                  "private": "private", "reopen": "open"}[action]
        review[fid] = {"status": status, "note": note, "at": now}
    elif action == "correct":
        if not note:
            return False, "a correction needs Lee's words in the note"
        review[fid] = {"status": "corrected", "note": note, "at": now}
    elif action == "merge":
        target = str(data.get("target") or "").strip()
        if target not in known or target == fid:
            return False, "merge needs a different existing target"
        src_images = []
        for f in load_findings_base().get("findings") or []:
            if f.get("id") == fid:
                src_images = list(f.get("images") or [])
        for s in splits:
            if s.get("id") == fid:
                src_images = list(s.get("images") or [])
        e = edits.get(fid) or {}
        src_images = [i for i in src_images if i not in set(e.get("removed_images") or [])]
        src_images += [i for i in (e.get("added_images") or []) if i not in src_images]
        edits.setdefault(fid, {})["merged_into"] = target
        tgt = edits.setdefault(target, {})
        added = tgt.get("added_images") or []
        for i in src_images:
            if i not in added:
                added.append(i)
        tgt["added_images"] = added
        review[fid] = {"status": "rejected", "note": "merged into %s. %s" % (target, note), "at": now}
    elif action == "split":
        images = [str(i) for i in (data.get("images") or []) if STEM_RE.match(str(i))]
        title = str(data.get("title") or "").strip()
        if not images or not title:
            return False, "split needs image ids and a title"
        new_id = "s%d-%s" % (len(splits) + 1, re.sub(r"[^a-z0-9]+", "-", title.lower())[:24].strip("-"))
        splits.append({"id": new_id, "title": title, "images": images,
                       "from": fid, "at": now})
        e = edits.setdefault(fid, {})
        removed = e.get("removed_images") or []
        for i in images:
            if i not in removed:
                removed.append(i)
        e["removed_images"] = removed
    state["findings_review"] = review
    state["finding_edits"] = edits
    state["split_findings"] = splits
    _save_state(state)
    _record_ruling_to_spine(fid, action, note, now)
    return True, action


def _record_ruling_to_spine(fid, action, note, when):
    """A ruling on a finding is business memory, not just a button state.

    Writes one row to the memory spine (LeeOSplus public.observations).
    If the spine is unreachable, the row waits in the worker's outbox and
    the daily worker retries it. The page state above is already saved,
    so a spine fault never loses the ruling and never breaks the page.
    """
    row = {
        "source": "image_plane_findings",
        "source_id": "%s:%s:%s" % (JOB_REF, fid, when),
        "observed_at": when,
        "raw_excerpt": ("Finding %s on job %s: %s. %s"
                        % (fid, JOB_REF, action, note or "(no note)")).strip(),
        "confidence": "lee_confirmed",
        "extracted_fields": {"job_ref": JOB_REF, "finding_id": fid,
                             "action": action, "note": note,
                             "surface": "job_screen findings page"},
        "source_metadata": {"machine": "mini-a", "recorded_by": "job_screen.py"},
    }
    try:
        env = _load_env(ENV_PATH)
        url = env.get("LEEOSPLUS_URL", "").rstrip("/")
        key = env.get("LEEOSPLUS_SERVICE_KEY", "")
        if not url or not key:
            raise RuntimeError("no spine credential")
        req = urllib.request.Request(
            url + "/rest/v1/observations",
            data=json.dumps(row).encode(),
            headers={"apikey": key, "Authorization": "Bearer " + key,
                     "Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status not in (200, 201):
                raise RuntimeError("spine said %s" % resp.status)
    except Exception:
        try:
            os.makedirs(WORKER_DIR, exist_ok=True)
            with open(SPINE_OUTBOX_PATH, "a") as f:
                f.write(json.dumps(row) + "\n")
        except Exception:
            traceback.print_exc()


# --------------------------------------------------------------------------
# Findings workspace HTML
# --------------------------------------------------------------------------

WS_CSS = r"""
:root { --bg:#12110f; --card:#1c1a17; --ink:#efe6d6; --muted:#9a8f7c; --line:#3a342b; --acc:#c4a35a; --ok:#7d9a5a; --warn:#c47a4a; --bad:#a35a5a; --blue:#7a9ab0; }
* { box-sizing:border-box; }
html,body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif; }
header { padding:20px 24px 12px; border-bottom:1px solid var(--line); }
h1 { margin:0; font-size:22px; font-weight:640; }
h2 { font-size:17px; margin:0; font-weight:640; }
.sub { color:var(--muted); margin-top:4px; }
.meta { display:flex; flex-wrap:wrap; gap:6px 18px; margin-top:8px; color:var(--muted); font-size:12.5px; }
a { color:var(--acc); }
.wrap { max-width:1180px; margin:0 auto; padding:18px 24px 80px; }
.summary { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 18px; margin:14px 0 22px; }
.summary p { margin:6px 0; }
.finding { background:var(--card); border:1px solid var(--line); border-radius:12px; margin:0 0 22px; overflow:hidden; }
.finding.rejected, .finding.merged { opacity:.55; }
.fhead { padding:14px 18px 10px; border-bottom:1px solid var(--line); display:flex; flex-wrap:wrap; gap:8px 14px; align-items:baseline; }
.fhead .loc { color:var(--muted); font-size:13px; width:100%; }
.chip { font-size:11px; padding:2px 9px; border-radius:999px; background:#2a261f; text-transform:uppercase; letter-spacing:.05em; }
.chip.open { background:#2a261f; color:var(--muted); }
.chip.confirmed { background:#2a3a1c; color:#cfe3b0; }
.chip.corrected { background:#1c2f3a; color:#b7d4e3; }
.chip.rejected { background:#3a1c1c; color:#f0b0b0; }
.chip.private { background:#33281c; color:#e3ceb0; }
.chip.lee { background:#2a3a1c; color:#cfe3b0; }
.chip.doc { background:#1c2f3a; color:#b7d4e3; }
.chip.machine { background:#3a2618; color:#f0c09a; }
.chip.unknown { background:#3a1c1c; color:#f0b0b0; }
.fbody { padding:14px 18px; }
.block { margin:0 0 12px; }
.block .bt { font-size:11.5px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin-bottom:3px; display:flex; gap:8px; align-items:center; }
blockquote { margin:6px 0; padding:8px 14px; border-left:3px solid var(--ok); background:#181712; border-radius:0 8px 8px 0; font-style:italic; }
.note { border-left:3px solid var(--blue); background:#151a1d; padding:8px 14px; border-radius:0 8px 8px 0; margin:6px 0; }
.imgs { display:grid; grid-template-columns:repeat(auto-fill,minmax(340px,1fr)); gap:14px; margin-top:10px; }
.ic { background:#161410; border:1px solid var(--line); border-radius:10px; overflow:hidden; }
.ic img, .ic video { width:100%; aspect-ratio:4/3; object-fit:cover; display:block; background:#000; }
.ic .icb { padding:10px 12px; }
.ic .fn { font-weight:640; font-size:13.5px; margin-bottom:6px; }
.ic .rdg { font-size:13px; margin:6px 0; }
.ic .rdg .src { font-size:10.5px; text-transform:uppercase; letter-spacing:.05em; margin-right:6px; }
.machinetext { color:#f0c09a; }
.doctext { color:#b7d4e3; }
.actions { padding:10px 18px 14px; border-top:1px solid var(--line); display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
button { background:var(--acc); color:#1a1408; border:0; border-radius:7px; padding:7px 13px; font-weight:640; cursor:pointer; font-size:13px; }
button.ghost { background:transparent; color:var(--ink); border:1px solid var(--line); }
button.danger { background:transparent; color:#f0b0b0; border:1px solid #5a3535; }
select, input[type=text] { background:#0e0d0b; color:var(--ink); border:1px solid var(--line); border-radius:6px; padding:6px 8px; font-size:13px; }
.rmk { color:var(--muted); font-size:12.5px; }
.provenance { color:var(--muted); font-size:12px; border-top:1px solid var(--line); margin-top:26px; padding-top:14px; }
.provenance code { color:var(--ink); }
"""


def _label_chip(cls, text):
    return '<span class="chip %s">%s</span>' % (cls, _html_esc(text))


def _image_card_html(card, confirmed_view=False):
    stem = card.get("id") or ""
    fn = card.get("filename") or stem
    if card.get("kind") == "video":
        media = ('<video controls playsinline preload="metadata" poster="%s" src="%s"></video>'
                 % (_html_esc(card.get("thumb") or ""), _html_esc(card.get("media") or "")))
    elif card.get("thumb"):
        media = ('<a href="%s" target="_blank"><img src="%s" alt="%s" loading="lazy"></a>'
                 % (_html_esc(card.get("media") or card.get("thumb")),
                    _html_esc(card.get("thumb")), _html_esc(stem)))
    else:
        media = '<div style="padding:40px;color:#9a8f7c">no thumb</div>'
    match_cap = ""
    seed = SEEDS.get(stem)
    if seed and seed.get("caption"):
        match_cap = ('<div class="rdg doctext"><span class="src chip doc">matched note</span>%s</div>'
                     % _html_esc(seed["caption"]))
    q = card.get("qwen")
    if q and q.get("response"):
        qtxt = ('<div class="rdg machinetext"><span class="src chip machine">machine suggestion</span>'
                '%s <span class="rmk">(%s, %ss)</span></div>'
                % (_html_esc(q["response"]), _html_esc(q.get("model") or ""),
                   _html_esc(q.get("seconds") or "?")))
    elif card.get("kind") == "video":
        qtxt = '<div class="rdg rmk">video — never watched, never machine-read</div>'
    else:
        qtxt = '<div class="rdg rmk">no machine reading yet</div>'
    if confirmed_view:
        qtxt = "" if not (q and q.get("response")) else (
            '<div class="rdg rmk">machine suggestion (unconfirmed): %s</div>' % _html_esc(q["response"]))
    return ('<div class="ic"><div>%s</div><div class="icb"><div class="fn">%s</div>%s%s</div></div>'
            % (media, _html_esc(fn), match_cap, qtxt))


def render_findings_page():
    payload = build_findings_payload()
    findings = payload["findings"]
    live = [f for f in findings if not f.get("merged_into")]
    counts = {}
    for f in live:
        counts[f.get("status") or "open"] = counts.get(f.get("status") or "open", 0) + 1
    fids = [(f["id"], f.get("title") or f["id"]) for f in findings if not f.get("merged_into")]
    sections = []
    for f in findings:
        fid = f.get("id") or ""
        status = f.get("status") or "open"
        merged = f.get("merged_into") or ""
        cls = "finding"
        if status == "rejected":
            cls += " rejected"
        if merged:
            cls += " merged"
        frs = "".join("<blockquote>%s</blockquote>" % _html_esc(x)
                      for x in (f.get("dictate_fragments") or []))
        docs = " · ".join('<a href="%s">%s</a>' % (_html_esc(d.get("href") or "#"),
                                                   _html_esc(d.get("label") or "document"))
                          for d in (f.get("documents") or []))
        imgs = "".join(_image_card_html(c) for c in (f.get("cards") or []))
        merge_opts = "".join('<option value="%s">%s</option>' % (_html_esc(i), _html_esc(t))
                             for i, t in fids if i != fid)
        note_html = ""
        if f.get("review_note"):
            note_html = ('<div class="block"><div class="bt">Lee\'s correction / note %s</div>'
                         '<div class="note">%s</div></div>'
                         % (_label_chip("lee", "lee-confirmed"), _html_esc(f["review_note"])))
        rec_html = ""
        if f.get("recommendation"):
            rec_html = ('<div class="block"><div class="bt">Recommended action %s</div><div>%s</div></div>'
                        % (_label_chip("lee", "from Lee's dictate"), _html_esc(f["recommendation"])))
        merged_html = ('<div class="note">Merged into <b>%s</b>. Images now shown there.</div>'
                       % _html_esc(merged)) if merged else ""
        sections.append("""
<section class="%s" id="%s">
  <div class="fhead">
    <h2>%s</h2>
    <span class="chip %s">%s</span>
    <div class="loc">location: %s</div>
  </div>
  <div class="fbody">
    %s
    <div class="block"><div class="bt">Lee's dictate — exact fragments %s</div>%s</div>
    %s
    <div class="block"><div class="bt">Supporting records %s</div><div>%s</div></div>
    <div class="block"><div class="bt">What this establishes</div><div>%s</div></div>
    <div class="block"><div class="bt">Remaining uncertainty %s</div><div>%s</div></div>
    %s
    <div class="block"><div class="bt">Supporting images (%d)</div><div class="imgs">%s</div></div>
  </div>
  <div class="actions" data-fid="%s">
    <button onclick="act(this,'confirm')">Confirm</button>
    <button class="ghost" onclick="actNote(this,'correct')">Correct…</button>
    <button class="danger" onclick="act(this,'reject')">Reject</button>
    <button class="ghost" onclick="act(this,'private')">Keep private</button>
    <button class="ghost" onclick="act(this,'reopen')">Reopen</button>
    <select class="mtarget"><option value="">merge into…</option>%s</select>
    <button class="ghost" onclick="doMerge(this)">Merge</button>
    <input type="text" class="simgs" placeholder="split: IMG_1841 IMG_1850">
    <input type="text" class="stitle" placeholder="split title">
    <button class="ghost" onclick="doSplit(this)">Split</button>
    <span class="rmk">%s</span>
  </div>
</section>""" % (
            cls, _html_esc(fid), _html_esc(f.get("title") or fid),
            _html_esc(status), _html_esc(STATUS_LABELS.get(status, status)),
            _html_esc(f.get("location") or "unknown"),
            merged_html,
            _label_chip("lee", "lee-confirmed"),
            frs or '<div class="rmk">none — no dictate fragment matches this group</div>',
            note_html,
            _label_chip("doc", "document-supported"),
            docs or '<span class="rmk">none genuinely available</span>',
            _html_esc(f.get("establishes") or ""),
            _label_chip("unknown", "unknown"),
            _html_esc(f.get("uncertain") or "none recorded"),
            rec_html,
            len(f.get("cards") or []), imgs or '<div class="rmk">no images</div>',
            _html_esc(fid), merge_opts,
            _html_esc(("reviewed " + f.get("review_at")) if f.get("review_at") else ""),
        ))
    src = payload.get("sources") or {}
    page = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>1892-26 · 6 Pancras Square · evidence review</title>
<style>%s</style></head><body>
<header>
  <h1>1892-26 · 6 Pancras Square — diagnostic evidence review</h1>
  <div class="sub">Findings, not files. <a href="/job/1892-26/diagnostic-section">diagnostic section (confirmed only)</a>
   · <a href="/job/1892-26/1892-26-diagnostic.pdf">diagnostic PDF</a>
   · <a href="/job/1892-26/packs/drainage-v1/">drainage pack v1</a>
   · <a href="/job/1892-26/contact-sheet">contact sheet (internal engineering diagnostic)</a></div>
  <div class="meta">
    <span>visit: diagnostic · 18 Aug 2026</span>
    <span>identity: Lee's explicit ruling (24 Aug 2026) · not ladder-confirmed · GRA identity: unresolved</span>
    <span>machine readings: %d photos read by qwen3-vl (recorded describe route)</span>
    <span>roof plan: none — no real source establishes roof zones</span>
  </div>
</header>
<div class="wrap">
  <div class="summary">
    <p><b>Visit summary.</b> Loose-laid sedum roof, roughly 12 years old, dry and excessively
    porous: light recycled-aggregate substrate with negligible retention, drainage filter fleece
    with large holes, depths measured fine (~55–130&nbsp;mm at three holes). Hibernacula need renewal.
    Two failed plant-bed roofs dictated at level 8. Remediation direction: mosaic of more retentive
    granular material; proof of concept on half of level 11. Terrace opportunity for
    connected-habitat planters.</p>
    <p class="rmk">Review status: %s. Labels: <span class="chip lee">lee-confirmed</span> Lee's words ·
    <span class="chip doc">document-supported</span> a record on disk ·
    <span class="chip machine">machine suggestion</span> qwen3-vl, never a conclusion ·
    <span class="chip unknown">unknown</span> no source.</p>
  </div>
  %s
  <div class="provenance">
    <b>Provenance.</b> Dictate: <code>%s</code> · Match: <code>%s</code> ·
    Machine readings: <code>%s</code> · Review state: <code>incoming/google/1892-26/job_screen_state.json</code> ·
    Identity: Lee's explicit ruling, 24 Aug 2026 (match_method lee_answer); every ladder lane found nothing; GRA entity none.
  </div>
</div>
<script>
async function post(fid, body) {
  body.finding_id = fid;
  const r = await fetch('/api/job/1892-26/findings/action', {method:'POST',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  const out = await r.json();
  if (!out.ok) { alert(out.message || 'refused'); return; }
  location.reload();
}
function fid(el) { return el.closest('.actions').dataset.fid; }
function act(el, a) { post(fid(el), {action:a}); }
function actNote(el, a) {
  const n = prompt("Lee's correction, in his words:");
  if (n === null || !n.trim()) return;
  post(fid(el), {action:a, note:n.trim()});
}
function doMerge(el) {
  const t = el.closest('.actions').querySelector('.mtarget').value;
  if (!t) { alert('pick a merge target'); return; }
  post(fid(el), {action:'merge', target:t});
}
function doSplit(el) {
  const a = el.closest('.actions');
  const imgs = a.querySelector('.simgs').value.trim().split(/[\\s,]+/).filter(Boolean);
  const title = a.querySelector('.stitle').value.trim();
  if (!imgs.length || !title) { alert('split needs image ids and a title'); return; }
  post(fid(el), {action:'split', images:imgs, title:title});
}
</script>
</body></html>""" % (
        WS_CSS, payload.get("qwen_read_count") or 0,
        _html_esc(", ".join("%s %s" % (v, STATUS_LABELS.get(k, k)) for k, v in sorted(counts.items()))),
        "\n".join(sections),
        _html_esc(src.get("dictate") or ""), _html_esc(src.get("match") or ""),
        _html_esc(src.get("qwen") or ""),
    )
    return page


def render_section_page():
    """Diagnostic-section view: confirmed (or corrected) findings only."""
    payload = build_findings_payload()
    keep = [f for f in payload["findings"]
            if not f.get("merged_into")
            and not f.get("group_kind")
            and (f.get("status") in ("confirmed", "corrected"))]
    sections = []
    for f in keep:
        frs = "".join("<blockquote>%s</blockquote>" % _html_esc(x)
                      for x in (f.get("dictate_fragments") or []))
        docs = " · ".join('<a href="%s">%s</a>' % (_html_esc(d.get("href") or "#"),
                                                   _html_esc(d.get("label") or "document"))
                          for d in (f.get("documents") or []))
        imgs = "".join(_image_card_html(c, confirmed_view=True) for c in (f.get("cards") or []))
        note = ""
        if f.get("review_note"):
            note = '<div class="note">Lee\'s correction: %s</div>' % _html_esc(f["review_note"])
        rec = ""
        if f.get("recommendation"):
            rec = ('<div class="block"><div class="bt">Recommended action</div><div>%s</div></div>'
                   % _html_esc(f["recommendation"]))
        sections.append("""
<section class="finding">
  <div class="fhead"><h2>%s</h2><span class="chip %s">%s</span>
  <div class="loc">location: %s</div></div>
  <div class="fbody">
    %s
    <div class="block"><div class="bt">Confirmed observation (Lee's dictate)</div>%s</div>
    <div class="block"><div class="bt">Supporting evidence</div><div>%s</div></div>
    <div class="block"><div class="bt">Remaining uncertainty</div><div>%s</div></div>
    %s
    <div class="block"><div class="bt">Selected images (%d)</div><div class="imgs">%s</div></div>
  </div>
</section>""" % (
            _html_esc(f.get("title") or f.get("id")),
            _html_esc(f.get("status")), _html_esc(STATUS_LABELS.get(f.get("status"), f.get("status"))),
            _html_esc(f.get("location") or "unknown"),
            note,
            frs or '<div class="rmk">%s</div>' % _html_esc(f.get("establishes") or ""),
            docs or '<span class="rmk">photographs and Lee\'s dictate only</span>',
            _html_esc(f.get("uncertain") or "none recorded"),
            rec,
            len(f.get("cards") or []), imgs or '<div class="rmk">no images</div>',
        ))
    body = "\n".join(sections) if sections else (
        '<div class="summary"><p>No findings are confirmed yet. Confirm findings in the '
        '<a href="/job/1892-26">evidence review</a> and they assemble here.</p></div>')
    src = payload.get("sources") or {}
    return """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>1892-26 · diagnostic section (internal)</title>
<style>%s</style></head><body>
<header>
  <h1>1892-26 · 6 Pancras Square — diagnostic section</h1>
  <div class="sub">Assembled from confirmed findings only. Internal review view — not a customer page.
  <a href="/job/1892-26">back to evidence review</a></div>
  <div class="meta"><span>visit: diagnostic · 18 Aug 2026</span>
  <span>identity: Lee's explicit ruling (24 Aug 2026) · GRA identity: unresolved</span></div>
</header>
<div class="wrap">%s
<div class="provenance"><b>Provenance.</b> Confirmed findings from the 1892-26 evidence review ·
Dictate: <code>%s</code> · Machine readings: <code>%s</code> ·
Review state: <code>incoming/google/1892-26/job_screen_state.json</code></div>
</div></body></html>""" % (WS_CSS, body, _html_esc(src.get("dictate") or ""),
                           _html_esc(src.get("qwen") or ""))


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def _json_body(handler):
    n = int(handler.headers.get("Content-Length") or 0)
    raw = handler.rfile.read(n) if n else b"{}"
    try:
        data = json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def _safe_media_name(name):
    name = os.path.basename(urllib.parse.unquote(name or ""))
    if not SAFE_NAME_RE.match(name):
        return None
    return name


# --------------------------------------------------------------------------
# Daily-worker surfaces: the Attention page and generic album/job views.
# Everything above this line renders 1892-26 exactly as before.
# --------------------------------------------------------------------------

WORKER_DIR = os.path.join(ROOT, "incoming", "worker")
ATTENTION_PATH = os.path.join(WORKER_DIR, "attention.json")
SPINE_OUTBOX_PATH = os.path.join(WORKER_DIR, "spine_outbox.jsonl")
INBOX_DIR = os.path.join(ROOT, "incoming", "google")
SAFE_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,79}$")
SAFE_WFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]*\.(jpg|jpeg|png|heic|mov|mp4)$", re.I)
GENERIC_JOB_RE = re.compile(r"^/job/(\d{3,4}-\d{2})$")
ALBUM_PAGE_RE = re.compile(r"^/album/([A-Za-z0-9][A-Za-z0-9._ -]{0,79})$")

PAGE_CSS = ("body{background:#12110f;color:#efe6d6;font:15px/1.5 -apple-system,"
            "BlinkMacSystemFont,Segoe UI,sans-serif;max-width:1100px;margin:0 auto;"
            "padding:24px 24px 80px}a{color:#c4a35a}h1{font-size:22px}"
            ".card{background:#1c1a17;border:1px solid #3a342b;border-radius:12px;"
            "padding:14px 18px;margin:0 0 18px}"
            ".chip{font-size:11px;padding:2px 9px;border-radius:999px;background:#3a2618;"
            "color:#f0c09a;text-transform:uppercase;letter-spacing:.05em}"
            ".chip.q{background:#3a1c1c;color:#f0b0b0}"
            ".muted{color:#9a8f7c}.grid{display:grid;grid-template-columns:repeat("
            "auto-fill,minmax(220px,1fr));gap:12px;margin-top:10px}"
            ".grid img{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:8px;"
            "background:#000}pre{white-space:pre-wrap;background:#181712;border:1px solid "
            "#3a342b;border-radius:8px;padding:10px;font-size:12.5px}")


def _read_json_file(path, fallback):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return fallback


def _album_dirs_for_job(job_ref):
    out = []
    if not os.path.isdir(INBOX_DIR):
        return out
    for name in sorted(os.listdir(INBOX_DIR)):
        d = os.path.join(INBOX_DIR, name)
        if not os.path.isdir(d) or name == JOB_REF:
            continue
        prog = _read_json_file(os.path.join(d, "PROGRESS.json"), {})
        if prog.get("job_ref") == job_ref:
            out.append((name, prog))
    return out


def _album_readings(slug):
    out = []
    p = os.path.join(INBOX_DIR, slug, "readings.jsonl")
    if os.path.isfile(p):
        for line in open(p):
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def _render_album_cards(slug):
    prog = _read_json_file(os.path.join(INBOX_DIR, slug, "PROGRESS.json"), {})
    ident = _read_json_file(os.path.join(INBOX_DIR, slug, "IDENTITY.json"), {}).get("identity", {})
    manifest = _read_json_file(os.path.join(INBOX_DIR, slug, "MANIFEST.json"), {"files": {}})
    readings = {r.get("file"): r for r in _album_readings(slug)}
    cards = []
    for rel, entry in sorted(manifest.get("files", {}).items()):
        if entry.get("kind") != "image" or entry.get("duplicate_of"):
            continue
        stem = os.path.splitext(os.path.basename(rel))[0]
        r = readings.get(rel) or {}
        cap = _html_esc(r.get("caption") or "not read yet")
        writing = (r.get("visible_writing") or "").strip()
        wr = ""
        if writing and writing != "NO WORDS ON THIS PAGE":
            wr = "<pre>%s</pre>" % _html_esc(writing[:600])
        cards.append(
            '<div class="card"><img src="/worker-media/%s/thumbs/%s.jpg" '
            'style="width:100%%;border-radius:8px;background:#000" loading="lazy">'
            '<div style="margin-top:8px"><b>%s</b> <span class="muted">%s</span></div>'
            '<div><span class="chip">machine reading</span> %s</div>%s</div>'
            % (urllib.parse.quote(slug), urllib.parse.quote(stem),
               _html_esc(os.path.basename(rel)),
               _html_esc(entry.get("taken_at") or ""), cap, wr))
    return prog, ident, cards


def render_album_page(slug):
    prog, ident, cards = _render_album_cards(slug)
    state = prog.get("identity") or "unprocessed"
    chip = ('<span class="chip q">quarantined — identity uncertain</span>'
            if state == "quarantined" else
            '<span class="chip">%s</span>' % _html_esc(state))
    ident_block = ("<pre>%s</pre>" % _html_esc(json.dumps(ident, indent=2)[:2000])) if ident else ""
    return ("<!DOCTYPE html><html><head><meta charset='utf-8'><title>album %s</title>"
            "<style>%s</style></head><body>"
            "<p><a href='/attention'>&larr; attention</a></p>"
            "<h1>Album: %s %s</h1>"
            "<p class='muted'>Machine suggestions only. Nothing here is a confirmed "
            "fact until a person rules on it. Quarantined media is attached to no "
            "customer and no site.</p>%s"
            "<div class='grid'>%s</div></body></html>"
            % (_html_esc(slug), PAGE_CSS, _html_esc(prog.get("album_name") or slug),
               chip, ident_block, "".join(cards)))


def render_generic_job_page(job_ref):
    albums = _album_dirs_for_job(job_ref)
    if not albums:
        return None
    parts = []
    for slug, prog in albums:
        _, ident, cards = _render_album_cards(slug)
        fp = _read_json_file(os.path.join(INBOX_DIR, slug, "findings_proposed.json"), {})
        fhtml = ""
        for f in fp.get("findings", []):
            fhtml += ('<div class="card"><b>%s</b> <span class="chip">%s</span>'
                      '<div class="muted">%s</div><div>%s</div></div>'
                      % (_html_esc(f.get("id", "")), _html_esc(f.get("state", "")),
                         _html_esc(f.get("uncertain", "")),
                         _html_esc(f.get("may_establish", ""))))
        parts.append("<h2>Album %s</h2>%s<div class='grid'>%s</div>"
                     % (_html_esc(prog.get("album_name") or slug), fhtml, "".join(cards)))
    return ("<!DOCTYPE html><html><head><meta charset='utf-8'><title>job %s</title>"
            "<style>%s</style></head><body><p><a href='/attention'>&larr; attention</a></p>"
            "<h1>Job %s</h1><p class='muted'>Daily-worker evidence view. Machine "
            "suggestions are labelled; a person's ruling is the only confirmation.</p>"
            "%s</body></html>"
            % (_html_esc(job_ref), PAGE_CSS, _html_esc(job_ref), "".join(parts)))


def render_attention_page():
    data = _read_json_file(ATTENTION_PATH, {"entries": [], "built_at": "never"})
    rows = []
    for e in data.get("entries", []):
        kind = e.get("kind", "")
        why = _html_esc(e.get("why", ""))
        title = _html_esc(e.get("album_name") or e.get("album") or e.get("job_ref") or kind)
        link = e.get("link")
        imgs = "".join('<img src="%s" loading="lazy">' % _html_esc(u)
                       for u in (e.get("images") or [])[:8])
        q = ("<div><b>Question:</b> %s</div>" % _html_esc(e["question"])) if e.get("question") else ""
        ev = ""
        if e.get("identity_evidence"):
            ev = "<pre>%s</pre>" % _html_esc(json.dumps(e["identity_evidence"], indent=2)[:1200])
        lk = ('<div><a href="%s">open</a></div>' % _html_esc(link)) if link else ""
        rows.append('<div class="card"><span class="chip q">%s</span> <b>%s</b>'
                    "<div>%s</div>%s%s<div class='grid'>%s</div>%s</div>"
                    % (_html_esc(kind), title, why, q, ev, imgs, lk))
    if not rows:
        rows = ["<div class='card'>Nothing is waiting. The worker has no open questions.</div>"]
    return ("<!DOCTYPE html><html><head><meta charset='utf-8'><title>Image Plane attention</title>"
            "<style>%s</style></head><body><h1>Attention — things waiting on a person</h1>"
            "<p class='muted'>Built %s by the daily worker. "
            "<a href='/job/1892-26'>1892-26 evidence review</a></p>%s</body></html>"
            % (PAGE_CSS, _html_esc(data.get("built_at", "")), "".join(rows)))


def attention_next():
    """One machine-readable answer: the next job waiting on a review."""
    data = _read_json_file(ATTENTION_PATH, {"entries": []})
    for e in data.get("entries", []):
        if e.get("kind") in ("identity_uncertain", "findings_waiting"):
            return {"waiting": True, "entry": e}
    return {"waiting": False, "entry": None}


class JobHandler(BaseHTTPRequestHandler):
    server_version = "ImagePlaneJobScreen/1892-26"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, code, obj):
        self._send(code, json.dumps(obj, indent=2), "application/json; charset=utf-8")

    def _send_file(self, path, ctype):
        if not os.path.isfile(path):
            self._send(404, "not found", "text/plain; charset=utf-8")
            return
        size = os.path.getsize(path)
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        code = 200
        extra = {"Accept-Ranges": "bytes"}
        if rng and rng.startswith("bytes="):
            spec = rng.split("=", 1)[1].split(",")[0].strip()
            a, _, b = spec.partition("-")
            try:
                if a:
                    start = int(a)
                if b:
                    end = int(b)
            except ValueError:
                start, end = 0, size - 1
            if start < 0 or end >= size or start > end:
                self.send_response(416)
                self.send_header("Content-Range", "bytes */%d" % size)
                self.end_headers()
                return
            code = 206
            extra["Content-Range"] = "bytes %d-%d/%d" % (start, end, size)
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "private, max-age=3600")
        for k, v in extra.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                chunk = f.read(min(65536, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path in ("/",):
            self.send_response(302)
            self.send_header("Location", "/job/1892-26")
            self.end_headers()
            return
        if path == "/job/1892-26":
            try:
                self._send(200, render_findings_page())
            except Exception:
                traceback.print_exc()
                self._send(500, "findings page failed", "text/plain; charset=utf-8")
            return
        if path == "/job/1892-26/contact-sheet":
            # Hidden engineering diagnostic surface. Not the product.
            self._send(200, render_page().replace(
                "Image Plane job screen ·",
                "INTERNAL ENGINEERING DIAGNOSTIC (contact sheet) — the product surface is "
                '<a href="/job/1892-26" style="color:#c4a35a">the evidence review</a> ·'))
            return
        if path == "/job/1892-26/diagnostic-section":
            try:
                self._send(200, render_section_page())
            except Exception:
                traceback.print_exc()
                self._send(500, "section page failed", "text/plain; charset=utf-8")
            return
        if path == "/api/job/1892-26/findings":
            try:
                self._send_json(200, build_findings_payload())
            except Exception:
                traceback.print_exc()
                self._send_json(500, {"error": "findings_build_failed"})
            return
        if path in ("/job/1892-26/1892-26-diagnostic.pdf", "/1892-26-diagnostic.pdf"):
            self._send_file(DIAGNOSTIC_PDF, "application/pdf")
            return
        if path.startswith("/job/1892-26/packs/"):
            self._serve_pack(path)
            return
        if path == "/api/job/1892-26":
            try:
                self._send_json(200, build_payload())
            except Exception:
                traceback.print_exc()
                self._send_json(500, {"error": "build_failed"})
            return
        if path.startswith("/thumb/"):
            name = _safe_media_name(path.split("/", 2)[-1])
            if not name:
                self._send(400, "bad name", "text/plain")
                return
            # thumbs are jpeg even when original is HEIC/MOV
            stem = _stem(name)
            self._send_file(os.path.join(THUMB_DIR, stem + ".jpg"), "image/jpeg")
            return
        if path.startswith("/media/"):
            name = _safe_media_name(path.split("/", 2)[-1])
            if not name:
                self._send(400, "bad name", "text/plain")
                return
            ext = os.path.splitext(name)[1].lower()
            ctype = {
                ".heic": "image/heic",
                ".mov": "video/quicktime",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
            }.get(ext, "application/octet-stream")
            self._send_file(os.path.join(ORIG_DIR, name), ctype)
            return
        if path == "/attention":
            try:
                self._send(200, render_attention_page())
            except Exception:
                traceback.print_exc()
                self._send(500, "attention page failed", "text/plain; charset=utf-8")
            return
        if path == "/api/attention":
            self._send_json(200, _read_json_file(ATTENTION_PATH, {"entries": []}))
            return
        if path == "/api/attention/next":
            self._send_json(200, attention_next())
            return
        m = ALBUM_PAGE_RE.match(urllib.parse.unquote(path))
        if m and SAFE_SLUG_RE.match(m.group(1)):
            slug = m.group(1)
            if os.path.isdir(os.path.join(INBOX_DIR, slug)):
                try:
                    self._send(200, render_album_page(slug))
                except Exception:
                    traceback.print_exc()
                    self._send(500, "album page failed", "text/plain; charset=utf-8")
                return
        m = GENERIC_JOB_RE.match(path)
        if m and m.group(1) != JOB_REF:
            try:
                body = render_generic_job_page(m.group(1))
            except Exception:
                traceback.print_exc()
                body = None
            if body is None:
                self._send(404, "no daily-worker evidence for this job yet",
                           "text/plain; charset=utf-8")
            else:
                self._send(200, body)
            return
        if path.startswith("/worker-media/"):
            parts = [urllib.parse.unquote(p) for p in path.split("/")[2:] if p]
            # /worker-media/<album>/<thumbs|originals>/<file> or /<album>/<file>
            if len(parts) in (2, 3):
                slug = parts[0]
                sub = parts[1] if len(parts) == 3 else ""
                name = os.path.basename(parts[-1])
                if (SAFE_SLUG_RE.match(slug) and SAFE_WFILE_RE.match(name)
                        and sub in ("", "thumbs", "originals")):
                    fpath = os.path.join(INBOX_DIR, slug, sub, name) if sub else \
                        os.path.join(INBOX_DIR, slug, name)
                    ext = os.path.splitext(name)[1].lower()
                    ctype = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                             ".png": "image/png", ".heic": "image/heic",
                             ".mov": "video/quicktime", ".mp4": "video/mp4"}.get(
                        ext, "application/octet-stream")
                    self._send_file(fpath, ctype)
                    return
            self._send(400, "bad worker media path", "text/plain")
            return
        self._send(404, "not found", "text/plain")

    def _serve_pack(self, path):
        """Internal pack routes: /job/1892-26/packs/<pack>/ and files inside.
        Same posture as the diagnostic PDF: internal only, no writes."""
        rest = path[len("/job/1892-26/packs/"):]
        parts = [urllib.parse.unquote(p) for p in rest.split("/") if p]
        if not parts:
            self._send(404, "not found", "text/plain")
            return
        pack = os.path.basename(parts[0])
        if not PACK_NAME_RE.match(pack):
            self._send(400, "bad pack name", "text/plain")
            return
        pack_dir = os.path.join(PACKS_DIR, pack)
        if not os.path.isdir(pack_dir):
            self._send(404, "not found", "text/plain")
            return
        if len(parts) == 1:
            names = sorted(
                n for n in os.listdir(pack_dir)
                if os.path.isfile(os.path.join(pack_dir, n)) and PACK_FILE_RE.match(n)
            )
            readme = ""
            readme_path = os.path.join(pack_dir, "README.txt")
            if os.path.isfile(readme_path):
                try:
                    with open(readme_path, encoding="utf-8", errors="replace") as f:
                        readme = f.read()
                except Exception:
                    readme = ""
            rows = "\n".join(
                '<li><a href="/job/1892-26/packs/%s/%s">%s</a></li>'
                % (_html_esc(urllib.parse.quote(pack)), _html_esc(urllib.parse.quote(n)), _html_esc(n))
                for n in names
            )
            body = (
                "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                "<title>1892-26 pack %s</title>"
                "<style>body{background:#12110f;color:#efe6d6;font:14px/1.5 -apple-system,sans-serif;"
                "max-width:760px;margin:0 auto;padding:24px}a{color:#c4a35a}pre{white-space:pre-wrap;"
                "background:#1c1a17;border:1px solid #3a342b;border-radius:8px;padding:14px}</style>"
                "</head><body><h1>1892-26 · pack %s</h1>"
                "<p>Internal only. <a href='/job/1892-26'>back to job screen</a></p>"
                "<ul>%s</ul><pre>%s</pre></body></html>"
            ) % (_html_esc(pack), _html_esc(pack), rows, _html_esc(readme))
            self._send(200, body)
            return
        name = os.path.basename(parts[1])
        if len(parts) != 2 or not PACK_FILE_RE.match(name):
            self._send(400, "bad file name", "text/plain")
            return
        ext = os.path.splitext(name)[1].lower()
        ctype = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".txt": "text/plain; charset=utf-8",
            ".pdf": "application/pdf",
        }.get(ext, "application/octet-stream")
        self._send_file(os.path.join(pack_dir, name), ctype)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        data = _json_body(self)
        if path == "/api/job/1892-26/findings/action":
            try:
                ok, msg = apply_finding_action(data)
            except Exception:
                traceback.print_exc()
                ok, msg = False, "action failed"
            self._send_json(200 if ok else 400, {"ok": ok, "message": msg})
            return
        ids = data.get("ids") or []
        if not isinstance(ids, list):
            ids = []
        ids = [str(x) for x in ids if STEM_RE.match(str(x)) or str(x).startswith("ROW_")]
        state = _load_state()
        if path == "/api/job/1892-26/selection":
            state["selection"] = ids
            _save_state(state)
            self._send_json(200, {"ok": True, "ids": ids})
            return
        if path == "/api/job/1892-26/approve":
            approvals = state.get("approvals") or {}
            payload = build_payload()
            by_id = {it["id"]: it for it in payload["items"]}
            done = []
            for i in ids:
                rec = {
                    "approved": True,
                    "approved_at": _utc_now(),
                    "approved_by": "job-screen",
                    "is_public": False,
                }
                item = by_id.get(i) or {}
                if item.get("row_id"):
                    rec["row_id"] = item["row_id"]
                    ok, reason = patch_row_approved(item["row_id"])
                    rec["spine"] = "ok" if ok else reason
                approvals[i] = rec
                done.append(i)
            state["approvals"] = approvals
            # keep approved ids in the persisted selection too
            sel = list(state.get("selection") or [])
            for i in ids:
                if i not in sel:
                    sel.append(i)
            state["selection"] = sel
            _save_state(state)
            self._send_json(200, {"ok": True, "approved": done, "is_public": False})
            return
        self._send_json(404, {"error": "not found"})


def main():
    if not os.path.isdir(ORIG_DIR):
        sys.stderr.write("job_screen: cabinet originals missing: %s\n" % ORIG_DIR)
        sys.exit(1)
    os.makedirs(JOB_DIR, exist_ok=True)
    if not os.path.exists(STATE_PATH):
        _save_state({"selection": [], "approvals": {}})
    httpd = ThreadingHTTPServer((BIND_HOST, PORT), JobHandler)
    sys.stderr.write(
        "job_screen: 1892-26 on http://%s:%s/job/1892-26 (cabinet=%s)\n"
        % (BIND_HOST, PORT, ORIG_DIR)
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
