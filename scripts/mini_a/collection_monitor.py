"""Read-only progress projection of the existing retained collection and phase ledgers."""
import json, subprocess, time, sys
from pathlib import Path
BASE=Path.home()/'image-plane'
CACHE={}

def read_json(path):
 return json.loads(path.read_text())

def ledger(path):
 if not path.exists():return []
 result=[]
 lines=path.read_text().splitlines()
 for i,line in enumerate(lines):
  if not line.strip():continue
  try:result.append(json.loads(line))
  except json.JSONDecodeError:
   if i!=len(lines)-1:raise
 return result

def tally(rows):
 unique={r['sha256']:r for r in rows};albums=set();billed=set();jobs=set();lee_photos=set();terms=set();links=0;labelled=0;assigned=0
 for sha,r in unique.items():
  ref=r.get('identity',{}).get('job_ref');event=r.get('event',{})
  if ref:
   jobs.add(ref);assigned+=1
   if event.get('id'):
    key=(ref,event['id']);albums.add(key)
    if event.get('invoices'):billed.add(key)
  kw=r.get('keywords',{});lee={s for s in kw.get('lee',[]) if isinstance(s,str) and s and s!='needs-lee'}
  if lee:lee_photos.add(sha);terms.update(lee);links+=len(lee)
  if lee or kw.get('machine_proposals'):labelled+=1
 return dict(retained_photos=len(unique),albums_with_job_code=len(albums),job_codes=len(jobs),billable_event_links=len(billed),photos_with_lee_keywords=len(lee_photos),lee_keyword_assignments=links,distinct_lee_keywords=len(terms),photos_with_any_labels=labelled,photos_with_job_code=assigned,photos_awaiting_job_code=len(unique)-assigned)

def latest_photo(records,rows):
 latest=max(records,key=lambda r:r.get('ts',0),default=None)
 if latest is None:return None
 source=next((r for r in rows if r['sha256']==latest.get('sha256')),None)
 return dict(filename=Path(latest['path']).stem+'.jpg',job_code=latest.get('job_ref'),labels=latest.get('labels') or latest.get('components',[]),saved_at=latest['ts'],sha256=latest.get('sha256') if source else None,site=source.get('identity',{}).get('display_name') if source else None)

def snapshot(base=BASE):
 now=time.time();root=base/'incoming/worker/collection';state=base/'grind/approved_phase_resume'
 rows=read_json(root/'results.json');metrics=tally(rows)
 review=read_json(root/'lee-review-index.json')
 media_status=read_json(root/'media-worker/status.json')
 ready=sum(1 for r in rows if (root/'full-size'/(r['sha256']+'.jpg')).is_file() and (root/'full-size'/(r['sha256']+'.json')).is_file())
 media_status.update(ready_now=ready,remaining_now=len(rows)-ready)
 metrics.update(review['counts'])
 status=read_json(state/'status.json');activation=read_json(state/'activation.json')
 p1=ledger(base/'grind/vision_categories_takeout_p1.jsonl')
 accepted=[r for r in p1 if not r.get('validation_error') and r.get('parse_error') is None]
 since=[r for r in accepted if r.get('ts',0)>=activation['installed_at']]
 fresh={r.get('sha256') or r['path']:r for r in since}
 phase=next((r for r in reversed(status.get('phases',[])) if r['phase']==1),None)
 pending=ledger(state/'pending-p1.jsonl');target={r.get('sha256') or r['path'] for r in pending}
 done={r.get('sha256') or r['path'] for r in accepted}&target
 proc=subprocess.run(['launchctl','print','user/501/com.leeos.image-plane-approved-phases'],capture_output=True,text=True,timeout=4)
 running=proc.returncode==0 and 'state = running' in proc.stdout
 children=subprocess.run(['pgrep','-f',str(base/'incoming/worker/runtime/approved-phases-20260910/approved_categorize_p1_components.py')],capture_output=True,text=True,timeout=4)
 active=running and children.returncode==0
 control=read_json(state/'positive-equipment-check.json')
 sys.path.insert(0,str(base/'incoming/worker/runtime/approved-phases-20260910'))
 from resume_phases import reader_fingerprint
 equipment_ok=bool(control.get('passed') and control.get('smoke_verified') and 'ladder' in control.get('labels',[]) and control.get('reader_fingerprint')==reader_fingerprint(2))
 blockers=[]
 if not equipment_ok:blockers.append('Equipment pass awaits its verified smoke test.' if control.get('passed') else 'Equipment pass held: visible-equipment controls have not passed.')
 phase_states={}
 for number in range(3,8):
  proof=state/f'verified-p{number}.json';check=read_json(proof) if proof.exists() else {}
  review_path=state/f'review-p{number}.json';reviewed=read_json(review_path) if review_path.exists() else {}
  enabled=check.get('controls_passed') and check.get('semantic_smoke_reviewed') and check.get('reader_fingerprint')==reader_fingerprint(number)
  phase_states[str(number)]='validated proposal pass enabled' if enabled else 'held: '+reviewed.get('reason','actual controls and reviewed smoke test required')
 blockers.append('Full diagnostic labelling is incomplete. Later phases: '+', '.join(k+' '+v for k,v in phase_states.items())+'. Species, invasive-reference and before/after confirmation remain separate work.')
 cooldown=base/'grind/gmail-ladder-cooldown.json'
 if cooldown.exists():
  c=read_json(cooldown)
  if c.get('http_status')==403:blockers.append('Gmail identification checks are quota-limited. Saved mail evidence remains available.')
 blockers.append('Latest Xero refresh failed authentication; existing invoice evidence is available. A fresh sync is not yet verified.')
 latest=latest_photo(fresh.values(),rows)
 summary='Checking roof components and installation quality; new results are being saved alongside the earlier work.' if active else ('Component worker is between runs.' if running else 'Component worker is not currently running; its saved results remain available.')
 current_phase=1
 names={1:'Roof components and installation quality',2:'Installer equipment',3:'Safe working',4:'Roof vegetation types',5:'Waterproofing membrane kinds',6:'Leak diagnostics',7:'Vegetation diagnostics'}
 current=next((p for p in reversed(status.get('phases',[])) if not p.get('finished')),None)
 if current:
  current_phase=current['phase'];stem='approved_categorize_p2_equipment.py' if current_phase==2 else f'approved_categorize_p{current_phase}.py'
  if current_phase!=1:
   child=subprocess.run(['pgrep','-f',str(base/'incoming/worker/runtime/approved-phases-20260910'/stem)],capture_output=True,text=True,timeout=4)
   active=child.returncode==0
   accepted=[r for r in ledger(Path(current['output'])) if not r.get('validation_error') and r.get('parse_error') is None]
   fresh={r.get('sha256') or r['path']:r for r in accepted if r.get('ts',0)>=current['started']}
   pending=ledger(Path(current['input']));target={r.get('sha256') or r['path'] for r in pending};done={r.get('sha256') or r['path'] for r in accepted}&target
   summary=names[current_phase]+(' smoke test is reading actual photographs.' if 'smoke-' in current['output'] else ' pass is saving machine proposals.') if active else names[current_phase]+' is between runs.'
   latest=latest_photo(fresh.values(),rows)
 last=max((r.get('ts',0) for r in fresh.values()),default=None)
 if active and (not last or now-last>600):summary=names[current_phase]+' worker is active, but no new pass result has been saved in the last ten minutes.'
 result=dict(generated_at=now,collection_updated_at=(root/'results.json').stat().st_mtime,metrics=metrics,media=media_status,summary=summary,worker=dict(running=running,actively_processing=active,phase=names[current_phase],completed_since_restart=len(fresh),restart_at=activation['installed_at'],queued_at_current_run=len(target),completed_current_run=len(done),remaining_current_run=len(target-done),last_saved_at=last),latest=latest,blockers=blockers,diagnostic_phase_states=phase_states,equipment_check_passed=equipment_ok,process_locked=False,attribution_note='Album and invoice counts are saved links, including provisional links. They are not counts of fully approved albums.',keyword_note='Lee keywords counts photos carrying Lee’s saved words directly. Machine proposals are counted separately.',sources={'collection':'incoming/worker/collection/results.json','components':'grind/vision_categories_takeout_p1.jsonl','worker':'grind/approved_phase_resume/status.json'})
 result['intake']=intake_progress(root,rows,now)
 return result

def intake_progress(root,rows,now):
 """Use the existing scope checkpoint and publication; no new queue or scanner."""
 scope_path=root/'scope-reader-status.json';scope=read_json(scope_path)
 daily=read_json(root/'status.json');heartbeat=scope_path.stat().st_mtime
 service=subprocess.run(['launchctl','print','user/501/com.leeos.image-plane-scope-reader'],capture_output=True,text=True,timeout=4)
 running=service.returncode==0 and 'state = running' in service.stdout
 age=max(0,now-heartbeat);fresh=age<=180
 state='running' if running and scope.get('running') and fresh else 'stalled' if running and not fresh else 'finished' if scope.get('finished_at') else 'stopped'
 last=scope.get('last_result',{});photo=next((r for r in rows if r['sha256']==last.get('sha256')),None)
 latest={'photo_id':last.get('sha256'),'decision':last.get('decision'),'reason':last.get('reason'),'checked_at':None,'preview_available':photo is not None,'filename':Path(photo['original_name']).stem+'.jpg' if photo else 'Awaiting collection publication' if last.get('decision')=='admitted' else 'Preview withheld by collection screening','keywords':photo.get('keywords',{}) if photo else {},'full_photograph_complete':False}
 # Show a recent actual published photograph even when the newest decision is
 # held/excluded or the minute publisher has not caught up. Never bypass scope.
 published=None;by_sha={r['sha256']:r for r in rows};visual=root/'screening-visual.jsonl'
 if visual.exists():
  with visual.open('rb') as stream:
   size=stream.seek(0,2);start=max(0,size-131072);stream.seek(start);lines=stream.read().splitlines()
  if start:lines=lines[1:]
  for line in reversed(lines):
   try:record=json.loads(line)
   except ValueError:continue
   if record.get('sha256')==last.get('sha256') and not record.get('error') and latest['checked_at'] is None:latest['checked_at']=record.get('checked_at')
   retained=by_sha.get(record.get('sha256'))
   if published is None and retained and record.get('decision')=='admitted' and not record.get('error'):
    published={'photo_id':record['sha256'],'filename':Path(retained['original_name']).stem+'.jpg','checked_at':record.get('checked_at'),'reason':record.get('reason'),'keywords':retained.get('keywords',{})}
   if published is not None and latest['checked_at'] is not None:break
 if running and scope.get('running'):
  if not fresh or (latest['checked_at'] is not None and now-latest['checked_at']>180):state='stalled'
  elif latest['checked_at'] is None:state='waiting for first saved result'
 return {'state':state,'heartbeat_at':heartbeat,'heartbeat_age_seconds':age,'completed_screen_checks_this_run':scope.get('completed'),'queued_at_start':scope.get('queued_at_start'),'awaiting_screening':daily.get('states',{}).get('awaiting_scope_screening'),'collection_published_at':daily.get('finished'),'publication_stale':not daily.get('finished') or now-daily['finished']>180,'errors_this_run':scope.get('errors',0),'requires_attention_count':len(scope.get('requires_attention',[])),'latest':latest,'latest_published':published,'full_collection_complete':False,'remaining_note':'Awaiting screening is the current saved catalogue state. The initial worker queue can change as intake arrives; neither count is a complete cloud-library total.'}

def progress_json():
 now=time.time()
 if not CACHE or now-CACHE['at']>15:
  data=snapshot();CACHE.update(at=now,data=data)
 return json.dumps(CACHE['data'],ensure_ascii=False).encode()

def progress_html():
 import guards
 return Path(__file__).with_name('collection_progress.html').read_text().replace('__COUNTS_FOOTER__',guards.counts_footer()).encode()
