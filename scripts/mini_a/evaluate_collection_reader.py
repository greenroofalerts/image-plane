"""Local-only incident reproduction. Raw image/model evidence never printed."""
import sys,json,time,pathlib,hashlib,urllib.request,io,collections
runtime=sys.argv[1];model=sys.argv[2];sys.path.insert(0,runtime)
import collection_worker as w,collection_sources as s
base=pathlib.Path.home()/'image-plane';state=base/'incoming/worker/collection'
stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());out=state/'evaluations'/('incident-'+stamp);out.mkdir(parents=True)
prior=(state/'heldout-evaluation.json').read_bytes();(out/'previous-evaluation.json').write_bytes(prior)
samples=json.loads(prior)['results'];vocab=w.load_module('audit_vocab',base/'vocab_v2.py');reader=w.load_module('audit_reader',base/'fewshot_engine.py');notes,_=s.recover_annotations(base,state);terms,_=s.vocabulary(vocab,notes)
show=urllib.request.Request('http://127.0.0.1:11434/api/show',data=json.dumps({'model':model}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(show,timeout=15) as r: info=json.load(r)
meta={'model':model,'model_details':info.get('details'),'reader_sha256':s.sha_file(pathlib.Path(runtime)/'collection_worker.py'),'sample_source_sha256':hashlib.sha256(prior).hexdigest(),'vocabulary_sha256':s.digest(terms),'started':time.time(),'production_write':False,'method':'same six source-annotated photos as previous evaluation; no examples; notes are incomplete reference labels, not exhaustive ground truth'}
s.write_json(out/'metadata.json',meta);original=urllib.request.urlopen;current=[0]
def recorded(req,*args,**kwargs):
 with original(req,*args,**kwargs) as response: raw=response.read()
 (out/('response-%02d.json'%current[0])).write_bytes(raw)
 return io.BytesIO(raw)
results=[];totals=collections.Counter();urllib.request.urlopen=recorded
print(json.dumps({'evaluation_directory':str(out),'model':model}),flush=True)
for i,sample in enumerate(samples):
 current[0]=i;start=time.time();row={'sha256':sample['sha256'],'path':sample['path'],'truth':sample['truth']}
 try:
  if s.sha_file(sample['path'])!=sample['sha256']:raise ValueError('source hash mismatch')
  pred=w.local_labels(reader,sample['path'],terms,'No examples from this photograph, original hash or job are included.',model)
  truth=set(sample['truth']);proposed=set(pred);counts={'matched_note_labels':len(truth&proposed),'unmatched_proposals':len(proposed-truth),'missed_note_labels':len(truth-proposed)};totals.update(counts)
  row.update(state='evaluated',predictions=pred,counts=counts)
 except Exception as e:row.update(state='error',error=type(e).__name__+': '+str(e)[:180])
 row['seconds']=round(time.time()-start,2);results.append(row)
 s.write_json(out/'evaluation.json',{'metadata':meta,'results':results,'totals':dict(totals),'complete':len(results)==len(samples)})
 print(json.dumps({'completed':i+1,'state':row['state'],'seconds':row['seconds'],'counts':row.get('counts'),'error':row.get('error')}),flush=True)
print(json.dumps({'samples':len(results),'valid':sum(r['state']=='evaluated' for r in results),'totals':dict(totals),'evaluation_directory':str(out)}),flush=True)
