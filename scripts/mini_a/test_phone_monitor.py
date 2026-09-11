import unittest,tempfile,json,time,os,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
from collection_monitor import intake_progress,latest_photo
class MonitorTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.now=time.time();self.scope={'running':True,'completed':9,'queued_at_start':12,'last_result':{'sha256':'a'*64,'decision':'held','reason':'No roof context'}}
  (self.root/'scope-reader-status.json').write_text(json.dumps(self.scope));(self.root/'status.json').write_text(json.dumps({'finished':self.now,'states':{'awaiting_scope_screening':21}}))
  (self.root/'screening-visual.jsonl').write_text(json.dumps({'sha256':'a'*64,'decision':'held','checked_at':self.now})+'\n')
 def tearDown(self):self.temp.cleanup()
 def read(self,running=True):
  with patch('collection_monitor.subprocess.run') as run:
   run.return_value.returncode=0;run.return_value.stdout='state = running' if running else 'state = not running';return intake_progress(self.root,[],self.now)
 def test_current_worker_and_distinct_counts(self):
  r=self.read();self.assertEqual(r['state'],'running');self.assertEqual(r['completed_screen_checks_this_run'],9);self.assertEqual(r['awaiting_screening'],21);self.assertFalse(r['latest']['preview_available']);self.assertFalse(r['full_collection_complete'])
 def test_stale_live_process_is_not_progress(self):
  os.utime(self.root/'scope-reader-status.json',(self.now-181,self.now-181));self.assertEqual(self.read()['state'],'stalled')
 def test_dead_worker_is_stopped(self):self.assertEqual(self.read(False)['state'],'stopped')
 def test_stale_publication_is_reported_separately(self):
  (self.root/'status.json').write_text(json.dumps({'finished':self.now-181,'states':{}}));r=self.read();self.assertTrue(r['publication_stale']);self.assertIsNone(r['awaiting_screening'])
 def test_held_image_no_preview_no_labels(self):
  r=self.read()['latest'];self.assertEqual(r['keywords'],{});self.assertEqual(r['filename'],'Preview withheld by collection screening')
 def test_error_checkpoint_does_not_redate_successful_result(self):
  rows=[{'sha256':'a'*64,'decision':'held','checked_at':self.now-60},{'sha256':'b'*64,'error':True,'checked_at':self.now}]
  (self.root/'screening-visual.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
  self.assertEqual(self.read()['latest']['checked_at'],self.now-60)
 def test_missing_result_timestamp_is_unknown(self):
  (self.root/'screening-visual.jsonl').unlink();r=self.read();self.assertIsNone(r['latest']['checked_at']);self.assertEqual(r['state'],'waiting for first saved result')
 def test_error_only_checkpoint_does_not_claim_progress(self):
  (self.root/'screening-visual.jsonl').write_text(json.dumps({'sha256':'a'*64,'decision':'held','checked_at':self.now-181})+'\n');self.assertEqual(self.read()['state'],'stalled')
 def test_active_diagnostic_uses_its_own_labels(self):
  r=latest_photo([{'sha256':'a'*64,'path':'/retained/test.jpg','ts':1,'labels':['equipment']}],[{'sha256':'a'*64,'identity':{}}]);self.assertEqual(r['labels'],['equipment']);self.assertEqual(r['sha256'],'a'*64)
 def test_diagnostic_never_previews_removed_photo(self):
  r=latest_photo([{'sha256':'a'*64,'path':'/retained/test.jpg','ts':1,'components':['component']}],[]);self.assertIsNone(r['sha256']);self.assertEqual(r['labels'],['component']);self.assertIsNone(latest_photo([],[]))
if __name__=='__main__':unittest.main()
