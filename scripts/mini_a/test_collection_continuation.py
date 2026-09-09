import json,tempfile,unittest,sys
from pathlib import Path
from types import SimpleNamespace
import re
import collection_sources as s
from collection_worker import original_labels,vocabulary_labels,connect

class CollectionTests(unittest.TestCase):
 def test_source_poll_does_not_masquerade_as_processing_progress(self):
  from collection_view import reader_health
  with tempfile.TemporaryDirectory() as t:
   state=Path(t);db=connect(state)
   db.executemany('insert into receipts(finished,processed) values(?,?)',[(1000,5),(2000,0)]);db.commit();db.close()
   (state/'reader-health.json').write_text(json.dumps({'state':'BLOCKED','reason':'Failed <test>','mitigation':'Evaluation isolated; model disabled.'}))
   notice,timing=reader_health(state,{'finished':2000,'states':{'pending_model':18}})
   self.assertIn('00:33:20',timing);self.assertIn('00:16:40',timing)
   self.assertIn('18 file records await model reading',notice);self.assertIn('Failed &lt;test&gt;',notice)
   self.assertIn('not connected',notice);self.assertIn('have not been validated',notice)
 def test_missing_quality_record_is_unknown_not_healthy(self):
  from collection_view import reader_health
  with tempfile.TemporaryDirectory() as t:
   notice,timing=reader_health(Path(t),{'finished':2000})
   self.assertIn('unknown',notice);self.assertIn('Not recorded',timing)
 def test_negated_caption_does_not_add_keyword(self):
  v=SimpleNamespace(DESC_KEYWORDS={('x','parapet'):re.compile('parapet')})
  self.assertEqual(vocabulary_labels('There is no parapet.',v),[])
  self.assertEqual(vocabulary_labels('A parapet with coping.',v),['parapet'])
 def test_removal_beats_earlier_note_and_original_words_survive(self):
  v=SimpleNamespace(NOTE_ALIASES={'bare-areas':('problems','gaps in planting')})
  notes=[{'tags':['bare-areas'],'remove':[]},{'tags':['parapet'],'remove':['bare-areas']}]
  self.assertEqual(original_labels(notes,v),(['parapet'],['parapet']))
 def test_roof_and_unconfirmed_notes_not_smeared(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);(b/'knowledge_notes.jsonl').write_text('\n'.join(json.dumps(r) for r in [
    {'path':'x.jpg','tags':['moss'],'scope':'roof'}, {'path':'y.jpg','tags':['moss'],'unconfirmed':True},
    {'path':'z.jpg','tags':['parapet']}]))
   notes,rev=s.recover_annotations(b,b/'state');self.assertEqual(set(notes),{'z.jpg'})
   audit=json.loads((b/'state/annotation-audit.json').read_text());self.assertEqual(len(audit['unapplied']),2)
 def test_annotation_backup_is_not_current_authority(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);(b/'knowledge_notes.jsonl').write_text(json.dumps({'path':'x','tags':['parapet']}));(b/'knowledge_notes.jsonl.bak').write_text(json.dumps({'path':'x','tags':['moss']}))
   notes,_=s.recover_annotations(b,b/'state');self.assertEqual(notes['x'][0]['tags'],['parapet'])
 def test_discovery_preserves_duplicate_album_membership(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);a=b/'albumA';a.mkdir();p=a/'same.jpg';p.write_bytes(b'a')
   data={'photo_ledger_merged.jsonl':[],'takeout_ledger_merged.jsonl':[],'takeout_index.jsonl':[{'path':str(p),'album':'original album'}]}
   members,checks=s.discover(b,{'data':data},[b]);self.assertEqual(len(members[str(p)]['memberships']),2);self.assertEqual(checks[0]['image_members'],1)
 def test_processing_progress_is_separate_from_business_canon(self):
  with tempfile.TemporaryDirectory() as t:
   db=connect(Path(t));names={r[0] for r in db.execute("select name from sqlite_master where type='table'")};self.assertEqual(names,{'work','readings','receipts'});db.close()

if __name__=='__main__':unittest.main()

class HttpBoundaryTests(unittest.TestCase):
 def test_collection_path_traversal_and_unrelated_routes(self):
  import importlib.util,types
  calls=[]
  fake=types.SimpleNamespace(JobHandler=type('Handler',(),{'do_GET':lambda self:calls.append('existing')}))
  prior=sys.modules.get('job_screen');sys.modules['job_screen']=fake
  try:
   spec=importlib.util.spec_from_file_location('test_collection_http',Path(__file__).with_name('collection_http.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
   request=types.SimpleNamespace(path='/collection/thumb/../../.env.flip',_send=lambda code,*a,**k:calls.append(code));m.get(request);self.assertEqual(calls,[404])
   request.path='/job/1000-26';m.get(request);self.assertEqual(calls[-1],'existing')
  finally:
   if prior:sys.modules['job_screen']=prior
   else:sys.modules.pop('job_screen',None)
