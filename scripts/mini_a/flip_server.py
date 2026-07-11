#!/usr/bin/env python3
"""
flip_server.py -- F5 stage 3, the Lee-only photo flip surface (LEE-411).

Spec: docs/F5-FLIP-SURFACE-SPEC-2026-07-11.md. Schema: docs/F5-VISUAL-OBSERVATIONS-
ROOF-TIMELINE-2026-07-11.md. Ruling it implements (Lee, 11 Jul): "at the point of
sharing, everything that doesn't need to be private can be flipped public."

stdlib http.server + urllib + PIL only. No flask. Runs on Mini A, port 8788, same
bind posture as the existing :8787 hub (which this script does not touch).

Fail-closed posture throughout:
  - Server refuses to start without all four service-key env vars.
  - A photo can only flip ON if its original_path exists on disk right now.
  - Upload failure -> no spine PATCH (LeeOSplus row stays exactly as it was).
  - Flip OFF revokes visibility (PATCH is_public=false) BEFORE deleting the
    storage object, so the row is never in a "flipped-off but still public"
    limbo if the delete step fails.

Python 3.9 (Mini A) -- no match statements, no PEP 604 unions.

Restart line:  nohup python3 ~/image-plane/flip_server.py > ~/image-plane/flip_server.log 2>&1 &
"""
import hashlib
import html
import io
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image

PORT = 8788
ROOT = os.path.expanduser("~/image-plane")
GRIND = os.path.join(ROOT, "grind")
THUMB_DIR = os.path.join(GRIND, "flip_thumbs")
SITE_NAMES_PATH = os.path.join(GRIND, "site_names.json")
SITE_NAMES_CACHE_PATH = os.path.join(GRIND, "flip_site_names_cache.json")
ENV_PATH = os.path.join(ROOT, ".env.flip")
STORAGE_BUCKET = "roof-photos"
FLIP_ACTOR = "lee-flip-surface"
CURATED_MAX_EDGE = 1600
THUMB_MAX_EDGE = 640

os.makedirs(THUMB_DIR, exist_ok=True)


# --------------------------------------------------------------------------
# Config -- fail closed without all four keys
# --------------------------------------------------------------------------

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


_ENV = _load_env(ENV_PATH)
LEEOSPLUS_URL = os.environ.get("LEEOSPLUS_URL") or _ENV.get("LEEOSPLUS_URL")
LEEOSPLUS_SERVICE_KEY = os.environ.get("LEEOSPLUS_SERVICE_KEY") or _ENV.get("LEEOSPLUS_SERVICE_KEY")
GRA_URL = os.environ.get("GRA_URL") or _ENV.get("GRA_URL")
GRA_SERVICE_KEY = os.environ.get("GRA_SERVICE_KEY") or _ENV.get("GRA_SERVICE_KEY")

_missing = [
    name for name, val in (
        ("LEEOSPLUS_URL", LEEOSPLUS_URL),
        ("LEEOSPLUS_SERVICE_KEY", LEEOSPLUS_SERVICE_KEY),
        ("GRA_URL", GRA_URL),
        ("GRA_SERVICE_KEY", GRA_SERVICE_KEY),
    ) if not val
]
if _missing:
    sys.stderr.write(
        "flip_server: refusing to start -- missing env var(s): %s "
        "(checked process env, then %s). Fail closed.\n" % (", ".join(_missing), ENV_PATH)
    )
    sys.exit(1)

LEEOSPLUS_URL = LEEOSPLUS_URL.rstrip("/")
GRA_URL = GRA_URL.rstrip("/")


# --------------------------------------------------------------------------
# Tiny REST helpers (urllib only)
# --------------------------------------------------------------------------

def _http(method, url, headers=None, data=None, timeout=30):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.getheaders()), resp.read()
    except urllib.error.HTTPError as e:
        body = e.read()
        return e.code, dict(e.headers or {}), body
    except urllib.error.URLError as e:
        raise RuntimeError("network error calling %s: %s" % (url, e))


def _leeosplus_headers(extra=None):
    h = {
        "apikey": LEEOSPLUS_SERVICE_KEY,
        "Authorization": "Bearer " + LEEOSPLUS_SERVICE_KEY,
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _gra_headers(extra=None):
    h = {
        "apikey": GRA_SERVICE_KEY,
        "Authorization": "Bearer " + GRA_SERVICE_KEY,
    }
    if extra:
        h.update(extra)
    return h


def leeosplus_get_all(table, query):
    """Paginated GET over PostgREST Range headers. query is a raw querystring
    (already urlencoded), e.g. 'select=id,job_ref&job_ref=eq.1124-19'."""
    rows = []
    page = 1000
    offset = 0
    while True:
        url = "%s/rest/v1/%s?%s" % (LEEOSPLUS_URL, table, query)
        headers = _leeosplus_headers({"Range-Unit": "items", "Range": "%d-%d" % (offset, offset + page - 1)})
        status, _, body = _http("GET", url, headers=headers)
        if status not in (200, 206):
            raise RuntimeError("LeeOSplus GET %s failed: HTTP %d %s" % (table, status, body[:300]))
        chunk = json.loads(body or b"[]")
        rows.extend(chunk)
        if len(chunk) < page:
            break
        offset += page
    return rows


def leeosplus_patch(row_id, body):
    url = "%s/rest/v1/visual_observations?id=eq.%s" % (LEEOSPLUS_URL, urllib.parse.quote(str(row_id)))
    headers = _leeosplus_headers({"Prefer": "return=representation"})
    status, _, resp_body = _http("PATCH", url, headers=headers, data=json.dumps(body).encode("utf-8"))
    if status not in (200, 204):
        raise RuntimeError("LeeOSplus PATCH id=%s failed: HTTP %d %s" % (row_id, status, resp_body[:300]))
    try:
        return json.loads(resp_body or b"[]")
    except Exception:
        return []


def gra_storage_upload(object_path, data_bytes):
    url = "%s/storage/v1/object/%s/%s" % (GRA_URL, STORAGE_BUCKET, urllib.parse.quote(object_path))
    headers = _gra_headers({"Content-Type": "image/jpeg", "x-upsert": "true"})
    status, _, body = _http("POST", url, headers=headers, data=data_bytes, timeout=60)
    if status not in (200, 201):
        raise RuntimeError("GRA storage upload %s failed: HTTP %d %s" % (object_path, status, body[:300]))


def gra_storage_delete(object_path):
    url = "%s/storage/v1/object/%s/%s" % (GRA_URL, STORAGE_BUCKET, urllib.parse.quote(object_path))
    status, _, body = _http("DELETE", url, headers=_gra_headers())
    if status not in (200, 204):
        raise RuntimeError("GRA storage delete %s failed: HTTP %d %s" % (object_path, status, body[:300]))


# --------------------------------------------------------------------------
# Site name resolution -- names not codes (Lee's hard rule)
# --------------------------------------------------------------------------

def _load_site_names_json():
    if not os.path.exists(SITE_NAMES_PATH):
        return {}
    try:
        return json.load(open(SITE_NAMES_PATH))
    except Exception:
        return {}


def _fetch_gra_addresses():
    """GRA sites has no site_name column -- 'address' is the real identity
    field (per CLAUDE.md site-vs-billing doctrine). Cache the pull so a GRA
    outage doesn't blank the index."""
    try:
        rows = []
        page = 1000
        offset = 0
        while True:
            url = "%s/rest/v1/sites?select=job_ref,address" % GRA_URL
            headers = _gra_headers({"Range-Unit": "items", "Range": "%d-%d" % (offset, offset + page - 1)})
            status, _, body = _http("GET", url, headers=headers)
            if status not in (200, 206):
                raise RuntimeError("GRA sites GET failed: HTTP %d %s" % (status, body[:300]))
            chunk = json.loads(body or b"[]")
            rows.extend(chunk)
            if len(chunk) < page:
                break
            offset += page
        cache = {r["job_ref"]: r.get("address") for r in rows if r.get("job_ref")}
        with open(SITE_NAMES_CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=1)
        return cache
    except Exception as e:
        sys.stderr.write("flip_server: GRA site-name fetch failed (%s), falling back to cache file\n" % e)
        if os.path.exists(SITE_NAMES_CACHE_PATH):
            try:
                return json.load(open(SITE_NAMES_CACHE_PATH))
            except Exception:
                return {}
        return {}


_SITE_NAMES = _load_site_names_json()
_GRA_ADDR_CACHE = _fetch_gra_addresses()


def resolve_name(job_ref):
    rec = _SITE_NAMES.get(job_ref)
    if rec and rec.get("name"):
        return rec["name"]
    addr = _GRA_ADDR_CACHE.get(job_ref)
    if addr:
        return addr
    return None


def display_name_html(job_ref):
    name = resolve_name(job_ref)
    if name:
        return "%s <span class='refcode'>(%s)</span>" % (html.escape(name), html.escape(job_ref))
    return "<span class='unnamed'>Unnamed site</span> <span class='refcode'>(%s)</span>" % html.escape(job_ref)


# --------------------------------------------------------------------------
# Image handling
# --------------------------------------------------------------------------

def _sips_to_jpeg(src_path, dest_path, max_edge):
    proc = subprocess.run(
        ["sips", "-s", "format", "jpeg", "-Z", str(max_edge), src_path, "--out", dest_path],
        capture_output=True, timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError("sips failed on %s: %s" % (src_path, proc.stderr.decode(errors="replace")[:300]))
    with open(dest_path, "rb") as f:
        head = f.read(4)
    if head[:2] != b"\xff\xd8":
        raise RuntimeError("sips did not produce a real JPEG for %s (first bytes %r)" % (src_path, head))


def make_thumb(row_id, original_path):
    """Local downscaled JPEG, cached under grind/flip_thumbs/. sips handles
    every source format uniformly (PIL alone can't open HEIC on this box)."""
    dest = os.path.join(THUMB_DIR, "%s.jpg" % row_id)
    if os.path.exists(dest):
        return dest
    if not os.path.exists(original_path):
        return None
    _sips_to_jpeg(original_path, dest, THUMB_MAX_EDGE)
    return dest


def curate_image(original_path):
    """Flip-ON curated copy: max edge 1600px, EXIF/GPS fully stripped.
    sips does the format-normalise + resize (handles HEIC); PIL then rebuilds
    a fresh Image from raw pixel data only (no .info dict carried over) --
    that rebuild is what actually guarantees EXIF/GPS are gone, per spec."""
    fd, tmp_path = tempfile.mkstemp(suffix=".jpg", dir=THUMB_DIR)
    os.close(fd)
    try:
        _sips_to_jpeg(original_path, tmp_path, CURATED_MAX_EDGE)
        img = Image.open(tmp_path)
        img = img.convert("RGB")
        clean = Image.new("RGB", img.size)
        clean.putdata(list(img.getdata()))
        buf = io.BytesIO()
        clean.save(buf, "JPEG", quality=85)
        return buf.getvalue()
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Flip actions
# --------------------------------------------------------------------------

def flip_on(row):
    row_id = row["id"]
    job_ref = row["job_ref"]
    original_path = row.get("original_path")

    if row.get("is_public") and row.get("gra_media_path"):
        return {"ok": True, "id": row_id, "is_public": True, "note": "already public"}

    if not original_path or not os.path.exists(original_path):
        return {"ok": False, "error": "original file missing on disk -- cannot flip public", "status": 400}

    try:
        curated_bytes = curate_image(original_path)
    except Exception as e:
        return {"ok": False, "error": "curation failed: %s" % e, "status": 500}

    sha16 = hashlib.sha256(curated_bytes).hexdigest()[:16]
    object_path = "%s/%s.jpg" % (job_ref, sha16)

    try:
        gra_storage_upload(object_path, curated_bytes)
    except Exception as e:
        # Fail closed: no spine change if upload fails.
        return {"ok": False, "error": "GRA upload failed, no change made: %s" % e, "status": 502}

    patch_body = {
        "gra_media_path": object_path,
        "is_public": True,
        "public_flipped_at": _now_iso(),
        "public_flipped_by": FLIP_ACTOR,
        "curated_set": "flip-surface-max1600-exif-stripped",
    }
    try:
        leeosplus_patch(row_id, patch_body)
    except Exception as e:
        # Roll back the upload so we don't leave an orphan object with no
        # spine row pointing at it.
        try:
            gra_storage_delete(object_path)
        except Exception:
            pass
        return {"ok": False, "error": "spine update failed after upload, rolled back: %s" % e, "status": 502}

    return {"ok": True, "id": row_id, "is_public": True, "gra_media_path": object_path}


def flip_off(row):
    row_id = row["id"]
    existing_path = row.get("gra_media_path")

    if not row.get("is_public") and not existing_path:
        return {"ok": True, "id": row_id, "is_public": False, "note": "already private"}

    patch_body = {
        "is_public": False,
        "gra_media_path": None,
        "curated_set": None,
    }
    try:
        leeosplus_patch(row_id, patch_body)
    except Exception as e:
        return {"ok": False, "error": "spine update failed: %s" % e, "status": 502}

    if existing_path:
        try:
            gra_storage_delete(existing_path)
        except Exception as e:
            return {
                "ok": True, "id": row_id, "is_public": False,
                "warning": "row is private now, but storage cleanup failed and needs a retry: %s" % e,
            }

    return {"ok": True, "id": row_id, "is_public": False}


def get_row(row_id):
    rows = leeosplus_get_all(
        "visual_observations",
        "id=eq.%s&select=id,job_ref,original_path,is_public,gra_media_path,visit_date,lee_note,building"
        % urllib.parse.quote(str(row_id)),
    )
    return rows[0] if rows else None


# --------------------------------------------------------------------------
# HTML rendering
# --------------------------------------------------------------------------

BASE_CSS = """
:root { color-scheme: dark; }
body { background:#0f0f10; color:#e8e8e8; margin:0; padding:0 0 90px;
  font:16px/1.55 -apple-system,Segoe UI,Roboto,sans-serif; }
.wrap { max-width:1180px; margin:0 auto; padding:0 20px; }
a { color:#7fb0e8; }
.banner { background:#1a2333; border-left:5px solid #7fb0e8; padding:16px 18px;
  margin:18px 0 18px; border-radius:0 8px 8px 0; }
.banner h1 { font-size:20px; margin:0 0 8px; font-weight:700; color:#cfe0f5; }
.banner p { margin:0; color:#e8e8e8; font-size:15px; }
.refcode { color:#8a9; font-size:13px; font-weight:400; }
.unnamed { color:#e0b87e; }
table { width:100%; border-collapse:collapse; }
th, td { text-align:left; padding:12px 10px; border-top:1px solid #262626; font-size:15px; }
th { color:#9aa; font-weight:600; font-size:13px; text-transform:uppercase; letter-spacing:.03em; }
tr:hover td { background:#161616; }
.count { font-variant-numeric:tabular-nums; }
.count-public { color:#7fd18b; font-weight:700; }
.row { border-top:1px solid #262626; padding:26px 0; }
.row:first-of-type { border-top:none; }
.rowhead { display:flex; align-items:center; gap:12px; margin-bottom:10px; flex-wrap:wrap; }
.date-badge { display:inline-flex; align-items:center; padding:6px 12px; border-radius:8px;
  background:#1c2436; color:#a9c4ec; font-weight:700; font-size:14px; }
.building-badge { display:inline-flex; align-items:center; padding:6px 12px; border-radius:8px;
  background:#241c33; color:#c9a9ec; font-weight:600; font-size:13px; }
.photowrap { display:block; width:100%; margin-bottom:10px; }
.photowrap img { display:block; width:100%; max-width:100%; height:auto; border-radius:8px; background:#1a1a1a; }
.missing { color:#e0837e; font-size:14px; padding:24px; background:#1a1414; border-radius:8px; text-align:center; }
.caption { background:#141c14; border-left:4px solid #7fd18b; border-radius:0 6px 6px 0;
  padding:8px 12px; margin:8px 0 12px; font-size:14.5px; color:#dfe8df; }
.caption-label { color:#7fd18b; font-weight:700; text-transform:uppercase; font-size:11px;
  letter-spacing:.03em; margin-right:6px; }
.state-row { display:flex; align-items:center; gap:12px; margin-top:8px; flex-wrap:wrap; }
.state-badge { display:inline-flex; align-items:center; padding:6px 14px; border-radius:20px;
  font-weight:800; font-size:13px; letter-spacing:.04em; }
.state-public { background:#16321f; color:#7fd18b; }
.state-private { background:#2a2a2a; color:#aaa; }
.toggle-btn { border:none; border-radius:8px; padding:10px 18px; font-size:14.5px;
  font-weight:700; cursor:pointer; }
.toggle-btn.is-private { background:#243a2a; color:#a9e8bd; }
.toggle-btn.is-public { background:#3a2626; color:#f0b0b0; }
.toggle-btn:disabled { opacity:.55; cursor:wait; }
.footer-bar { position:fixed; left:0; right:0; bottom:0; background:#141416;
  border-top:1px solid #2a2a2a; padding:12px 20px; text-align:center; font-size:14.5px; }
.error-flag { color:#e0837e; font-size:13.5px; margin-top:6px; }
"""


def page_shell(title, body_html, extra_head=""):
    return (
        "<!doctype html>\n<meta charset=\"utf-8\">\n<title>%s</title>\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<style>%s</style>\n%s\n<div class=\"wrap\">%s</div>\n"
        % (html.escape(title), BASE_CSS, extra_head, body_html)
    )


def render_index():
    rows = leeosplus_get_all("visual_observations", "select=job_ref,is_public")
    per_ref = {}
    for r in rows:
        jr = r.get("job_ref")
        if not jr:
            continue
        d = per_ref.setdefault(jr, {"total": 0, "public": 0})
        d["total"] += 1
        if r.get("is_public"):
            d["public"] += 1

    def sort_key(jr):
        name = resolve_name(jr)
        return (0, name.lower()) if name else (1, jr)

    refs = sorted(per_ref.keys(), key=sort_key)
    total_photos = sum(d["total"] for d in per_ref.values())
    total_public = sum(d["public"] for d in per_ref.values())

    rows_html = []
    for jr in refs:
        d = per_ref[jr]
        pub_html = ("<span class='count count-public'>%d</span>" % d["public"]) if d["public"] else \
            "<span class='count'>0</span>"
        rows_html.append(
            "<tr onclick=\"location.href='/flip/%s'\" style='cursor:pointer'>"
            "<td>%s</td><td class='count'>%d</td><td>%s</td></tr>"
            % (urllib.parse.quote(jr), display_name_html(jr), d["total"], pub_html)
        )

    body = (
        "<div class='banner'><h1>Roof photo timelines</h1>"
        "<p>%d roofs with tied photos &middot; %d photos total &middot; "
        "<span class='count-public'>%d public</span></p></div>"
        "<table><thead><tr><th>Site</th><th>Photos</th><th>Public</th></tr></thead>"
        "<tbody>%s</tbody></table>"
        % (len(refs), total_photos, total_public, "".join(rows_html))
    )
    return page_shell("Roof photo timelines", body)


def render_flip_page(job_ref, only_id=None):
    rows = leeosplus_get_all(
        "visual_observations",
        "job_ref=eq.%s&select=id,visit_date,lee_note,building,is_public,gra_media_path,original_path"
        "&order=visit_date.asc,id.asc" % urllib.parse.quote(job_ref),
    )
    # 'only' is a verification convenience (jump straight to one photo for a
    # proof screenshot) -- it never changes what exists, only what's shown.
    if only_id:
        rows = [r for r in rows if str(r.get("id")) == str(only_id)]
    if not rows:
        body = "<div class='banner'><h1>%s</h1><p>No tied photos found for this roof.</p></div>" % \
            display_name_html(job_ref)
        return page_shell("No photos", body)

    total = len(rows)
    public_now = sum(1 for r in rows if r.get("is_public"))

    row_blocks = []
    for r in rows:
        rid = r["id"]
        date = r.get("visit_date") or "undated"
        is_pub = bool(r.get("is_public"))
        state_cls = "state-public" if is_pub else "state-private"
        state_txt = "PUBLIC" if is_pub else "PRIVATE"
        btn_cls = "is-public" if is_pub else "is-private"
        btn_txt = "Public — tap to make Private" if is_pub else "Private — tap to make Public"

        building_html = ""
        if r.get("building"):
            building_html = "<span class='building-badge'>%s</span>" % html.escape(r["building"])

        note_html = ""
        if r.get("lee_note"):
            note_html = (
                "<div class='caption'><span class='caption-label'>Lee</span>%s</div>"
                % html.escape(r["lee_note"])
            )

        has_file = bool(r.get("original_path")) and os.path.exists(r.get("original_path") or "")
        if has_file:
            photo_html = (
                "<a class='photowrap' href='/thumb?id=%s' target='_blank'>"
                "<img src='/thumb?id=%s' loading='lazy' alt='roof photo'></a>"
                % (urllib.parse.quote(str(rid)), urllib.parse.quote(str(rid)))
            )
            error_html = ""
        else:
            photo_html = "<div class='missing'>Original file not found on disk &mdash; cannot display or flip.</div>"
            error_html = "<div class='error-flag'>Missing on disk: flip is disabled for this photo.</div>"

        toggle_html = (
            "" if not has_file else
            "<button class=\"toggle-btn %s\" data-id=\"%s\" data-public=\"%s\" onclick=\"flipPhoto(this)\">%s</button>"
            % (btn_cls, html.escape(str(rid)), "1" if is_pub else "0", html.escape(btn_txt))
        )

        row_blocks.append(
            "<div class='row photo-row' id='row-%s'>"
            "<div class='rowhead'><span class='date-badge'>%s</span>%s</div>"
            "%s%s"
            "<div class='state-row'>"
            "<span class='state-badge %s'>%s</span>%s</div>"
            "%s"
            "</div>"
            % (html.escape(str(rid)), html.escape(str(date)), building_html, photo_html, note_html,
               state_cls, state_txt, toggle_html, error_html)
        )

    js = """
<script>
async function flipPhoto(btn) {
  const id = btn.dataset.id;
  const makePublic = btn.dataset.public !== '1';
  btn.disabled = true;
  const prevText = btn.textContent;
  btn.textContent = 'Working...';
  try {
    const res = await fetch('/flip', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({id: id, public: makePublic})
    });
    const data = await res.json();
    if (!res.ok || data.ok === false) {
      alert('Flip failed: ' + (data.error || res.status));
      btn.disabled = false;
      btn.textContent = prevText;
      return;
    }
    applyState(btn, makePublic);
  } catch (e) {
    alert('Flip failed: ' + e);
    btn.disabled = false;
    btn.textContent = prevText;
  }
}
function applyState(btn, isPublic) {
  btn.dataset.public = isPublic ? '1' : '0';
  btn.textContent = isPublic ? 'Public \\u2014 tap to make Private' : 'Private \\u2014 tap to make Public';
  btn.className = 'toggle-btn ' + (isPublic ? 'is-public' : 'is-private');
  btn.disabled = false;
  const row = btn.closest('.photo-row');
  const badge = row.querySelector('.state-badge');
  badge.textContent = isPublic ? 'PUBLIC' : 'PRIVATE';
  badge.className = 'state-badge ' + (isPublic ? 'state-public' : 'state-private');
  updateFooter();
}
function updateFooter() {
  const total = document.querySelectorAll('.photo-row').length;
  const pub = document.querySelectorAll('.state-badge.state-public').length;
  document.getElementById('footer-counts').textContent = pub + ' of ' + total + ' public';
}
document.addEventListener('DOMContentLoaded', updateFooter);
</script>
"""

    body = (
        "<div class='banner'><h1>%s</h1><p><a href='/'>&larr; all roofs</a></p></div>"
        "%s"
        "<div class='footer-bar'>Live counts: <span id='footer-counts'>%d of %d public</span></div>"
        % (display_name_html(job_ref), "".join(row_blocks), public_now, total)
    )
    return page_shell("Flip -- %s" % (resolve_name(job_ref) or job_ref), body, extra_head=js)


# --------------------------------------------------------------------------
# HTTP handler
# --------------------------------------------------------------------------

class FlipHandler(BaseHTTPRequestHandler):
    server_version = "flip-server/1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send_html(self, body, status=200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, obj, status=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, data, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/":
                self._send_html(render_index())
            elif path.startswith("/flip/"):
                job_ref = urllib.parse.unquote(path[len("/flip/"):])
                only_id = (qs.get("only") or [None])[0]
                self._send_html(render_flip_page(job_ref, only_id=only_id))
            elif path == "/thumb":
                row_id = (qs.get("id") or [None])[0]
                if not row_id:
                    self._send_json({"error": "missing id"}, status=400)
                    return
                row = get_row(row_id)
                if not row:
                    self._send_json({"error": "row not found"}, status=404)
                    return
                original_path = row.get("original_path")
                if not original_path or not os.path.exists(original_path):
                    self._send_json({"error": "original file missing on disk"}, status=404)
                    return
                try:
                    thumb_path = make_thumb(row_id, original_path)
                except Exception as e:
                    self._send_json({"error": "thumb generation failed: %s" % e}, status=500)
                    return
                with open(thumb_path, "rb") as f:
                    self._send_bytes(f.read(), "image/jpeg")
            else:
                self._send_json({"error": "not found"}, status=404)
        except Exception as e:
            self._send_json({"error": "server error: %s" % e}, status=500)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/flip":
            self._send_json({"error": "not found"}, status=404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw or b"{}")
        except Exception as e:
            self._send_json({"ok": False, "error": "bad request body: %s" % e}, status=400)
            return

        row_id = payload.get("id")
        want_public = bool(payload.get("public"))
        if not row_id:
            self._send_json({"ok": False, "error": "missing id"}, status=400)
            return

        try:
            row = get_row(row_id)
        except Exception as e:
            self._send_json({"ok": False, "error": "lookup failed: %s" % e}, status=502)
            return
        if not row:
            self._send_json({"ok": False, "error": "row not found"}, status=404)
            return

        result = flip_on(row) if want_public else flip_off(row)
        status = 200 if result.get("ok") else result.get("status", 500)
        self._send_json(result, status=status)


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), FlipHandler)
    print("flip_server: listening on :%d (pid %d)" % (PORT, os.getpid()))
    print("flip_server: %d site names loaded, %d GRA addresses cached"
          % (len(_SITE_NAMES), len(_GRA_ADDR_CACHE)))
    server.serve_forever()


if __name__ == "__main__":
    main()
