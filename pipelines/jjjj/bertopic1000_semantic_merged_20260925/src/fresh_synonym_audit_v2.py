"""Reproducible, previously unseen random records for the proposed synonym merges."""
from merge_common import *
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

PROPOSED = [[43,750],[78,334],[159,376],[158,974],[281,682],[297,720],
    [381,876],[447,591],[558,963],[738,953],[563,644],[212,803],
    [610,982],[616,948],[692,713],[598,689],[375,893]]
SEED=2026092502

def main():
    labels=np.load(RAW/'results/raw_labels.npy',mmap_mode='r')
    used=set(pq.read_table(RAW/'evidence/review_documents.parquet',columns=['row_id'])['row_id'].to_pylist())
    used.update(r['row_id'] for r in read(BASE/'evidence/fresh_random_audit.json')['records'])
    excluded=np.array(sorted(used))
    rng=np.random.default_rng(SEED)
    chosen={}
    for i in sorted({i for g in PROPOSED for i in g}):
        candidates=np.flatnonzero(labels==i)
        candidates=candidates[~np.isin(candidates,excluded)]
        for rid in rng.choice(candidates,size=8,replace=False):
            chosen[int(rid)]=i
    records=[]
    for ix,p in enumerate(read(CORPUS/'data/INPUT_MANIFEST.json')['parts']):
        ids=sorted(r for r in chosen if p['first_row']<=r<p['first_row']+p['n'])
        if not ids:
            continue
        t=pq.read_table(CORPUS/p['file'],columns=['row_id','doc_id','source','title','body','url','title_only','quality_note'])
        for r in t.take(pa.array([i-p['first_row'] for i in ids])).to_pylist():
            body=r.pop('body') or ''
            r.update(cluster=chosen[r['row_id']],selection_roles=f'fresh_random:seed{SEED}',
                body_excerpt=body[:600],full_body_characters=len(body),body_sha256=hashlib.sha256(body.encode()).hexdigest(),
                source_part=p['file'])
            records.append(r)
        if ix%25==0:
            print(f'read {ix+1} corpus parts; obtained {len(records)}/{len(chosen)} sample records',flush=True)
    records.sort(key=lambda r:(r['cluster'],r['row_id']))
    assert len(records)==len(chosen)
    dump(BASE/'evidence/fresh_synonym_audit_v2.json',dict(created_utc=now(),proposed_groups=PROPOSED,
        seed=SEED,samples_per_raw_topic=8,excluded_previous_sample_rows=len(used),
        selection='uniform random without replacement within each raw topic; excludes every previously saved sample',
        scope='stored titles and leading 600 body characters; actual read scope is recorded separately',records=records))
    print('saved',len(records),'new random samples',flush=True)

if __name__=='__main__':
    main()
