from refine_common import *
from decision_guards import ACCEPTED,apply
from text_quality import process
import argparse,bisect

def main():
    p=argparse.ArgumentParser();p.add_argument('--partial',action='store_true');p.add_argument('--per-topic',type=int,default=2)
    args=p.parse_args()
    excluded=set(pq.read_table(NEW/'evidence/review_documents.parquet',columns=['row_id']).column(0).to_pylist())
    excluded.update(r['row_id'] for r in read(AUDIT/'evidence/audit_samples.json')['records'])
    for f in (OLD/'evidence').glob('*documents.parquet'):
        excluded.update(pq.read_table(f,columns=['row_id']).column(0).to_pylist())
    excluded.update([4304,5982,5844,17015,12699])
    if not args.partial and (BASE/'evidence/partial_review_samples.json').exists():
        excluded.update(r['row_id'] for r in read(BASE/'evidence/partial_review_samples.json')['records'])
    pool={};seed=48620260925
    old=pd.read_csv(OLD/'results/merged_topics.csv').set_index('merged_topic_id').status.to_dict()
    for f in sorted((BASE/'results/assignments').glob('*.parquet')):
        if not (BASE/'logs'/f'{f.stem}.json').exists():continue
        df=pq.read_table(f).to_pandas()
        df=df[df.assignment_status.isin(ACCEPTED)&(df.topic_changed|df.text_cleaned)&~df.row_id.isin(excluded)]
        if not len(df):continue
        ids=df.row_id.to_numpy(dtype=np.uint64)
        rank=(ids^np.uint64(seed))*np.uint64(11400714819323198485)
        rank^=rank>>np.uint64(29)
        df['sample_rank']=rank
        for tid,g in df.groupby('final_topic_id'):
            candidates=g.nsmallest(args.per_topic,'sample_rank').to_dict('records')
            if args.partial:candidates=[apply(r,old)[0] for r in candidates]
            candidates=[r for r in candidates if r['assignment_status'] in ACCEPTED]
            pool[tid]=sorted(pool.get(tid,[])+candidates,key=lambda r:r['sample_rank'])[:args.per_topic]
    selected={int(r['row_id']):r for rows in pool.values() for r in rows}
    # Original input hashes were verified. Reuse already saved excerpts only;
    # all labels above were freshly read from the current official assignments.
    cached={}
    for previous in ['partial_review_samples.json','round2_review_samples.json','round3_review_samples.json']:
        f=BASE/'evidence'/previous
        if f.exists():
            for r in read(f)['records']:cached[r['row_id']]=r
    for rid,r in selected.items():
        if rid in cached:
            r.update({k:cached[rid][k] for k in ['original_title','body_excerpt','url','source_part']})
    parts=read(OLD/'data/INPUT_MANIFEST.json')['parts']
    for part in parts:
        ids=sorted(r for r in selected if r not in cached and part['first_row']<=r<part['first_row']+part['n'])
        if not ids:continue
        t=pq.read_table(OLD/part['file'],columns=['row_id','title','body','url'])
        for r in t.take(pa.array([i-part['first_row'] for i in ids])).to_pylist():
            q=process(r['title'],r['body'])
            s=selected[r['row_id']]
            s.update(original_title=r['title'],body_excerpt=q['body'][:1000],url=r['url'],source_part=part['file'])
    for s in selected.values():
        s.pop('sample_rank',None)
        for k,v in list(s.items()):
            if isinstance(v,float) and np.isnan(v):s[k]=None
    output=BASE/'evidence'/('partial_review_samples.json' if args.partial else 'final_review_samples.json')
    ordered=sorted(selected.values(),key=lambda r:(r['final_topic_id'],r['row_id']))
    dump(output,dict(created_utc=now(),seed=seed,per_topic=args.per_topic,topics=len(pool),records=ordered,
        excluded_prior_evidence_rows=len(excluded),scope='Fresh stratified diagnostic sample of accepted changed labels, not a population accuracy estimate; saved excerpts are not automatically considered read.'))
    print(output.name,'records',len(ordered),'topics',len(pool),flush=True)

if __name__=='__main__':main()
