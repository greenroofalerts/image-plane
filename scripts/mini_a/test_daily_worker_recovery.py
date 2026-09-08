"""Offline recovery checks. No customer data, model requests or network writes."""
import hashlib
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import daily_worker as worker


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inbox = self.root / 'incoming' / 'google'
        self.album = self.inbox / 'album'
        self.album.mkdir(parents=True)
        self.work = self.root / 'incoming' / 'worker'
        self.work.mkdir()
        self.log = self.work / 'run.log'
        self.sha = hashlib.sha256(b'synthetic').hexdigest()
        self.manifest = {'files': {'originals/test.jpg': {'kind': 'image', 'sha256': self.sha}}}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in {'BASE': self.root, 'INBOX': self.inbox, 'WORKER': self.work,
                            'READ_INDEX': self.work / 'index.json', '_PRIOR_READINGS': None}.items():
            self.stack.enter_context(patch.object(worker, name, value))

    def reading(self):
        return {'sha256': self.sha, 'reading_version': worker.READING_VERSION,
                'caption': 'Synthetic roof.', 'visible_writing': 'NO WORDS ON THIS PAGE.',
                'file': 'originals/test.jpg', 'model': 'synthetic'}

    def mock_reader(self, replies=None):
        self.stack.enter_context(patch.object(worker, 'make_thumb', return_value=True))
        self.stack.enter_context(patch.object(worker, 'to_jpg_1024', return_value=True))
        return self.stack.enter_context(patch.object(worker, 'qwen', side_effect=replies or [
            ('Synthetic roof.', 1), ('NO WORDS ON THIS PAGE.', 1)]))

    def test_failed_thumbnail_retries_then_unchanged_success_skips_model(self):
        ledger = self.album / 'readings.jsonl'
        ledger.write_text(json.dumps({'sha256': self.sha, 'error': 'thumbnail_failed'}) + '\n')
        model = self.mock_reader()
        progress = {'stages': {}}
        self.assertEqual(worker.reading_stage(self.album, progress, self.manifest, self.log), 1)
        self.assertEqual(model.call_count, 2)
        self.assertIn('reading_completed', progress['stages'])
        worker.reading_stage(self.album, progress, self.manifest, self.log)
        self.assertEqual(model.call_count, 2)

    def test_failed_retry_clears_false_completion(self):
        (self.album / 'readings.jsonl').write_text(json.dumps({'sha256': self.sha, 'error': 'thumbnail_failed'})+'\n')
        self.stack.enter_context(patch.object(worker, 'make_thumb', return_value=False))
        model = self.stack.enter_context(patch.object(worker, 'qwen', side_effect=AssertionError('no model')))
        progress = {'stages': {'reading_completed': 'old'}, 'images_read': 1}
        worker.reading_stage(self.album, progress, self.manifest, self.log)
        self.assertNotIn('reading_completed', progress['stages'])
        self.assertNotIn('images_read', progress)
        model.assert_not_called()

    def test_reused_result_has_actual_caption_and_writing(self):
        other = self.inbox / 'previous'
        other.mkdir()
        (other / 'readings.jsonl').write_text(json.dumps(self.reading())+'\n')
        worker.save_json(worker.READ_INDEX, {self.sha: [worker.READING_VERSION]})
        model = self.stack.enter_context(patch.object(worker, 'qwen', side_effect=AssertionError('no model')))
        progress = {'stages': {}}
        worker.reading_stage(self.album, progress, self.manifest, self.log)
        saved = json.loads((self.album / 'readings.jsonl').read_text())
        self.assertEqual(saved['caption'], self.reading()['caption'])
        self.assertEqual(saved['visible_writing'], self.reading()['visible_writing'])
        self.assertTrue(Path(saved['reused_from']).is_file())
        model.assert_not_called()

    def test_orphaned_index_marker_retries_reading(self):
        worker.save_json(worker.READ_INDEX, {self.sha: [worker.READING_VERSION]})
        model = self.mock_reader()
        worker.reading_stage(self.album, {'stages': {}}, self.manifest, self.log)
        self.assertEqual(model.call_count, 2)

    def test_changed_instructions_retry_old_success(self):
        old = dict(self.reading(), reading_version='old')
        (self.album / 'readings.jsonl').write_text(json.dumps(old)+'\n')
        model = self.mock_reader()
        worker.reading_stage(self.album, {'stages': {}}, self.manifest, self.log)
        self.assertEqual(model.call_count, 2)

    def test_empty_model_result_does_not_count_as_read(self):
        self.mock_reader([('', 1), ('NO WORDS ON THIS PAGE.', 1)])
        progress = {'stages': {}}
        self.assertEqual(worker.reading_stage(self.album, progress, self.manifest, self.log), 0)
        self.assertNotIn('reading_completed', progress['stages'])

    def test_filename_collision_preserves_original_and_prevents_wrong_record(self):
        dest = self.root / 'cabinet' / '1000-26' / 'originals' / 'test.jpg'
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b'previous original')
        writer = self.stack.enter_context(patch.object(worker, 'rest', side_effect=AssertionError('no write')))
        with self.assertRaisesRegex(ValueError, 'filename collision'):
            worker.filing_stage(self.album, {}, self.manifest, {'job_ref': '1000-26'}, {}, self.log)
        self.assertEqual(dest.read_bytes(), b'previous original')
        writer.assert_not_called()

    def test_album_failure_produces_failed_run_and_continues_other_albums(self):
        for name, value in {'LOGS': self.work / 'logs', 'REGISTRY': self.work / 'registry.json'}.items():
            self.stack.enter_context(patch.object(worker, name, value))
        self.stack.enter_context(patch.object(worker, 'take_lock', return_value=True))
        self.stack.enter_context(patch.object(worker, 'drop_lock'))
        self.stack.enter_context(patch.object(worker, 'discover', return_value={'a': {}, 'b': {}}))
        self.stack.enter_context(patch.object(worker, 'load_env', return_value={}))
        process = self.stack.enter_context(patch.object(worker, 'process_album', side_effect=[ValueError('synthetic failure'), 'complete']))
        self.stack.enter_context(patch.object(worker, 'retry_spine_outbox'))
        self.stack.enter_context(patch.object(worker, 'build_attention', return_value=[]))
        saved = self.stack.enter_context(patch.object(worker, 'append_run'))
        self.assertEqual(worker.main(), 1)
        self.assertEqual(process.call_count, 2)
        self.assertEqual(saved.call_args.args[0]['result'], 'error')


if __name__ == '__main__':
    unittest.main()
