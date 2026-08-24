"""Internal Image Plane job screen. Mesh URL: /job/{job_ref}."""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import sqlite3
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import albums
from . import cabinet
from . import db as dbmod
from . import gra
from . import pack
from . import paths
from . import report

log = logging.getLogger("image_plane.server")

FILTERS = [
    "Installation",
    "Waterproofing",
    "Drainage and outlets",
    "Edges and penetrations",
    "Protection and build-up",
    "Substrate",
    "Planting and vegetation",
    "Irrigation",
    "Maintenance",
    "Defect",
    "Repair",
    "Before",
    "After",
    "Private",
    "Approved",
    "Published",
]

CSS = """
:root { --bg:#111113; --card:#1a1a1d; --ink:#ececec; --muted:#9a9aa3;
  --line:#2a2a2e; --acc:#7fb0e8; --ok:#7fd18b; --warn:#e0b87e; --bad:#e0837e;
  --machine:#c9a9ec; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.45 system-ui,sans-serif; }
a { color:var(--acc); }
.wrap { max-width:1180px; margin:0 auto; padding:20px 20px 140px; }
.banner { background:#18181b; border:1px solid var(--line); border-radius:12px; padding:18px 20px; margin-bottom:16px; }
h1 { margin:0 0 6px; font-size:24px; }
.meta { color:var(--muted); font-size:14px; }
.toolbar { display:flex; flex-wrap:wrap; gap:8px; margin:14px 0; align-items:center; }
input[type=search], input[type=text] { background:#101012; color:var(--ink); border:1px solid var(--line);
  border-radius:8px; padding:8px 10px; min-width:220px; }
button, .btn { background:#243044; color:#dce8f8; border:1px solid #33425a; border-radius:8px;
  padding:8px 12px; font-weight:650; cursor:pointer; text-decoration:none; display:inline-block; }
button.danger { background:#3a2626; color:#f0b0b0; }
.chips { display:flex; flex-wrap:wrap; gap:6px; margin:8px 0 16px; }
.chip { background:#1c1c20; border:1px solid var(--line); color:var(--muted); border-radius:999px;
  padding:5px 10px; font-size:12px; cursor:pointer; }
.chip.on { background:#243044; color:#dce8f8; border-color:#3a5273; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:12px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px; overflow:hidden; }
.card.quarantine { border-color:#6a4a20; }
.card.machine { border-color:#4a3a62; }
.thumb { background:#0d0d0f; min-height:170px; display:flex; align-items:center; justify-content:center; }
.thumb img { width:100%; height:190px; object-fit:contain; background:#0d0d0f; display:block; }
.thumb .video { color:var(--muted); padding:24px; text-align:center; }
.body { padding:10px 12px 12px; font-size:13px; }
.label { color:var(--muted); text-transform:uppercase; font-size:10px; letter-spacing:.04em; }
.badges { display:flex; flex-wrap:wrap; gap:5px; margin:6px 0; }
.badge { font-size:11px; font-weight:700; border-radius:6px; padding:2px 7px; }
.b-conf { background:#16321f; color:var(--ok); }
.b-mach { background:#241c33; color:var(--machine); }
.b-unk { background:#2a2a2a; color:#aaa; }
.b-priv { background:#2a2a2a; color:#aaa; }
.b-appr { background:#243a2a; color:var(--ok); }
.b-pub { background:#1c2436; color:var(--acc); }
.b-q { background:#332619; color:var(--warn); }
.unknown { color:#8a8a8a; font-style:italic; }
.footer { position:fixed; left:0; right:0; bottom:0; background:#141416; border-top:1px solid var(--line);
  padding:10px 18px; display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
.notice { background:#241f14; border-left:4px solid var(--warn); padding:10px 12px; margin:10px 0 16px; color:#e0cba0; }
.empty { color:var(--muted); padding:24px 0; }
.selbox { margin-right:6px; }
"""

JS = r"""
function selectedIds(){
  return Array.from(document.querySelectorAll('.selbox:checked')).map(el => el.value);
}
function currentFilters(){
  return Array.from(document.querySelectorAll('.chip.on')).map(el => el.dataset.filter);
}
function applyView(){
  const q = (document.getElementById('q').value || '').toLowerCase();
  const filters = currentFilters();
  let shown = 0;
  document.querySelectorAll('.card').forEach(card => {
    const blob = card.dataset.blob || '';
    let ok = !q || blob.includes(q);
    filters.forEach(f => {
      const aliases = (card.dataset[f.replace(/\s+/g,'_').toLowerCase()] || card.dataset.blob);
      if (ok && f && !blob.includes(f.toLowerCase()) && !aliases.includes(f.toLowerCase())) {
        // allow alias tokens already baked into data-blob
        const token = f.toLowerCase().split(' ')[0];
        if (!blob.includes(token)) ok = false;
      }
    });
    card.style.display = ok ? '' : 'none';
    if (ok) shown += 1;
  });
  document.getElementById('shown').textContent = shown;
}
function toggleChip(el){
  el.classList.toggle('on');
  applyView();
}
async function postJSON(url, body){
  const res = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}
async function saveSelection(){
  const name = document.getElementById('selname').value.trim();
  const ids = selectedIds();
  if (!name) { alert('Name the selection'); return; }
  if (!ids.length) { alert('Select at least one image'); return; }
  const data = await postJSON(location.pathname + '/selection', {name, item_ids: ids});
  location.search = '?selection=' + encodeURIComponent(data.name);
}
async function setVis(visibility){
  const ids = selectedIds();
  if (!ids.length) { alert('Select items first'); return; }
  await postJSON(location.pathname + '/visibility', {item_ids: ids, visibility});
  location.reload();
}
async function makeReport(){
  const name = document.getElementById('selname').value.trim() || new URLSearchParams(location.search).get('selection');
  if (!name) { alert('Save or reopen a named selection first'); return; }
  const data = await postJSON(location.pathname + '/report', {selection: name});
  window.location = data.url;
}
async function makePack(){
  const name = document.getElementById('selname').value.trim() || new URLSearchParams(location.search).get('selection');
  if (!name) { alert('Save or reopen a named selection first'); return; }
  const data = await postJSON(location.pathname + '/pack', {selection: name});
  window.location = data.url;
}
async function prepGRA(){
  const name = document.getElementById('selname').value.trim() || new URLSearchParams(location.search).get('selection');
  if (!name) { alert('Save or reopen a named selection first'); return; }
  const data = await postJSON(location.pathname + '/gra', {selection: name});
  alert(data.blocker || ('Prepared ' + (data.approved_copied||[]).length + ' approved derivatives'));
}
document.addEventListener('DOMContentLoaded', applyView);
"""


def _esc(text) -> str:
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _unknown(value) -> str:
    if value in (None, "", "unknown"):
        return "<span class='unknown'>unknown</span>"
    return _esc(value)


def _blob(item: dict) -> str:
    parts = [
        item.get("source_path"),
        item.get("source_album"),
        item.get("filed_job_ref"),
        item.get("staged_job_ref"),
        item.get("site_identity"),
        item.get("capture_date"),
        item.get("phase"),
        item.get("roof_area"),
        item.get("component"),
        item.get("condition_defect"),
        item.get("work_action"),
        item.get("before_after"),
        item.get("observation_confirmed"),
        item.get("observation_machine"),
        item.get("confirmation_state"),
        item.get("visibility"),
        item.get("identity_status"),
        item.get("media_kind"),
    ]
    return " ".join(str(p or "") for p in parts).lower()


def render_job(conn: sqlite3.Connection, job_ref: str, query: str, filters: list[str], selection_name: str | None) -> str:
    items = cabinet.items_for_job(conn, job_ref)
    filtered = cabinet.filter_items(items, query, filters)
    site = paths.site_name(job_ref)
    selections = cabinet.list_selections(conn, job_ref)
    selected_ids = set()
    if selection_name:
        sel = cabinet.get_selection(conn, job_ref, selection_name)
        if sel:
            selected_ids = set(sel["item_ids"])
    resolved = sum(1 for i in items if i["identity_status"] == "resolved")
    quarantined = sum(1 for i in items if i["identity_status"] != "resolved")
    videos = sum(1 for i in items if i["media_kind"] == "video")
    historic_note = ""
    if not items:
        historic_note = (
            "<div class='notice'>This cabinet has no evidenced records for this job. "
            "The screen will not invent matches from date or appearance. "
            "Best evidenced subset: 0.</div>"
        )
    elif query or filters:
        if not filtered:
            historic_note = (
                "<div class='notice'>No evidenced matches for this search inside job "
                f"{_esc(job_ref)}. Best evidenced subset: 0. Nothing was guessed.</div>"
            )
        elif any(f.lower() in {"installation", "waterproofing"} for f in filters) and not any(
            (i.get("phase") or i.get("component") or i.get("observation_confirmed") or "")
            for i in filtered
        ):
            historic_note = (
                "<div class='notice'>Existing historic records lack enough confirmed "
                "installation/waterproofing notes. Showing the best evidenced subset only.</div>"
            )

    chips = []
    for name in FILTERS:
        on = " on" if name.lower() in {f.lower() for f in filters} else ""
        chips.append(
            f"<button type='button' class='chip{on}' data-filter='{_esc(name)}' onclick='toggleChip(this)'>{_esc(name)}</button>"
        )

    cards = []
    for item in filtered:
        klass = "card"
        if item["identity_status"] != "resolved":
            klass += " quarantine"
        if item.get("observation_machine") and not item.get("observation_confirmed"):
            klass += " machine"
        checked = " checked" if item["id"] in selected_ids else ""
        if item["media_kind"] == "image" and item.get("thumb_path"):
            media = (
                f"<a class='thumb' href='/media/{item['id']}' target='_blank'>"
                f"<img src='/thumb/{item['id']}' alt='cabinet image' loading='lazy'></a>"
            )
        elif item["media_kind"] == "video":
            media = (
                f"<div class='thumb'><div class='video'>Video<br>{_esc(Path(item['source_path']).name)}<br>"
                f"<a href='/media/{item['id']}'>Open / download original</a></div></div>"
            )
        else:
            media = "<div class='thumb'><div class='video'>No thumbnail</div></div>"
        badges = []
        if item["identity_status"] != "resolved":
            badges.append("<span class='badge b-q'>quarantine / unresolved</span>")
        else:
            badges.append("<span class='badge b-conf'>filed</span>")
        if item.get("confirmation_state") == "confirmed":
            badges.append("<span class='badge b-conf'>confirmed wording</span>")
        else:
            badges.append("<span class='badge b-unk'>unconfirmed</span>")
        if item.get("observation_machine"):
            badges.append("<span class='badge b-mach'>machine suggestion</span>")
        vis = item.get("visibility") or "private"
        badges.append(f"<span class='badge b-{vis[:4] if vis!='private' else 'priv'}'>{_esc(vis)}</span>")
        evidence = {}
        try:
            evidence = json.loads(item.get("identity_evidence") or "{}")
        except json.JSONDecodeError:
            evidence = {}
        lanes = evidence.get("lanes") or []
        lane_txt = ", ".join(f"{l.get('name')}→{l.get('job_ref')}" for l in lanes) or "none"
        cards.append(
            f"<article class='{klass}' data-blob='{_esc(_blob(item))}'>"
            f"<label style='display:block'>{media}"
            f"<div class='body'><input class='selbox' type='checkbox' value='{item['id']}'{checked}> "
            f"<strong>{_esc(Path(item['source_path']).name)}</strong>"
            f"<div class='badges'>{''.join(badges)}</div>"
            f"<div><span class='label'>Site / job</span> {_unknown(item.get('site_identity'))} · {_unknown(item.get('filed_job_ref') or item.get('staged_job_ref'))}</div>"
            f"<div><span class='label'>Capture / source</span> {_unknown(item.get('capture_date'))} · {_unknown(item.get('source_album'))}</div>"
            f"<div><span class='label'>Phase</span> {_unknown(item.get('phase'))}</div>"
            f"<div><span class='label'>Location</span> {_unknown(item.get('roof_area'))}</div>"
            f"<div><span class='label'>Component</span> {_unknown(item.get('component'))}</div>"
            f"<div><span class='label'>Condition / defect</span> {_unknown(item.get('condition_defect'))}</div>"
            f"<div><span class='label'>Work / action</span> {_unknown(item.get('work_action'))}</div>"
            f"<div><span class='label'>Before / after</span> {_unknown(item.get('before_after'))}</div>"
            f"<div><span class='label'>Confirmed observation</span> {_unknown(item.get('observation_confirmed'))}</div>"
            f"<div><span class='label'>Machine suggestion</span> {_unknown(item.get('observation_machine'))}</div>"
            f"<div><span class='label'>Identity evidence</span> {_esc(lane_txt)} · {_esc(evidence.get('reason') or item.get('identity_status'))}</div>"
            f"<div><span class='label'>Hash</span> {_esc((item.get('file_hash') or '')[:12])}…</div>"
            f"</div></label></article>"
        )

    sel_links = " · ".join(
        f"<a href='/job/{_esc(job_ref)}?selection={urllib.parse.quote(s['name'])}'>{_esc(s['name'])}</a>"
        for s in selections
    ) or "<span class='unknown'>none saved</span>"
    stable = paths.job_url(job_ref)
    pub = cabinet.latest_publication(conn, job_ref, "report")
    report_link = ""
    if pub:
        report_link = f" · <a href='/export/{pub['id']}'>latest report PDF</a>"

    body = f"""
<div class='banner'>
  <h1>{_esc(site)} <span class='meta'>({_esc(job_ref)})</span></h1>
  <div class='meta'>Image Plane cabinet · stable URL <a href='{stable}'>{stable}</a>
  · {len(items)} records · {resolved} filed · {quarantined} unresolved · {videos} video
  · showing <span id='shown'>{len(filtered)}</span>{report_link}</div>
  <div class='meta'>Saved selections: {sel_links}</div>
  <div class='meta'>Glengarry action: open this exact URL. No job-reference re-entry.</div>
</div>
{historic_note}
<div class='toolbar'>
  <input id='q' type='search' placeholder='Search this job' value='{_esc(query)}' oninput='applyView()'>
  <input id='selname' type='text' placeholder='Selection name' value='{_esc(selection_name or "")}'>
  <button type='button' onclick='saveSelection()'>Save selection</button>
  <button type='button' onclick='setVis("approved")'>Approve visibility</button>
  <button type='button' onclick='setVis("private")'>Make private</button>
  <button type='button' onclick='makeReport()'>Report PDF</button>
  <button type='button' onclick='makePack()'>Installer pack</button>
  <button type='button' onclick='prepGRA()'>Prepare GRA copies</button>
</div>
<div class='chips'>{''.join(chips)}</div>
<div class='grid'>{''.join(cards) or "<div class='empty'>No cabinet records on this job.</div>"}</div>
<div class='footer'>
  Confirmed wording is green. Machine suggestions are purple and never enter a report as fact.
  Unresolved identity stays visible in quarantine. Originals are not served from incoming.
</div>
"""
    return (
        "<!doctype html><meta charset='utf-8'><title>Image Plane "
        f"{_esc(job_ref)}</title><meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<style>{CSS}</style><div class='wrap'>{body}</div><script>{JS}</script>"
    )


def render_index(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        """SELECT COALESCE(filed_job_ref, staged_job_ref) job_ref, COUNT(*) n
           FROM cabinet_items GROUP BY 1 ORDER BY 1"""
    ).fetchall()
    links = []
    for r in rows:
        if not r["job_ref"]:
            continue
        links.append(
            f"<li><a href='/job/{_esc(r['job_ref'])}'>{_esc(paths.site_name(r['job_ref']))} "
            f"({_esc(r['job_ref'])})</a> — {r['n']} records</li>"
        )
    return (
        "<!doctype html><meta charset='utf-8'><title>Image Plane</title>"
        f"<style>{CSS}</style><div class='wrap'><div class='banner'><h1>Image Plane</h1>"
        f"<p class='meta'>Stable job URLs live at /job/&lt;ref&gt;. Pancras: "
        f"<a href='/job/{paths.PANCRAS_JOB}'>/job/{paths.PANCRAS_JOB}</a></p></div>"
        f"<ul>{''.join(links) or '<li class=unknown>No cabinet jobs yet</li>'}</ul></div>"
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "ImagePlane/1"

    def log_message(self, fmt, *args):
        log.info("%s " + fmt, self.address_string(), *args)

    def _db(self) -> sqlite3.Connection:
        return dbmod.connect(self.server.db_path)

    def _send(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict):
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        conn = self._db()
        try:
            if path in {"/", "/jobs"}:
                return self._send(200, render_index(conn).encode("utf-8"))
            if path.startswith("/job/") and "/api" not in path and path.count("/") == 2:
                job_ref = urllib.parse.unquote(path.split("/")[2])
                html = render_job(
                    conn,
                    job_ref,
                    (qs.get("q") or [""])[0],
                    qs.get("filter") or [],
                    (qs.get("selection") or [None])[0],
                )
                return self._send(200, html.encode("utf-8"))
            if path.startswith("/thumb/"):
                return self._file_from_item(conn, int(path.split("/")[2]), thumb=True)
            if path.startswith("/media/"):
                return self._file_from_item(conn, int(path.split("/")[2]), thumb=False)
            if path.startswith("/export/"):
                return self._export(conn, int(path.split("/")[2]))
            if path.startswith("/glengarry/"):
                job_ref = urllib.parse.unquote(path.split("/")[2])
                self.send_response(302)
                self.send_header("Location", f"/job/{job_ref}")
                self.end_headers()
                return
            if path == "/api/glengarry/link":
                job_ref = (qs.get("job") or [paths.PANCRAS_JOB])[0]
                return self._json(200, {"job_ref": job_ref, "url": paths.job_url(job_ref), "path": f"/job/{job_ref}"})
            if path.startswith("/api/job/") and path.endswith("/items"):
                job_ref = urllib.parse.unquote(path.split("/")[3])
                return self._json(200, {"items": cabinet.items_for_job(conn, job_ref)})
            if path.startswith("/api/selection/"):
                name = urllib.parse.unquote(path.split("/")[3])
                job_ref = (qs.get("job") or [paths.PANCRAS_JOB])[0]
                sel = cabinet.get_selection(conn, job_ref, name)
                if not sel:
                    return self._json(404, {"error": "selection not found"})
                confirmed = [
                    i
                    for i in sel["items"]
                    if i and i.get("confirmation_state") == "confirmed" and i.get("observation_confirmed")
                ]
                return self._json(200, {"selection": name, "job_ref": job_ref, "confirmed_items": confirmed})
            self._send(404, b"not found")
        finally:
            conn.close()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        conn = self._db()
        try:
            body = self._read_json()
            if path.startswith("/job/") and path.endswith("/selection"):
                job_ref = urllib.parse.unquote(path.split("/")[2])
                sel = cabinet.save_selection(conn, job_ref, body["name"], body.get("item_ids") or [])
                return self._json(200, {"name": sel["name"], "item_ids": json.loads(sel["item_ids"])})
            if path.startswith("/job/") and path.endswith("/visibility"):
                cabinet.set_visibility(conn, body.get("item_ids") or [], body.get("visibility") or "private")
                return self._json(200, {"ok": True})
            if path.startswith("/job/") and path.endswith("/report"):
                job_ref = urllib.parse.unquote(path.split("/")[2])
                dest = report.build_report_pdf(conn, job_ref, body["selection"])
                pub = cabinet.latest_publication(conn, job_ref, "report")
                return self._json(200, {"path": str(dest), "url": f"/export/{pub['id']}"})
            if path.startswith("/job/") and path.endswith("/pack"):
                job_ref = urllib.parse.unquote(path.split("/")[2])
                dest = pack.export_pack(conn, job_ref, body["selection"])
                pub = cabinet.latest_publication(conn, job_ref, "pack")
                return self._json(200, {"path": str(dest), "url": f"/export/{pub['id']}"})
            if path.startswith("/job/") and path.endswith("/gra"):
                job_ref = urllib.parse.unquote(path.split("/")[2])
                payload = gra.prepare_publication(
                    conn, job_ref, body["selection"], gra_event_ref=body.get("gra_event_ref")
                )
                return self._json(200, payload)
            if path == "/api/albums/discover":
                return self._json(200, albums.discover_google_albums(conn))
            self._json(404, {"error": "not found"})
        except KeyError as e:
            self._json(404, {"error": str(e)})
        except Exception as e:
            log.exception("POST failed")
            self._json(400, {"error": str(e)})
        finally:
            conn.close()

    def _file_from_item(self, conn, item_id: int, thumb: bool):
        item = cabinet.get_item(conn, item_id)
        if not item:
            return self._send(404, b"missing")
        path = Path(item["thumb_path"] if thumb and item.get("thumb_path") else item["cabinet_path"])
        if not path.is_file():
            return self._send(404, b"file missing")
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f"inline; filename=\"{path.name}\"")
        self.end_headers()
        self.wfile.write(data)

    def _export(self, conn, pub_id: int):
        row = conn.execute("SELECT * FROM cabinet_publications WHERE id = ?", (pub_id,)).fetchone()
        if not row:
            return self._send(404, b"missing export")
        path = Path(row["output_path"])
        if path.is_dir():
            pdf = path / "pack.pdf"
            path = pdf if pdf.is_file() else path / "manifest.json"
        if not path.is_file():
            return self._send(404, b"export file missing")
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Disposition", f"inline; filename=\"{path.name}\"")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class CabinetServer(ThreadingHTTPServer):
    def __init__(self, host: str, port: int, db_path: Path):
        super().__init__((host, port), Handler)
        self.db_path = db_path


def serve(host: str = "0.0.0.0", port: int = paths.DEFAULT_PORT, db_path: Path | None = None) -> None:
    db_path = db_path or dbmod.DEFAULT_DB
    dbmod.connect(db_path).close()
    httpd = CabinetServer(host, port, db_path)
    log.info("Image Plane job screen on http://%s:%s/job/%s", host, port, paths.PANCRAS_JOB)
    httpd.serve_forever()
