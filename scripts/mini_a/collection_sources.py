"""Recover existing local originals, annotations and vocabulary without rewriting them."""
import hashlib,json,os,re,time,urllib.request
from pathlib import Path
from collections import defaultdict

EXTS={'.jpg','.jpeg','.png','.heic','.heif','.tif','.tiff','.webp'}
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def sha_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def rows(p):
 if not p.exists():return []
 return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def write_json(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False));os.replace(tmp,p)
def record_ref(v):
 m=re.fullmatch(r'0*(\d+)-(\d{2})',str(v or '').strip());return str(int(m[1]))+'-'+m[2] if m else None

def refresh_canon(base,state):
 import pull_canon_snapshot as reader
 dest=state/'canon-input.json';old=json.loads(dest.read_text()) if dest.exists() else {}
 if old and time.time()-old.get('checked_epoch',0)<300:return old
 url,key,_=reader.find_credential();out={'records':{},'sources':{},'checked_epoch':time.time()}
 for table in ['spine_authority','job_registry']:
  collected=[]
  for offset in range(0,100000,500):
   query='select=*&order='+('id' if table=='spine_authority' else 'base_ref')+'&limit=500&offset='+str(offset)+('&status=eq.active' if table=='spine_authority' else '')
   req=urllib.request.Request(url.rstrip('/')+'/rest/v1/'+table+'?'+query,headers={'apikey':key,'Authorization':'Bearer '+key})
   with urllib.request.urlopen(req,timeout=30) as response:batch=json.loads(response.read())
   collected.extend(batch)
   if len(batch)<500:break
  else:raise ValueError('canonical pagination bound reached')
  if not collected:raise ValueError('empty authoritative source')
  out['records'][table]=collected
  out['sources'][table]={'availability':'available','authority':table,'lineage':table,'sha256':digest(collected),
                         'location':'LeeOSplus/public.'+table,'captured_at':out['checked_epoch']}
 out['revision']=digest(out['records']);write_json(dest,out);return out

def load_sources(base):
 names=['photo_ledger_merged.jsonl','takeout_ledger_merged.jsonl','takeout_index.jsonl','grind/allocation_v2.jsonl',
        'grind/visit_types_v4.jsonl','knowledge_notes.jsonl','grind/image_tags.jsonl','grind/note_attribution.jsonl',
        'grind/note_extractions.jsonl','grind/vision_categories_p1.jsonl','grind/vision_categories_p2.jsonl',
        'grind/vision_categories_takeout_p1.jsonl','grind/vision_categories_takeout_p2.jsonl']
 data={n:rows(base/n) for n in names}
 signatures={n:sha_file(base/n) if (base/n).exists() else 'unavailable' for n in names}
 out={'data':data,'signatures':signatures,'revision':digest(signatures)}
 tracking_path=base/'incoming/worker/source-captures/lee-originals/xero-job-tracking-options.json'
 out['job_companies']=defaultdict(set);out['xero_coverage']={}
 if tracking_path.exists():
  tracking=json.loads(tracking_path.read_text())
  for company,block in tracking.items():
   refs=set()
   for opt in block.get('options',[]):
    m=re.match(r'0*(\d{3,4})-(\d{2})(?![0-9])',str(opt.get('name','')).strip())
    if m:
     ref=str(int(m[1]))+'-'+m[2];refs.add(ref);out['job_companies'][ref].add(company)
   out['xero_coverage'][company]={'options':len(block.get('options',[])),'job_refs':len(refs),'refs':sorted(refs),'source_sha256':sha_file(tracking_path),'state':'historical tracking export; no current billing conclusion'}
 out['allocations']={r['path']:r for r in data['grind/allocation_v2.jsonl'] if r.get('path')}
 out['captions']={r['sha256']:r for n in names[:2] for r in data[n] if r.get('sha256') and r.get('response')}
 out['takeout']={r['path']:r for r in data['takeout_index.jsonl'] if r.get('path')}
 out['dates']={r['path']:r.get('date') for r in data['grind/allocation_v2.jsonl'] if r.get('path')}
 out['prior_labels']=defaultdict(list)
 for n in names[-4:]:
  for r in data[n]:
   if r.get('sha256'):out['prior_labels'][r['sha256']].extend(r.get('components') or [])
 return out

def recover_annotations(base,state,extra_roots=()):
 """Inventory every revision, but only the current note stream can supply labels.

 Backups and raw originals are retained for audit; copied rows are one assertion.
 Unknown grain and machine/unconfirmed notes are not spread onto photographs.
 """
 paths=set(base.glob('*notes*jsonl*'))|set(base.glob('knowledge_notes*'))
 for root in extra_roots:
  root=Path(root)
  if root.exists():
   for p in root.rglob('*'):
    if p.is_file() and not str(p).startswith(str(base/'incoming/worker/collection')) and p.suffix in ('.json','.jsonl','.txt','.md') and any(w in p.name.lower() for w in ['ground-truth','dictat','notes','vocab','word-list','teaching']):paths.add(p)
 manifest=[];seen={};current=rows(base/'knowledge_notes.jsonl');mapped=defaultdict(list);excluded=[]
 for p in sorted(paths):
  try:
   raw=p.read_bytes();h=hashlib.sha256(raw).hexdigest();entry={'path':str(p),'sha256':h,'bytes':len(raw),'state':'original retained; interpretation pending'}
   if h in seen:entry.update(state='identical copy',copy_of=seen[h])
   else:seen[h]=str(p)
   if p==base/'knowledge_notes.jsonl':entry['state']='current note stream'
   manifest.append(entry)
  except OSError as e:manifest.append({'path':str(p),'state':'unavailable','error':type(e).__name__})
 for i,r in enumerate(current,1):
  p=r.get('path');tags=r.get('tags')
  reason=None
  if r.get('unconfirmed') or r.get('confidence') in ('unconfirmed','machine'):reason='unconfirmed source'
  elif r.get('scope') in ('roof','job','rule') or r.get('kind') in ('rule','roof'):reason='not individual-photo grain'
  elif not p or not isinstance(tags,list):reason='no explicit photo/tag mapping'
  if reason:excluded.append({'line':i,'reason':reason});continue
  mapped[p].append({'line':i,'tags':tags,'remove':r.get('remove') or [],'note':r.get('note') or '',
                    'raw':r,'revision':digest(r),'source':str(base/'knowledge_notes.jsonl')})
 # Full current originals/revisions remain local and immutable in a content-addressed capture.
 revision=digest(manifest);write_json(state/'annotation-audit.json',{'sources':manifest,'current_rows':len(current),
    'photo_mapped_rows':sum(map(len,mapped.values())),'photo_paths':len(mapped),'unapplied':excluded,'revision':revision})
 return mapped,revision

def vocabulary(module,notes):
 terms={t for vals in module.VOCAB.values() for t in vals};terms.update(module.VISIT_TYPES_V4)
 # Preserve unmapped original words separately; do not silently turn machine-created
 # extraction strings into approved vocabulary.
 original_terms={str(t) for rs in notes.values() for r in rs for t in r['tags'] if isinstance(t,str)}
 return sorted(terms),sorted(original_terms)

def discover(base,sources,roots):
 """Full traversal of configured imports, plus every path in established ledgers."""
 members={};collections=[]
 for name in ['photo_ledger_merged.jsonl','takeout_ledger_merged.jsonl','takeout_index.jsonl']:
  for r in sources['data'][name]:
   p=r.get('path')
   if p:members.setdefault(p,{'path':p,'memberships':[]})['memberships'].append({'source':name,'album':r.get('album'),'source_sha256':r.get('sha256'),'album_ref':r.get('job_ref')})
 for root in roots:
  root=Path(root);count=0;albums=set()
  if root.exists():
   for p in root.rglob('*'):
    if p.is_file() and p.suffix.lower() in EXTS:
     count+=1;rel=p.relative_to(root);album=str(rel.parent);albums.add(album)
     members.setdefault(str(p),{'path':str(p),'memberships':[]})['memberships'].append({'source':str(root),'album':album})
  collections.append({'root':str(root),'available':root.exists(),'image_members':count,'album_or_folder_count':len(albums),'checked_at':time.time()})
 return members,collections
