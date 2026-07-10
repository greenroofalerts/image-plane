#!/usr/bin/env python3
# STEP 4 — Rebuild the WHOLE view. Generalises build_301_14.py to every job.
#  - billing resolved from Xero (both tenants, job_ref-keyed) + GRA site header
#  - grouped by BILLABLE EVENT (multi-day install = one event), day-sorted, chronological
#  - near-dupes already physically removed (STEP 1); undated album photos EXIF-recovered
#  - provenance labels ("matched by photo date / Xero unavailable / photo-date order") REMOVED
#  - Olympic-Mews-style same-postcode ambiguous photos -> a "needs Lee" pseudo-page, never forced
import json, os, re, html, hashlib, subprocess, datetime, sys
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/image-plane"))
import guards  # F1 render guards: counts_footer (docs/F1-GUARDS-SPEC-2026-07-10.md)
# NOTE: this builder renders no photo captions or species names (thumbnail
# grid + health badges only) -- D3/D4 are no-ops here; D2 (counts_footer) is
# wired into both index.html and every job page below.

IP=os.path.expanduser("~/image-plane"); G=os.path.join(IP,"grind")
OUT=os.path.join(G,"site_view"); THUMBS=os.path.join(OUT,"thumbs"); JOBS=os.path.join(OUT,"jobs")
os.makedirs(THUMBS,exist_ok=True); os.makedirs(JOBS,exist_ok=True)
# wipe stale job pages from prior builds (keep thumbs) so no old provenance labels linger
import glob as _glob
for _f in _glob.glob(os.path.join(JOBS,"*.html")):
    try: os.remove(_f)
    except: pass
THUMB_EDGE=480
def nr(x):
    m=re.match(r"\s*0*(\d+)-(\d{2})\b",str(x or "")); return f"{m.group(1)}-{m.group(2)}" if m else None
def esc(s): return html.escape(str(s if s is not None else ""))
def thumb_name(p): return hashlib.md5(p.encode()).hexdigest()[:16]+".jpg"
def dparse(s): return datetime.date.fromisoformat(s)

# ---- allocation -> photos per job ----
jobs=defaultdict(list); cluster_photos=defaultdict(list); own_photos=[]
for l in open(os.path.join(G,"allocation_v2.jsonl")):
    try: r=json.loads(l)
    except: continue
    if not os.path.exists(r["path"]): continue
    if r.get("own_premises"):
        own_photos.append(r)
    elif r.get("confidence")=="needs_lee":
        key="+".join(r.get("candidates",[r["job_ref"]]))
        cluster_photos[key].append(r)
    else:
        jobs[nr(r["job_ref"])].append(r)

# ---- date recovery for album/undated (path date already present for iCloud) ----
PATH_DATE=re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")
ALBUM_MD=re.compile(r"\b(\d{1,2})-(\d{1,2})-(\d{2,4})\b")
def date_from_path(p):
    m=PATH_DATE.search(p)
    if m:
        try: return datetime.date(int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
        except: return None
    return None
def exif_date(p):
    try:
        out=subprocess.run(["mdls","-name","kMDItemContentCreationDate","-raw",p],
                           capture_output=True,text=True,timeout=20).stdout.strip()
        m=re.match(r"(\d{4})-(\d{2})-(\d{2})",out)
        if m: return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    except: pass
    return None
allrows=[r for v in jobs.values() for r in v]+[r for v in cluster_photos.values() for r in v]+own_photos
need=[r for r in allrows if not r.get("date")]
def _d(r):
    d=date_from_path(r["path"]) or exif_date(r["path"]); return r["path"],d
with ThreadPoolExecutor(max_workers=8) as ex:
    dd={p:d for p,d in ex.map(_d,need)}
for r in need: r["date"]=dd.get(r["path"])

# ---- ensure thumbs for all rendered photos ----
def make_thumb(p):
    o=os.path.join(THUMBS,thumb_name(p))
    if os.path.exists(o) and os.path.getsize(o)>0: return
    try: subprocess.run(["sips","-s","format","jpeg","-Z",str(THUMB_EDGE),p,"--out",o],
                        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)
    except: pass
with ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(make_thumb,[r["path"] for r in allrows]))

# ---- billing per job (Xero both tenants, job_ref keyed) ----
xero=json.load(open(os.path.join(G,"xero_invoice_events_all.json")))
bill_by_ref=defaultdict(list)
INSTALL_KW=re.compile(r"instal|repair|replace|waterproof|gutter|chimney|fascia|dormer|advance|balance|deposit|works|build|construct|fit",re.I)
for e in xero:
    ref=nr(e["job_ref"])
    if not ref: continue
    bill_by_ref[ref].append({"date":(e.get("date") or "")[:10],"description":e.get("description",""),
                             "contact":e.get("contact",""),"tenant":e.get("tenant",""),
                             "is_install":bool(INSTALL_KW.search(e.get("description","")))})

# ---- site header maps ----
gra={nr(g["job_ref"]):g for g in json.load(open(os.path.join(G,"gra_sites.json"))) if nr(g["job_ref"])}
import csv
site_name={}
for r in csv.DictReader(open(os.path.join(IP,"portfolio_register.csv"))):
    ref=nr(r["job_ref"]);
    if ref: site_name[ref]=r.get("site","") or ""

# ---- roof health per photo: model pass v1, overridden by Lee's hand labels ----
# Model grades run generous (never worse than Lee): its "poor" is trustworthy,
# its "patchy" can hide worse. Lee's knowledge_notes health always wins.
health={}  # path -> {"grade","src"}
GRADES={"healthy","patchy","poor","dead"}  # anything else in the field is not a grade
_hp=os.path.join(G,"health_pass_v1.jsonl")
if os.path.exists(_hp):
    for l in open(_hp):
        try: r=json.loads(l)
        except: continue
        g=(r.get("health") or "").strip().lower()
        if g in GRADES: health[r["path"]]={"grade":g,"src":"model"}
_kn=os.path.join(IP,"knowledge_notes.jsonl")
if os.path.exists(_kn):
    for l in open(_kn):
        try: r=json.loads(l)
        except: continue
        p=r.get("path"); g=(r.get("health") or "").strip().lower()
        if p and g in GRADES: health[p]={"grade":g,"src":"lee"}
def hb_cls(g): return re.sub(r"[^a-z0-9]+","-",g)

# ---- associated job numbers: present these together (Lee's rulings) ----
# canonical page ref -> every number to show + bill under it, in display order
ASSOC={
    "651-16":["651-16","652-16"],     # Litten Place: two roofs on one property, blended into one record
    # De Beauvoir is 1701-24 ONLY. 1703-24 is a SEPARATE site (The Hickman, Whitechapel) with its own page.
}
def assoc_refs(ref): return ASSOC.get(ref,[ref])
def head_label(ref): return " / ".join(assoc_refs(ref))
# refs whose portfolio site label is conflated/wrong — keep the number (billing) but hide its address
SUPPRESS_ADDR=set()  # (was {"1703-24"}) The Hickman is now its own job 1703-24 and shows its own address.
def addr_for(ref):
    seen=[]
    for x in assoc_refs(ref):
        if x in SUPPRESS_ADDR: continue
        a=(gra.get(x,{}).get("address") or site_name.get(x,"")).strip()
        if a and a not in seen: seen.append(a)
    return " & ".join(seen)

PAGE_CSS="""<!doctype html><meta charset='utf-8'><title>Job</title><style>
body{background:#0f0f10;color:#e8e8e8;font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:0 28px 80px}
a.back{display:inline-block;color:#7fb;text-decoration:none;padding:16px 0 0}
h1{font-size:20px;font-weight:650;padding:8px 0 2px}
.sub{color:#9aa;font-size:13px;margin-bottom:16px}
.sub.warn,.warn{color:#e8a06a}
.bundle{margin:0 0 22px;border:1px solid #222;border-radius:10px;overflow:hidden;background:#141416}
.bhdr{display:flex;align-items:baseline;gap:14px;padding:10px 14px;background:#1b1c1f;border-left:5px solid #444}
.bhdr.install{border-left-color:#4ea1ff;background:#15243a}
.bhdr.maint{border-left-color:#4fd18b;background:#122a1e}
.bhdr.warn{border-left-color:#e8a06a;background:#2a2113}
.dt{font-weight:700;font-variant-numeric:tabular-nums;color:#fff;min-width:150px}
.lbl{font-weight:600;color:#cfe}
.bhdr.install .lbl{color:#9cc8ff}.bhdr.maint .lbl{color:#8ef0b8}.bhdr.warn .lbl{color:#f0c48e}
.meta{margin-left:auto;color:#8a8f96;font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:6px;padding:10px}
.grid img{width:100%;height:130px;object-fit:cover;border-radius:4px;background:#000;display:block}
.daytag{grid-column:1/-1;color:#7fb;font-size:11px;text-transform:uppercase;letter-spacing:.05em;padding:8px 2px 2px}
.bill{padding:4px 14px;color:#8a8f96;font-size:12px}.bill .bdt{color:#cfe;font-variant-numeric:tabular-nums}
.ev{padding:7px 14px;margin:0 0 8px;border-left:5px solid #555;background:#141416;font-size:13px;color:#aab}
.ev.install{border-left-color:#4ea1ff;background:#15243a;color:#9cc8ff}
.ev .dt{min-width:110px;display:inline-block}.ev .xdesc{color:#888;font-style:italic}
.ph{position:relative;display:block}
.hb{position:absolute;left:4px;bottom:4px;font-size:10px;font-weight:600;padding:1px 6px;border-radius:3px;background:rgba(0,0,0,.78);color:#ddd}
.hb-healthy{color:#8ef0b8}.hb-patchy{color:#e8c76a}.hb-poor{color:#e8a06a}.hb-dead{color:#f08e8e}
.counts-footer{margin:30px 0 0;padding:14px 0;border-top:1px solid #262626;color:#9aa;font-size:12.5px}
.counts-footer .counted-by,.counts-footer .counted-at{color:#767b80}
.counts-footer-error{color:#e0837e}
</style>"""

# D2 guard: computed ONCE per build run (this is a batch of static-file
# generations, not a live server -- "at render time" means at build time here)
# and reused across every job page + the index, never hardcoded.
COUNTS_FOOTER_HTML = guards.counts_footer()

def render_days(day_photos):
    out=["<div class='grid'>"]
    for day in sorted(day_photos):
        ph=sorted(day_photos[day],key=lambda r:r["path"])
        out.append(f"<div class='daytag'>{esc(day)} &middot; {len(ph)} photos</div>")
        for r in ph:
            h=health.get(r["path"]); badge=""
            if h:
                who="Lee" if h["src"]=="lee" else "model"
                badge=f"<span class='hb hb-{hb_cls(h['grade'])}'>{esc(h['grade'])} &middot; {who}</span>"
            out.append(f"<a class='ph' href='../thumbs/{thumb_name(r['path'])}' target='_blank'>"
                       f"<img loading='lazy' src='../thumbs/{thumb_name(r['path'])}'>{badge}</a>")
    out.append("</div>"); return "\n".join(out)

def build_events(photos, billing):
    # cluster photo days into sessions (gap>25d), attach nearby billing (+/-45d)
    day_photos=defaultdict(list); undated=[]
    for r in photos:
        (day_photos[r["date"]].append(r) if r.get("date") else undated.append(r))
    days=sorted(day_photos)
    sessions=[]
    for d in days:
        if sessions and (dparse(d)-dparse(sessions[-1][-1])).days<=25: sessions[-1].append(d)
        else: sessions.append([d])
    billing=sorted(billing,key=lambda e:e["date"] or "")
    events=[]
    for sess in sessions:
        s,e=sess[0],sess[-1]
        lo=(dparse(s)-datetime.timedelta(days=45)).isoformat(); hi=(dparse(e)+datetime.timedelta(days=45)).isoformat()
        binf=[b for b in billing if b["date"] and lo<=b["date"]<=hi]
        is_install=any(b["is_install"] for b in binf) or (dparse(e)-dparse(s)).days>=20
        if is_install: kind="install"; label="Install / works (multi-day)" if (dparse(e)-dparse(s)).days>=2 else "Install / works"
        elif binf: kind="maint"; label="Maintenance visit"
        else: kind="visit"; label="Site visit"
        events.append({"kind":kind,"label":label,"start":s,"end":e,"billings":binf,"days":sess})
    covered=set()
    for ev in events:
        for b in ev["billings"]: covered.add(b["date"]+"|"+b["description"])
    billed_only=[b for b in billing if b["date"] and (b["date"]+"|"+b["description"]) not in covered]
    return events, billed_only, day_photos, undated

def page(ref, photos, is_cluster=False, cluster_refs=None):
    billing=[] if is_cluster else [b for x in assoc_refs(ref) for b in bill_by_ref.get(x,[])]
    events,billed_only,day_photos,undated=build_events(photos,billing)
    g=gra.get(ref,{}); addr=(addr_for(ref) if not is_cluster else (g.get("address") or site_name.get(ref,"")).strip()); pc=(g.get("postcode") or "").strip()
    parts=[PAGE_CSS,"<a class='back' href='../index.html'>&larr; all jobs</a>"]
    if is_cluster:
        parts.append(f"<h1 class='warn'>Needs Lee &middot; same postcode, unit unknown</h1>")
        parts.append(f"<div class='sub warn'>{esc(pc)} &middot; candidate units: {esc(', '.join(cluster_refs))}. "
                     f"GPS cannot separate these units &mdash; {len(photos)} photos await your call. "
                     f"Album-labelled photos are already filed to the correct unit.</div>")
    else:
        head=f"{esc(head_label(ref))}" + (f" &middot; {esc(addr)}" if addr else "") + (f" &middot; {esc(pc)}" if pc else "")
        parts.append(f"<h1>{head}</h1>")
        nb=len(billing)
        parts.append(f"<div class='sub'>{len(events)} events &middot; {len(photos)} photos &middot; "
                     f"{nb} billed events on file. Ordered chronologically.</div>")
    gr=[r for r in photos if r["path"] in health]
    if gr:
        nlee=sum(1 for r in gr if health[r["path"]]["src"]=="lee"); nmod=len(gr)-nlee
        bits=[]
        if nlee: bits.append(f"{nlee} graded by Lee")
        if nmod: bits.append(f"{nmod} graded by the vision model")
        line=f"Roof health shown on {len(gr)} photos ({', '.join(bits)})."
        if nmod: line+=" The model reads generous &mdash; where it says poor, believe it; where it says patchy, the roof may be worse."
        parts.append(f"<div class='sub'>{line}</div>")
    timeline=[("event",ev["start"],ev) for ev in events]+[("billed",b["date"],b) for b in billed_only]
    timeline.sort(key=lambda t:t[1] or "")
    for kind,d0,item in timeline:
        if kind=="billed":
            cls="install" if item.get("is_install") else ""
            parts.append(f"<div class='ev {cls}'><span class='dt'>{esc(item['date'])}</span> "
                         f"<span class='lbl'>Billed event</span> "
                         f"<span class='xdesc'>&ldquo;{esc(item['description'][:80])}&rdquo;</span></div>")
            continue
        ev=item; lblcls=ev["kind"] if ev["kind"] in ("install","maint") else "warn"
        span=esc(ev["start"]) if ev["start"]==ev["end"] else f"{esc(ev['start'])} &rarr; {esc(ev['end'])}"
        nph=sum(len(day_photos[d]) for d in ev["days"])
        parts.append(f"<div class='bundle'><div class='bhdr {lblcls}'>"
                     f"<span class='dt'>{span}</span> <span class='lbl'>{esc(ev['label'])}</span>"
                     f"<span class='meta'>{nph} photos &middot; {len(ev['days'])} day(s)</span></div>")
        for b in ev["billings"]:
            parts.append(f"<div class='bill'><span class='bdt'>{esc(b['date'])}</span> "
                         f"&ldquo;{esc(b['description'][:80])}&rdquo;</div>")
        parts.append(render_days({d:day_photos[d] for d in ev["days"]}))
        parts.append("</div>")
    if undated:
        parts.append("<div class='bundle'><div class='bhdr warn'><span class='dt'>date unknown</span> "
                     f"<span class='lbl'>Undated</span><span class='meta'>{len(undated)} photos</span></div>")
        parts.append(render_days({"undated":undated})); parts.append("</div>")
    parts.append(f"<div class='counts-footer'>{COUNTS_FOOTER_HTML}</div>")
    fn=("cluster_"+ref.replace("+","_") if is_cluster else ref)+".html"
    open(os.path.join(JOBS,fn),"w").write("\n".join(parts))
    return fn, len(events), len(billing), len(photos)

# ---- render all job pages ----
def latest_health(photos):
    gr=sorted(((r.get("date") or "", health[r["path"]]) for r in photos if r["path"] in health),
              key=lambda t:t[0])
    if not gr: return ""
    h=gr[-1][1]
    return h["grade"]+(" (Lee)" if h["src"]=="lee" else " (model)")

rows=[]
for ref,photos in sorted(((k,v) for k,v in jobs.items() if k), key=lambda kv:(-len(kv[1]), kv[0])):  # no-ref rows (allocation_v2_flags no_job_ref) never render as a roof
    if not ref: continue
    fn,nev,nb,nph=page(ref,photos)
    g=gra.get(ref,{}); addr=addr_for(ref); pc=(g.get("postcode") or "").strip()
    rows.append({"ref":head_label(ref),"fn":fn,"addr":addr,"pc":pc,"photos":nph,"billed":nb,"warn":False,
                 "health":latest_health(photos)})
for key,photos in sorted(cluster_photos.items(), key=lambda kv:-len(kv[1])):
    crefs=key.split("+")
    fn,nev,nb,nph=page(key,photos,is_cluster=True,cluster_refs=crefs)
    g=gra.get(crefs[0],{}); pc=(g.get("postcode") or "").strip()
    rows.append({"ref":"needs Lee: "+", ".join(crefs),"fn":fn,"addr":"unit unknown (same postcode)","pc":pc,
                 "photos":nph,"billed":0,"warn":True})

# ---- own-premises bucket (Organic Roofs' own yard, NOT a client job) ----
if own_photos:
    events,billed_only,day_photos,undated=build_events(own_photos,[])
    parts=[PAGE_CSS,"<a class='back' href='../index.html'>&larr; all jobs</a>",
           "<h1>Britannia Wharf</h1>",
           f"<div class='sub'>Organic Roofs' own yard (Portslade BN41 1ET) &mdash; a distinct pile, not a client job. "
           f"{len(own_photos)} photos, grouped by visit, in date order.</div>"]
    timeline=[("event",ev["start"],ev) for ev in events]
    timeline.sort(key=lambda t:t[1] or "")
    for kind,d0,ev in timeline:
        span=esc(ev["start"]) if ev["start"]==ev["end"] else f"{esc(ev['start'])} &rarr; {esc(ev['end'])}"
        nph=sum(len(day_photos[d]) for d in ev["days"])
        parts.append(f"<div class='bundle'><div class='bhdr'>"
                     f"<span class='dt'>{span}</span> <span class='lbl'>Own premises visit</span>"
                     f"<span class='meta'>{nph} photos &middot; {len(ev['days'])} day(s)</span></div>")
        parts.append(render_days({d:day_photos[d] for d in ev["days"]}))
        parts.append("</div>")
    if undated:
        parts.append("<div class='bundle'><div class='bhdr'><span class='dt'>date unknown</span> "
                     f"<span class='lbl'>Undated</span><span class='meta'>{len(undated)} photos</span></div>")
        parts.append(render_days({"undated":undated})); parts.append("</div>")
    parts.append(f"<div class='counts-footer'>{COUNTS_FOOTER_HTML}</div>")
    open(os.path.join(JOBS,"own_britannia_wharf.html"),"w").write("\n".join(parts))
    rows.insert(0,{"ref":"Britannia Wharf","fn":"own_britannia_wharf.html",
                   "addr":"Organic Roofs' own yard — not a client job","pc":"BN41 1ET",
                   "photos":len(own_photos),"billed":0,"warn":False,"own":True})

# ---- index ----
INDEX_CSS="""<!doctype html><meta charset='utf-8'><title>Green-roof jobs</title><style>
body{background:#0f0f10;color:#e8e8e8;font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:0 28px 80px}
h1{font-size:22px;font-weight:650;padding:22px 0 4px}.sub{color:#9aa;font-size:13px;margin-bottom:16px;max-width:900px}
table{border-collapse:collapse;width:100%;max-width:1000px}
th{text-align:left;color:#7fb;font-size:12px;text-transform:uppercase;letter-spacing:.04em;padding:8px 12px;border-bottom:1px solid #333}
td{padding:9px 12px;border-bottom:1px solid #1e1e1e}tr:hover td{background:#17181a;cursor:pointer}
.ref{font-weight:700;color:#cfe;font-variant-numeric:tabular-nums}.pc{color:#9aa}
.num{text-align:right;font-variant-numeric:tabular-nums;color:#dfe}.warn{color:#e8a06a}.own{color:#8ecbff}
a{color:inherit;text-decoration:none}
.counts-footer{margin:30px 0 0;padding:14px 0;border-top:1px solid #262626;color:#9aa;font-size:12.5px;max-width:1000px}
.counts-footer .counted-by,.counts-footer .counted-at{color:#767b80}
.counts-footer-error{color:#e0837e}
</style>"""
total_photos=sum(r["photos"] for r in rows)
n_jobs=len([r for r in rows if not r.get("own")])
ip=[INDEX_CSS,"<h1>Green-roof photo record</h1>",
    f"<div class='sub'>{n_jobs} jobs with photos &middot; {total_photos} photos filed &middot; "
    f"billing from Xero (both companies), sites from GRA. Near-duplicate bursts removed. "
    f"Grouped by billable event, in date order. "
    f"Latest health = most recent graded photo; grades marked (model) come from the first "
    f"vision pass over the maintenance-sedum roofs and read generous &mdash; a model &ldquo;poor&rdquo; "
    f"is trustworthy, a model &ldquo;patchy&rdquo; may hide worse. Lee's own grades override.</div>",
    "<table><tr><th>Job</th><th>Site</th><th>Postcode</th><th class='num'>Photos</th><th class='num'>Billed events</th><th>Latest health</th></tr>"]
for r in rows:
    cls="own" if r.get("own") else ("warn" if r["warn"] else "")
    ip.append(f"<tr onclick=\"location.href='jobs/{r['fn']}'\"><td class='ref {cls}'>"
              f"<a href='jobs/{r['fn']}'>{esc(r['ref'])}</a></td>"
              f"<td class='{cls}'>{esc(r['addr'])}</td><td class='pc'>{esc(r['pc'])}</td>"
              f"<td class='num'>{r['photos']}</td><td class='num'>{r['billed'] or ''}</td>"
              f"<td class='pc'>{esc(r.get('health',''))}</td></tr>")
ip.append("</table>")
ip.append(f"<div class='counts-footer'>{COUNTS_FOOTER_HTML}</div>")
open(os.path.join(OUT,"index.html"),"w").write("\n".join(ip))
print(json.dumps({"job_pages":len([r for r in rows if not r['warn'] and not r.get('own')]),
                  "needs_lee_pages":len([r for r in rows if r['warn']]),
                  "own_premises_pages":len([r for r in rows if r.get('own')]),
                  "total_photos_filed":total_photos,
                  "index":os.path.join(OUT,"index.html")},indent=2))
