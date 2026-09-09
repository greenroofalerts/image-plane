import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import collection_reader as reader
import collection_geo as geo
import collection_worker as worker
import collection_sources as source
from sample_collection_reader import choose


class ReaderBoundaryTests(unittest.TestCase):
    def response(self, labels=None, **outer):
        return json.dumps(dict(done=True,message={'content':json.dumps({
            'description':'A roof edge.', 'visible_text':'',
            'labels':labels if labels is not None else [{'term':'parapet','visible_evidence':'Raised edge visible at top'}]})},**outer)).encode()

    def test_exact_image_chat_and_raw_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            seen=[]
            def reply(req, **kw):
                seen.append(req)
                return io.BytesIO(self.response())
            with patch('urllib.request.urlopen',side_effect=reply):
                self.assertEqual(reader.read_labels(b'\xff\xd8original',['parapet'],'', 'test',1,t),['parapet'])
            payload=json.loads(seen[0].data)
            self.assertTrue(seen[0].full_url.endswith('/api/chat'))
            self.assertEqual(len(payload['messages'][0]['images']),1)
            run=next(Path(t).iterdir())
            self.assertEqual((run/'response.json').read_bytes(),self.response())
            self.assertFalse(json.loads((run/'outcome.json').read_text())['semantic_acceptance'])

    def test_invalid_truncated_unsupported_and_unexplained_outputs_fail(self):
        raws=[b'not-json',self.response(done_reason='length'),
              self.response([{'term':'invented','visible_evidence':'yes'}]),
              self.response([{'term':'parapet','visible_evidence':''}]),
              self.response([{'term':'parapet','visible_evidence':'x'}]*2)]
        for raw in raws:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as t:
                with patch('urllib.request.urlopen',return_value=io.BytesIO(raw)):
                    with self.assertRaises(ValueError):
                        reader.read_labels(b'\xff\xd8x',['parapet'],'','test',1,t)
                self.assertEqual(json.loads(next(Path(t).glob('*/outcome.json')).read_text())['state'],'failed')

    def test_empty_valid_labels_are_not_a_transport_failure(self):
        with tempfile.TemporaryDirectory() as t, patch('urllib.request.urlopen',return_value=io.BytesIO(self.response([]))):
            self.assertEqual(reader.read_labels(b'\xff\xd8x',['parapet'],'','test',1,t),[])


class LocationTests(unittest.TestCase):
    def test_adjacent_roofs_remain_ambiguous(self):
        data={'points':{'/photo':{(51.,0.)}},'jobs':{'1000-26':{'lat':51.,'lon':0.},'1001-26':{'lat':51.0001,'lon':0.}},'signatures':{}}
        result=geo.location_evidence('/photo',data)
        self.assertEqual(result['state'],'ambiguous')
        self.assertFalse(result['settles_job'])

    def test_unavailable_conflicting_and_invalid_coordinates(self):
        self.assertIsNone(geo.point({'lat':float('nan'),'lon':0}))
        self.assertIsNone(geo.point({'lat':91,'lon':0}))
        data={'points':{'/photo':{(51.,0.),(52.,0.)}},'jobs':{},'signatures':{}}
        self.assertEqual(geo.location_evidence('/photo',data)['state'],'conflicting_photo_coordinates')
        self.assertEqual(geo.location_evidence('/absent',data)['state'],'unavailable')
        self.assertEqual(geo.location_evidence('/photo',data,{'lat':50,'lon':0})['state'],'job_coordinates_unavailable')


class WorkerTests(unittest.TestCase):
    def test_read_failure_keeps_identity_and_old_keywords_do_not_skip_read(self):
        with tempfile.TemporaryDirectory() as t:
            b=Path(t);(b/'incoming/worker').mkdir(parents=True)
            p=b/'photo.jpg';p.write_bytes(b'original');(b/'fewshot_engine.py').write_text('# local')
            (b/'vocab_v2.py').write_text('# local')
            names=['photo_ledger_merged.jsonl','grind/visit_types_v4.jsonl']
            sha=source.sha_file(p)
            inputs={'revision':'one','signatures':{},'allocations':{},'takeout':{},'job_companies':{},'dates':{},'captions':{},'prior_labels':{sha:['parapet','moss']},'data':{n:[] for n in names},'xero_coverage':{}}
            vocab=SimpleNamespace(VOCAB={'things':['parapet','moss']},VISIT_TYPES_V4=[],DESC_KEYWORDS={},NOTE_ALIASES={})
            identity={'job_ref':'1000-26','job':{'state':'proposed','value':'1000-26'},'display_name':'example'}
            bridge=SimpleNamespace(resolve_photo=lambda *a:dict(identity),event_for=lambda *a:{'id':'e','start':None,'end':None,'name':'unknown','basis':'test'})
            with patch.dict('sys.modules',{'spine_evidence':SimpleNamespace(),'spine_evidence.image_plane':bridge}), \
                 patch.object(source,'load_sources',return_value=inputs), \
                 patch.object(source,'recover_annotations',return_value=({},'one')), \
                 patch.object(source,'refresh_canon',return_value={'revision':'one','checked_epoch':1,'sources':{}}), \
                 patch.object(source,'discover',return_value=({str(p):{'memberships':[]}},[])), \
                 patch.object(worker,'load_module',return_value=vocab), \
                 patch.object(worker,'capture_day',return_value=('2026-01-01','EXIF')), \
                 patch.object(worker,'capture_gps',return_value=None), \
                 patch.object(worker,'make_thumb',return_value=p), \
                 patch.object(worker,'local_labels',side_effect=ValueError('bad model')) as model, \
                 patch('collection_view.render'):
                result=worker.run({'base':str(b),'spine_code':str(b),'roots':[],'model_batch':1})
            self.assertEqual(model.call_count,1)
            stored=json.loads((b/'incoming/worker/collection/results.json').read_text())
            self.assertEqual(len(stored),1)
            self.assertEqual(stored[0]['identity']['job_ref'],'1000-26')
            self.assertEqual(stored[0]['date'],'2026-01-01')
            self.assertEqual(stored[0]['reading']['state'],'failed')
            self.assertEqual(result['states']['retry'],1)
            self.assertEqual(result['errors'],1)

    def test_random_sampling_is_repeatable_and_excludes_nonphoto_notes_and_copies(self):
        with tempfile.TemporaryDirectory() as t:
            b=Path(t);notes=[]
            for i in range(5):
                (b/f'{i}.jpg').write_bytes(str(i).encode())
                notes.append({'path':f'{i}.jpg','tags':['parapet']})
            (b/'copy.jpg').write_bytes(b'0');notes.append({'path':'copy.jpg','tags':['parapet']})
            notes.append({'path':'0.jpg','tags':['moss'],'scope':'roof'})
            (b/'knowledge_notes.jsonl').write_text('\n'.join(map(json.dumps,notes)))
            vocab=SimpleNamespace(NOTE_ALIASES={})
            first,n=choose(b,vocab,3,44);second,_=choose(b,vocab,3,44)
            self.assertEqual(n,5);self.assertEqual(first,second)
            self.assertEqual(len({r['sha256'] for r in first}),3)


if __name__=='__main__':unittest.main()
