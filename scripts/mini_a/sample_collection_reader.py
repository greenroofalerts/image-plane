"""Random, read-only original-photo sample. No bulk worker or cache writes.

Run on the existing authorised Mac/Mini A. Uses original photo annotations as
incomplete reference labels, never as instructions to the model. Prints a local
HTML review path after each result; retains failed and successful raw responses.
"""
import argparse
import html
import json
import random
import secrets
import time
from pathlib import Path
from types import SimpleNamespace
import collection_sources as sources
import collection_worker as worker


def choose(base, vocab, count, seed):
    eligible = {}
    for row in sources.rows(base/'knowledge_notes.jsonl'):
        if (not row.get('path') or not isinstance(row.get('tags'), list)
                or row.get('unconfirmed') or row.get('confidence') in ('unconfirmed','machine')
                or row.get('scope') in ('roof','job','rule') or row.get('kind') in ('rule','roof')):
            continue
        path = Path(row['path'])
        path = path if path.is_absolute() else base/path
        if path.is_file() and path.suffix.lower() in sources.EXTS:
            eligible.setdefault(str(path.resolve()), []).append(dict(row, remove=row.get('remove') or []))
    by_hash = {}
    for path, notes in sorted(eligible.items()):
        labels, original = worker.original_labels(notes, vocab)
        if not labels:
            continue
        sha = sources.sha_file(path)
        if sha in by_hash:
            # Avoid selecting conflicting copied annotations as clean truth.
            if by_hash[sha]['reference_labels'] != labels:
                by_hash[sha]['conflict'] = True
            continue
        by_hash[sha] = {'path':path, 'sha256':sha, 'reference_labels':labels,
                       'original_words':original, 'notes':[n.get('note','') for n in notes]}
    population = [r for r in by_hash.values() if not r.get('conflict')]
    if len(population) < count:
        raise ValueError('Not enough readable, explicitly annotated unique photos for requested sample')
    return random.Random(seed).sample(population, count), len(population)


def render(out, results, manifest):
    esc = lambda x: html.escape(str(x))
    parts = ['<!doctype html><meta charset="utf-8"><title>Random photo reader test</title>',
        '<style>body{font:18px system-ui;max-width:1000px;margin:30px auto}img{max-width:100%;max-height:550px}section{border-top:1px solid #aaa;padding:20px 0}pre{white-space:pre-wrap}</style>',
        '<h1>Random original-photo test</h1>',
        '<p>Reference notes are incomplete. Extra suggestions require review. No production labels changed.</p>',
        '<p>Seed '+esc(manifest['seed'])+'; '+esc(manifest['sample_size'])+' drawn from '+esc(manifest['eligible_unique_photos'])+' readable annotated originals.</p>']
    for row in results:
        parts += ['<section><h2>'+esc(Path(row['path']).name)+'</h2>',
                  '<img src="'+esc(Path(row['path']).as_uri())+'">',
                  '<p>Original notes: '+esc(' | '.join(row['notes']))+'</p>',
                  '<p>Recorded labels: '+esc(', '.join(row['reference_labels']))+'</p>',
                  '<p>New proposals: '+esc(', '.join(row.get('predictions',[])))+'</p>',
                  '<p>Status: '+esc(row['state'])+'</p>',
                  '<pre>'+esc(json.dumps(row.get('comparison',{}),indent=2))+'</pre></section>']
    (out/'review.html').write_text('\n'.join(parts))


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,default=Path.home()/'image-plane')
    p.add_argument('--model',required=True);p.add_argument('--sample',type=int,default=6)
    p.add_argument('--seed',type=int);p.add_argument('--timeout',type=int,default=180)
    a=p.parse_args()
    if not 1 <= a.sample <= 10 or not 1 <= a.timeout <= 300:
        p.error('sample must be 1..10 and timeout 1..300 seconds')
    base=a.base.resolve();seed=a.seed if a.seed is not None else secrets.randbits(64)
    vocab=worker.load_module('sample_vocab',base/'vocab_v2.py')
    samples,population=choose(base,vocab,a.sample,seed)
    terms=sorted({t for vals in vocab.VOCAB.values() for t in vals}|set(vocab.VISIT_TYPES_V4))
    out=base/'incoming/worker/collection/evaluations'/('random-'+str(time.time_ns()))
    out.mkdir(parents=True,mode=0o700)
    manifest={'seed':seed,'model':a.model,'sample_size':a.sample,'eligible_unique_photos':population,
              'population':'readable explicitly photo-scoped current annotations; unique original bytes',
              'samples':samples,'started':time.time(),'production_write':False,
              'annotation_sha256':sources.sha_file(base/'knowledge_notes.jsonl'),
              'vocabulary_sha256':sources.sha_file(base/'vocab_v2.py'),
              'worker_sha256':sources.sha_file(Path(worker.__file__)),
              'reader_sha256':sources.sha_file(Path(worker.__file__).with_name('collection_reader.py'))}
    sources.write_json(out/'manifest.json',manifest)
    results=[];render(out,results,manifest)
    print(json.dumps({'review':str(out/'review.html'),'seed':seed,'sample_size':len(samples)}),flush=True)
    reader=SimpleNamespace(reader_timeout=lambda:a.timeout)
    for sample in samples:
        row=dict(sample);start=time.time()
        try:
            if sources.sha_file(row['path'])!=row['sha256']:
                raise ValueError('original changed after selection')
            predictions=worker.local_labels(reader,row['path'],terms,'No teaching examples supplied.',a.model,out/'attempts')
            reference=set(row['reference_labels']);allowed=reference&set(terms);predicted=set(predictions)
            row.update(state='parsed_proposal',predictions=predictions,comparison={
                'matched_reference_labels':sorted(allowed&predicted),
                'missed_reference_labels':sorted(allowed-predicted),
                'additional_unadjudicated_proposals':sorted(predicted-reference),
                'reference_labels_not_in_vocabulary':sorted(reference-set(terms))})
        except Exception as e:
            row.update(state='failed',error_type=type(e).__name__)
        row['seconds']=round(time.time()-start,1);results.append(row)
        sources.write_json(out/'results.json',{'results':results,'complete':len(results)==len(samples)})
        render(out,results,manifest)
        print(json.dumps({'completed':len(results),'total':len(samples),'state':row['state'],
                          'seconds':row['seconds'],'review':str(out/'review.html')}),flush=True)


if __name__=='__main__':main()
