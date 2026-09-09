"""Incremental historical extension of the existing Image Plane worker.

Private derived views and resumable processing receipts only. Canon, originals,
legacy allocations, customer publication and other product services are untouched.
"""
import argparse,collections,fcntl,hashlib,importlib.util,json,os,re,sqlite3,subprocess,sys,tempfile,time
from pathlib import Path
import collection_sources as source

VERSION='collection-continuation/1'
def load_module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def connect(state):
 state.mkdir(parents=True,exist_ok=True);db=sqlite3.connect(state/'collection-progress.sqlite');db.row_factory=sqlite3.Row
 db.executescript('''CREATE TABLE IF NOT EXISTS work(path TEXT PRIMARY KEY,stat TEXT,sha TEXT,memberships TEXT,revision TEXT,state TEXT DEFAULT 'pending',attempts INTEGER DEFAULT 0,next_retry REAL DEFAULT 0,error TEXT,result TEXT,updated REAL); CREATE TABLE IF NOT EXISTS readings(sha TEXT,version TEXT,labels TEXT,model TEXT,created REAL,PRIMARY KEY(sha,version)); CREATE TABLE IF NOT EXISTS receipts(id INTEGER PRIMARY KEY,started REAL,finished REAL,revision TEXT,processed INTEGER,model_calls INTEGER,errors INTEGER,kind TEXT);''');return db

def vocabulary_labels(text,vocab):
 # Existing conservative lexical mapping; proposals only, never Lee labels.
 labels=[]
 for (_,term),pattern in vocab.DESC_KEYWORDS.items():
  for hit in pattern.finditer(text):
   prefix=text[max(0,hit.start()-35):hit.start()].lower()
   if re.search(r'\b(no|not|without|absent|lack of)\b[^.;:]*$',prefix):continue
   labels.append(term);break
 return sorted(set(labels))

def original_labels(notes,vocab):
 labels=[];original=[]
 for row in notes:
  for t in row['tags']:
   if not isinstance(t,str):continue
   original.append(t);alias=vocab.NOTE_ALIASES.get(t.lower().replace('_','-').replace(' ','-'))
   labels.append(alias[1] if alias else t)
  for t in row.get('remove',[]):
   alias=vocab.NOTE_ALIASES.get(str(t).lower().replace('_','-').replace(' ','-'));target=alias[1] if alias else t
   labels=[x for x in labels if x!=target];original=[x for x in original if x!=t]
 return sorted(set(labels)),sorted(set(original))

def capture_day(path,known=None):
 # Date from original metadata first; no filesystem mtime as visit evidence.
 p=Path(path)
 exif='/opt/homebrew/bin/exiftool'
 if Path(exif).exists():
  r=subprocess.run([exif,'-j','-DateTimeOriginal','-CreateDate',str(p)],capture_output=True,text=True,timeout=20)
  if r.returncode==0:
   data=json.loads(r.stdout)[0];s=data.get('DateTimeOriginal') or data.get('CreateDate')
   if s and re.match(r'\d{4}:\d{2}:\d{2}',s):return s[:10].replace(':','-'),'EXIF'
 # Existing dated export path is a sourced fallback, not a billing date.
 m=re.search(r'/(20\d\d)/(\d\d)/(\d\d)/',str(p))
 if m:return '-'.join(m.groups()),'dated export path'
 if known and re.fullmatch(r'\d{4}-\d{2}-\d{2}',known):return known,'historical allocation date; not reverified'
 return None,'date unavailable'

def make_thumb(path,sha,state):
 dest=state/'thumbs'/(sha+'.jpg');dest.parent.mkdir(exist_ok=True)
 if dest.exists() and dest.read_bytes()[:2]==b'\xff\xd8':return dest
 tmp=dest.with_suffix('.tmp.jpg')
 r=subprocess.run(['sips','-s','format','jpeg','-Z','1100',path,'--out',str(tmp)],capture_output=True,timeout=40)
 if r.returncode or not tmp.exists() or tmp.read_bytes()[:2]!=b'\xff\xd8':raise ValueError('original could not be rendered')
 os.replace(tmp,dest);return dest

def local_labels(reader,path,terms,examples,model):
 # Reuse the deployed conversion routine's input contract and local Ollama
 # transport, with a strict response boundary instead of malformed -> [] success.
 import base64,urllib.request
 with tempfile.TemporaryDirectory(prefix='image-plane-label-') as t:
  dest=Path(t)/'input.jpg'
  r=subprocess.run(['sips','-s','format','jpeg','-Z','1100',path,'--out',str(dest)],capture_output=True,timeout=40)
  if r.returncode or not dest.exists():raise ValueError('conversion failed')
  image=base64.b64encode(dest.read_bytes()).decode()
 prompt=('Label only what is visually supported in this green-roof photograph. Use the surveyor’s existing vocabulary below. '
         'Select all applicable terms; do not force a count. Do not infer job identity, consent, billing or payment. '
         'Previous examples are general vocabulary context, not evidence about this photograph.\n'+examples+
         '\nReturn a JSON object with labels, containing only a short selection of clearly visible exact terms. Do not repeat the vocabulary list. Use an empty labels array when uncertain.\n'+json.dumps(terms))
 payload={'model':model,'prompt':prompt,'images':[image],'stream':False,'think':False,'format':{'type':'object','properties':{'labels':{'type':'array','maxItems':12,'uniqueItems':True,'items':{'type':'string','enum':terms}}},'required':['labels'],'additionalProperties':False},'options':{'num_ctx':8192,'temperature':0,'num_predict':500}}
 request=urllib.request.Request('http://127.0.0.1:11434/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=reader.reader_timeout()) as response:raw=json.loads(response.read())
 text=raw.get('response','').strip()
 if not text:raise ValueError('empty local reader response')
 labels=json.loads(text)
 if isinstance(labels,dict) and set(labels)=={'labels'}:labels=labels['labels']
 if not isinstance(labels,list) or any(not isinstance(t,str) or t not in terms for t in labels):raise ValueError('local model returned unsupported labels')
 return sorted(set(labels))


def run(config,limit=None,model_limit=None):
 base=Path(config['base']);state=base/'incoming/worker/collection';state.mkdir(parents=True,exist_ok=True)
 lock=open(base/'incoming/worker/collection.lock','a')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:return {'state':'already_running'}
 started=time.time();db=connect(state);processed=errors=calls=0
 sys.path.insert(0,config['spine_code']);from spine_evidence.image_plane import resolve_photo,event_for
 sys.path.insert(0,str(base));vocab=load_module('collection_vocab',base/'vocab_v2.py')
 inputs=source.load_sources(base);notes,notes_revision=source.recover_annotations(base,state,config.get('annotation_roots',[]))
 terms,original_words=source.vocabulary(vocab,notes)
 source.write_json(state/'vocabulary.json',{'approved_terms':terms,'original_note_terms':original_words,'source':str(base/'vocab_v2.py'),'sha256':source.sha_file(base/'vocab_v2.py')})
 try:canon=source.refresh_canon(base,state);canon_state='fresh'
 except Exception as e:
  p=state/'canon-input.json'
  if not p.exists():raise
  canon=json.loads(p.read_text());canon_state='stale: '+type(e).__name__
  for origin in canon['sources'].values():origin['availability']='unavailable'
 revision=source.digest([VERSION,source.sha_file(Path(__file__)),inputs['revision'],notes_revision,canon['revision'],canon_state,source.sha_file(base/'vocab_v2.py')])
 members,collections_checked=source.discover(base,inputs,config['roots'])
 for path,member in members.items():
  p=Path(path)
  try:s=p.stat();stamp=str(s.st_size)+':'+str(s.st_mtime_ns);availability='pending'
  except OSError:stamp='missing';availability='missing_original'
  prior=db.execute('select stat,revision,memberships,state from work where path=?',(path,)).fetchone();membership=json.dumps(member['memberships'],sort_keys=True)
  changed=not prior or prior['stat']!=stamp or prior['revision']!=revision or prior['memberships']!=membership
  if changed:
   db.execute('''insert into work(path,stat,memberships,revision,state,updated) values(?,?,?,?,?,?) on conflict(path) do update set sha=case when work.stat!=excluded.stat then NULL else work.sha end,stat=excluded.stat,memberships=excluded.memberships,revision=excluded.revision,state=excluded.state,attempts=0,next_retry=0,error=NULL,updated=excluded.updated''',(path,stamp,membership,revision,availability,time.time()))
 db.commit()
 source.write_json(state/'source-check.json',{'checked_at':time.time(),'collections':collections_checked,'ledger_signatures':inputs['signatures'],'canon_state':canon_state,'canon_checked_at':canon['checked_epoch'],'population':len(members),'live_google_photos':'browser connection unavailable; local exports only'})
 model_enabled=(model_limit if model_limit is not None else config.get('model_batch',4))>0
 todo=db.execute("select * from work where (state in ('pending','retry') or (state='pending_model' and ?)) and next_retry<=? order by case when state='pending_model' then 1 else 0 end,attempts,updated,path limit ?",(model_enabled,time.time(),limit or config.get('batch_size',150))).fetchall()
 reader=None
 label_version=source.digest([terms,source.sha_file(base/'fewshot_engine.py'),config.get('model','qwen2.5vl:3b'),'full-vocabulary-proposals/2'])
 for item in todo:
  path=item['path']
  try:
   sha=item['sha'] or source.sha_file(path);allocation=inputs['allocations'].get(path,{})
   member=json.loads(item['memberships']);refs={source.record_ref(m.get('album_ref')) for m in member};refs.discard(None)
   album=inputs['takeout'].get(path,{})
   if len(refs)>1:album_ref=None
   else:album_ref=next(iter(refs),source.record_ref(album.get('job_ref')))
   if not album_ref:
    named_refs={source.record_ref(x) for m in member for x in re.findall(r'(?<![0-9])\d{3,4}-\d{2}(?![0-9])',str(m.get('album') or ''))};named_refs.discard(None)
    if len(named_refs)==1:album_ref=next(iter(named_refs))
   identity=resolve_photo(path,sha,album_ref,allocation,canon)
   companies=sorted(inputs['job_companies'].get(identity.get('job_ref'),[]))
   identity['company']={'state':'proposed' if len(companies)==1 else 'unresolved','value':companies[0] if len(companies)==1 else None,'historical_tracking_candidates':companies}
   day,date_source=capture_day(path,inputs['dates'].get(path))
   event=event_for(identity,day,inputs['data']['grind/visit_types_v4.jsonl'])
   lee,original=original_labels(notes.get(path,[]),vocab)
   caption=inputs['captions'].get(sha,{});machine=vocabulary_labels(str(caption.get('response') or ''),vocab)
   prior=inputs['prior_labels'].get(sha,[])
   machine=sorted(set(machine)|{t for t in prior if isinstance(t,str) and t in terms})
   cached=db.execute('select labels from readings where sha=? and version=?',(sha,label_version)).fetchone()
   if cached:machine=sorted(set(machine)|set(json.loads(cached['labels'])))
   elif not lee and len(machine)<2 and calls<(model_limit if model_limit is not None else config.get('model_batch',4)):
    if reader is None:reader=load_module('collection_existing_reader',base/'fewshot_engine.py')
    # General examples from different original paths/jobs, no target or same-byte teaching.
    examples=[]
    for other,ns in notes.items():
     if other==path or source.record_ref(inputs['allocations'].get(other,{}).get('job_ref'))==identity.get('job_ref'):continue
     known=next((r for r in inputs['data']['photo_ledger_merged.jsonl'] if r.get('path')==other),{})
     if known.get('sha256')==sha:continue
     labs,_=original_labels(ns,vocab)
     if labs:examples.append('Prior approved label vocabulary example: '+', '.join(labs))
     if len(examples)==3:break
    calls+=1;extra=local_labels(reader,path,terms,'\n'.join(examples),config.get('model','qwen2.5vl:3b'))
    db.execute('insert or replace into readings values(?,?,?,?,?)',(sha,label_version,json.dumps(extra),config.get('model','qwen2.5vl:3b'),time.time()));machine=sorted(set(machine)|set(extra))
   removed={str(t) for row in notes.get(path,[]) for t in row.get('remove',[])}
   for t in list(removed):
    alias=vocab.NOTE_ALIASES.get(t.lower().replace('_','-').replace(' ','-'))
    if alias:removed.add(alias[1])
   machine=[t for t in machine if t not in removed]
   thumb=make_thumb(path,sha,state)
   result={'path':path,'sha256':sha,'original_name':Path(path).name,'memberships':member,'identity':identity,'event':event,'date':day,'date_source':date_source,
           'keywords':{'lee':lee,'original_words':original,'machine_proposals':sorted(set(machine)-set(lee))},'thumb':str(thumb),
           'source_revision':revision,'caption_reused':bool(caption),'canon_state':canon_state,'customer_publication':False,'processed_at':time.time()}
   status='processed' if lee or machine else 'keywords_unresolved' if cached or calls else 'pending_model'
   if not lee and not machine and not cached and calls >= (model_limit if model_limit is not None else config.get('model_batch',4)):
    status='pending_model' if not db.execute('select 1 from readings where sha=? and version=?',(sha,label_version)).fetchone() else 'keywords_unresolved'
   db.execute('update work set sha=?,state=?,result=?,error=NULL,updated=? where path=?',(sha,status,json.dumps(result),time.time(),path));db.commit();processed+=1
  except Exception as e:
   attempts=item['attempts']+1;errors+=1
   db.execute('update work set state=?,attempts=?,next_retry=?,error=?,updated=? where path=?',('retry' if attempts<3 else 'attention',attempts,time.time()+min(3600,60*2**attempts),type(e).__name__+': '+str(e)[:160],time.time(),path));db.commit()
 # Resolve missing historical locations only against a byte-verified retained
 # copy. Album membership survives; absence of one path is not loss of content.
 verified={r['sha']:json.loads(r['result']) for r in db.execute("select sha,result from work where sha is not null and result is not null and state in ('processed','keywords_unresolved','pending_model')")}
 recovered=0
 for old in db.execute("select path,memberships from work where state='missing_original'").fetchall():
  memberships=json.loads(old['memberships']);hashes={m.get('source_sha256') for m in memberships if m.get('source_sha256')}
  if len(hashes)!=1:continue
  sha=next(iter(hashes));copy=verified.get(sha)
  if not copy:continue
  candidate=json.loads(json.dumps(copy));candidate['memberships']=memberships
  candidate['recovered_missing_location']=old['path'];candidate['copy_proof']='same recorded original SHA-256 as verified retained bytes'
  allocation=inputs['allocations'].get(old['path'],{})
  other=source.record_ref(allocation.get('job_ref'))
  if other and other!=candidate['identity'].get('job_ref'):
   candidate['identity']=dict(candidate['identity'],job_ref=None,display_name=None,job={'state':'contradicted','value':None})
   candidate['event']=event_for(candidate['identity'],candidate['date'],[])
  db.execute("update work set sha=?,state='recovered_copy',result=?,updated=? where path=?",(sha,json.dumps(candidate),time.time(),old['path']));recovered+=1
 db.commit()
 # Readers consume the same derivative result file; atomic replacement preserves
 # prior snapshot until the current batch is durable. No canonical facts copied.
 results=[json.loads(r[0]) for r in db.execute('select result from work where result is not null and state in (\'processed\',\'keywords_unresolved\',\'pending_model\',\'recovered_copy\')')]
 # Collapse exact content copies in the view while retaining all memberships.
 merged={}
 for r in results:
  if r['sha256'] not in merged:
   merged[r['sha256']]=r; r['source_paths']=[r['path']]
  else:
   old=merged[r['sha256']];old['source_paths'].append(r['path']);old['memberships'].extend(r['memberships'])
   if old['identity'].get('job_ref')!=r['identity'].get('job_ref'):
    old['identity']=dict(old['identity'],job_ref=None,display_name=None,job={'state':'contradicted','value':None})
    old['event']=event_for(old['identity'],old['date'],[])
   for k in ['lee','original_words','machine_proposals']:old['keywords'][k]=sorted(set(old['keywords'][k])|set(r['keywords'][k]))
 results=list(merged.values())
 source.write_json(state/'results.json',results)
 counts=dict(db.execute('select state,count(*) from work group by state').fetchall())
 receipt={'started':started,'finished':time.time(),'source_revision':revision,'processed_this_run':processed,'missing_locations_recovered_this_run':recovered,'model_calls':calls,'errors':errors,'population':len(members),'states':counts,
          'photos_with_keywords':sum(bool(r['keywords']['lee'] or r['keywords']['machine_proposals']) for r in results),'photos_with_multiple_keywords':sum(len(r['keywords']['lee'])+len(r['keywords']['machine_proposals'])>1 for r in results),
          'job_refs_with_provisional_photos':len({r['identity']['job_ref'] for r in results if r['identity'].get('job_ref')}),'unique_contents_processed':len({r['sha256'] for r in results}),'full_collection_complete':False}
 for company,coverage in inputs['xero_coverage'].items():
  coverage['job_refs_with_processed_photos']=len(set(coverage['refs']) & {r['identity'].get('job_ref') for r in results})
 source.write_json(state/'xero-coverage.json',inputs['xero_coverage'])
 db.execute('insert into receipts(started,finished,revision,processed,model_calls,errors,kind) values(?,?,?,?,?,?,?)',(started,time.time(),revision,processed,calls,errors,'substantive' if processed else 'source_check'));db.commit();db.close()
 source.write_json(state/'status.json',receipt)
 from collection_view import render
 render(base,state,results,receipt)
 return receipt

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--config',required=True);a.add_argument('--limit',type=int);a.add_argument('--model-limit',type=int);args=a.parse_args()
 print(json.dumps(run(json.loads(Path(args.config).read_text()),args.limit,args.model_limit)))
