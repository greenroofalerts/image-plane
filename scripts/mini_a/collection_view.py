"""Extend Image Plane's private job/event presentation with searchable keywords."""
import html,json,os,time,urllib.parse,sqlite3
from pathlib import Path
from collections import defaultdict
from collection_sources import write_json,digest

def esc(x):return html.escape(str(x or ''))
def reader_health(state,status):
 try: health=json.loads((state/'reader-health.json').read_text())
 except (OSError,ValueError):health={'state':'unknown','reason':'Reader quality has no recorded acceptance result.'}
 last=None
 try:
  db=sqlite3.connect('file:'+str(state/'collection-progress.sqlite')+'?mode=ro',uri=True)
  try:
   row=db.execute('select max(finished) from receipts where processed > 0').fetchone()
   last=row[0] if row else None
  finally:db.close()
 except sqlite3.Error:pass
 clock=lambda value:time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime(value)) if value else 'Not recorded'
 pending=status.get('states',{}).get('pending_model',0)
 notice=('<section class="notice" role="alert"><h2>Image reading: '+esc(health['state'])+'</h2><p>'+esc(health.get('reason'))+'</p>'
  '<p>'+str(pending)+' file records await model reading. Existing machine keywords have not been validated by this evaluation.</p>'
  '<p>'+esc(health.get('mitigation','No accepted replacement reader is recorded.'))+'</p>'
  '<p>Automatic failure notification to Lee: '+esc(health.get('notification','not connected'))+'.</p></section>')
 timing='<p class="sub">Last source check: '+clock(status.get('finished'))+' · Last batch that processed files: '+clock(last)+'</p>'
 return notice,timing

def render(base,state,results,status):
 out=state/'view';out.mkdir(exist_ok=True)
 jobs=defaultdict(list)
 for r in results:jobs[r['identity'].get('job_ref') or 'unresolved'].append(r)
 # Keep the established dark job/event layout, named-event sections and photo-date
 # order. This private extension does not curate or publish customer images.
 style="""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Image Plane · collection</title><style>body{background:#0f0f10;color:#e8e8e8;font:16px/1.5 -apple-system,system-ui,sans-serif;margin:0 auto;max-width:1250px;padding:24px}a{color:#9dddca}h1{font-size:28px}.sub{color:#b3c1c5}.notice{border-left:4px solid #e8a06a;padding:12px;background:#25201c}.bundle{border:1px solid #34383a;border-radius:10px;margin:24px 0;padding:16px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}figure{margin:0}img{width:100%;height:330px;object-fit:contain;background:#161819}figcaption{font-size:14px;overflow-wrap:anywhere}.tag{display:inline-block;border:1px solid #4b6860;padding:3px 8px;margin:3px;border-radius:12px}.machine{border-style:dashed;color:#c8c3ad}input{font:inherit;padding:10px;background:#202629;color:white;border:1px solid #6e7c82;width:80%;max-width:600px}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:12px;border-bottom:1px solid #34383a}summary{cursor:pointer}a:focus,input:focus{outline:3px solid #d7b45b}@media(max-width:500px){body{padding:14px}.grid{grid-template-columns:1fr}}</style>"""
 warning='<p class="notice">Private collection. Job links and event memberships are provisional unless individually settled. Machine keywords are proposals. No invoice, payment, consent or customer publication is inferred.</p>'
 health,timing=reader_health(state,status)
 nav='<a href="/collection">← All jobs and source coverage</a>'
 script="""<script>document.querySelector('#search').addEventListener('input',e=>{const terms=e.target.value.toLowerCase().split(/\\s+/).filter(Boolean);document.querySelectorAll('[data-search]').forEach(el=>el.hidden=!terms.every(t=>el.dataset.search.includes(t)));});</script>"""
 for ref,photos in jobs.items():
  identity=photos[0]['identity'];label=(ref+' · '+str(identity.get('display_name') or 'Site identity unresolved')) if ref!='unresolved' else 'Unresolved photo identities'
  parts=[style,nav,'<h1>'+esc(label)+'</h1>',health,timing,warning,'<label>Filter photographs by keyword or original name<br><input id="search" type="search" placeholder="e.g. parapet moss"></label>']
  events=defaultdict(list)
  for r in photos:events[r['event']['id']].append(r)
  for group in sorted(events.values(),key=lambda g:g[0]['event'].get('start') or ''):
   ev=group[0]['event'];parts.append('<section class="bundle"><h2>'+esc(ev['name'])+'</h2><p>'+esc(ev['start'] or 'Undated')+' — '+esc(ev['end'] or '')+' · '+str(len(group))+' photographs</p><p class="sub">'+esc(ev['basis'])+'</p><div class="grid">')
   for r in sorted(group,key=lambda r:(r.get('date') or '',r['original_name'])):
    words=r['keywords'];search=' '.join(words['lee']+words['original_words']+words['machine_proposals']+[r['original_name']]).lower()
    img='/collection/thumb/'+r['sha256']+'.jpg'
    tags=''.join('<span class="tag">'+esc(t)+' · Lee</span>' for t in words['lee'])+''.join('<span class="tag machine">'+esc(t)+' · proposed</span>' for t in words['machine_proposals'])
    parts.append('<figure data-search="'+esc(search)+'"><a href="'+img+'"><img loading="lazy" src="'+img+'" alt="'+esc(r['original_name'])+'"></a><figcaption>'+esc(r['original_name'])+' · '+esc(r.get('date') or 'Date unresolved')+'<br>'+tags+'<details><summary>Original and attribution</summary><p>'+esc(r['path'])+'</p><p>'+esc(r['identity']['job']['state'])+' photo/job link · '+esc(r['date_source'])+'</p></details></figcaption></figure>')
   parts.append('</div></section>')
  parts.extend([script,'</html>']);tmp=out/(ref+'.html.tmp');tmp.write_text('\n'.join(parts));os.replace(tmp,out/(ref+'.html'))
 checks=json.loads((state/'source-check.json').read_text());table=[]
 for c in checks['collections']:table.append('<tr><td>'+esc(c['root'])+'</td><td>'+str(c['image_members'])+'</td><td>'+str(c['album_or_folder_count'])+'</td><td>'+('Checked' if c['available'] else 'Unavailable')+'</td></tr>')
 parts=[style,'<h1>Image Plane · local collection</h1>',health,timing,warning,
 '<p>'+str(status['population'])+' source paths accounted for · '+str(status['unique_contents_processed'])+' distinct photos indexed · '+str(status['photos_with_keywords'])+' distinct photos with existing keywords.</p>',
 '<p class="notice">Coverage is the enumerated local imports and ledgers. Live Google Photos is not connected; the complete online album denominator remains unknown. Missing originals and unresolved work remain counted below.</p>',
 '<p>'+esc(json.dumps(status['states'],sort_keys=True))+'</p>',
 '<h2>Jobs with processed photographs</h2><label>Find a job or site<br><input id="search" type="search"></label><table><tr><th>Job / site</th><th>Photographs</th><th>Keywords</th></tr>']
 for ref,photos in sorted(jobs.items()):
  label=ref+' · '+str(photos[0]['identity'].get('display_name') or 'Site identity unresolved');labels=sum(bool(r['keywords']['lee'] or r['keywords']['machine_proposals']) for r in photos)
  parts.append('<tr data-search="'+esc(label.lower())+'"><td><a href="/collection/job/'+urllib.parse.quote(ref)+'">'+esc(label)+'</a></td><td>'+str(len(photos))+'</td><td>'+str(labels)+'</td></tr>')
 parts.extend(['</table><h2>Sources checked</h2><table><tr><th>Local source</th><th>Images</th><th>Albums / folders</th><th>Status</th></tr>',''.join(table),'</table>',script,'</html>'])
 tmp=out/'index.html.tmp';tmp.write_text('\n'.join(parts));os.replace(tmp,out/'index.html')
 write_json(state/'view-use-receipt.json',{'source_revision':status['source_revision'],'rows_used':len(results),'job_pages':len(jobs),'output':str(out/'index.html'),'rendered_at':time.time(),'customer_publication':False})
