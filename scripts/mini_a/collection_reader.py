"""Local vision boundary. Outputs remain proposals until real-image validation.

Transport success is not semantic acceptance. Preserve every request's identity
and raw response, including failures, without modifying originals or canon.
"""
import base64
import hashlib
import json
import os
import time
import urllib.request
import uuid
from pathlib import Path

VERSION = 'evidence-chat/1'


def read_labels(image_bytes, terms, examples, model, timeout, audit_root):
    if not image_bytes.startswith(b'\xff\xd8'):
        raise ValueError('reader input is not a JPEG')
    terms = sorted(set(terms))
    schema = {
        'type': 'object', 'additionalProperties': False,
        'required': ['description', 'visible_text', 'labels'],
        'properties': {
            'description': {'type': 'string'},
            'visible_text': {'type': 'string'},
            'labels': {'type': 'array', 'maxItems': 12, 'items': {
                'type': 'object', 'additionalProperties': False,
                'required': ['term', 'visible_evidence'],
                'properties': {'term': {'type': 'string', 'enum': terms},
                               'visible_evidence': {'type': 'string'}}}}}}
    prompt = (
        'Inspect the attached photograph. First describe what is actually visible. '
        'Transcribe legible writing into visible_text, or use an empty string. '
        'Select only vocabulary terms supported by visible details, and explain '
        'the visible detail for each selected term. An empty labels array is valid. '
        'Do not infer a visit purpose, job, company, date, payment, hidden layer, '
        'plant species or technical diagnosis from context alone. '
        'Prior label lists below explain vocabulary only; they are not visual '
        'examples, proof about this image, or labels to copy.\n'
        + examples + '\nReturn exactly this JSON schema:\n' + json.dumps(schema))
    payload = {'model': model, 'stream': False, 'think': False,
               'messages': [{'role': 'user', 'content': prompt,
                             'images': [base64.b64encode(image_bytes).decode()]}],
               'format': schema,
               'options': {'num_ctx': 8192, 'temperature': 0, 'num_predict': 1600}}
    run = Path(audit_root) / (str(time.time_ns()) + '-' + uuid.uuid4().hex)
    run.mkdir(parents=True, mode=0o700)
    metadata = {'version': VERSION, 'model': model, 'endpoint': '/api/chat',
                'input_jpeg_sha256': hashlib.sha256(image_bytes).hexdigest(),
                'prompt': prompt, 'format': schema, 'options': payload['options'],
                'started': time.time(), 'state': 'started'}
    def save(name, value):
        path = run / name
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(value)
    save('request.json', json.dumps(metadata).encode())
    try:
        request = urllib.request.Request('http://127.0.0.1:11434/api/chat',
            data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw_bytes = response.read()
        save('response.json', raw_bytes)
        raw = json.loads(raw_bytes)
        if raw.get('error') or raw.get('done') is not True:
            raise ValueError('reader failed or returned an incomplete response')
        if raw.get('done_reason') in ('length', 'max_tokens'):
            raise ValueError('reader output was truncated')
        result = json.loads(raw.get('message', {}).get('content', ''))
        if not isinstance(result, dict) or set(result) != set(schema['required']):
            raise ValueError('reader returned wrong object shape')
        if any(not isinstance(result[k], str) for k in ('description', 'visible_text')):
            raise ValueError('reader description/text must be strings')
        if not isinstance(result['labels'], list) or len(result['labels']) > 12:
            raise ValueError('reader labels must be a bounded list')
        labels = []
        for row in result['labels']:
            if (not isinstance(row, dict) or set(row) != {'term', 'visible_evidence'}
                or not isinstance(row['term'], str) or row['term'] not in terms
                or not isinstance(row['visible_evidence'], str)
                or not row['visible_evidence'].strip()):
                raise ValueError('reader label lacks an allowed term or visible evidence')
            if row['term'] in labels:
                raise ValueError('reader repeated a label')
            labels.append(row['term'])
        save('parsed.json', json.dumps(result).encode())
        save('outcome.json', json.dumps({'state': 'parsed_proposal', 'finished': time.time(),
                                       'semantic_acceptance': False}).encode())
        return sorted(labels)
    except Exception as error:
        save('outcome.json', json.dumps({'state': 'failed', 'finished': time.time(),
             'error_type': type(error).__name__, 'semantic_acceptance': False}).encode())
        raise
