"""Add independent, reproducible samples without replacing the first audit batch."""
from audit_metrics import *
import pyarrow as pa

ADDITIONAL = [
    ('O17', '锂金属电池界面与电解质', [659,782]),
    ('O18', '聚合物太阳能电池与有机光伏', [140,158]),
    ('O19', '电动汽车充电规划与调度', [253,879]),
    ('O20', '电池模组装配与盖板结构', [379,759,864]),
    ('O21', '气候政策、适应与国际治理', [219,594,908]),
    ('C03', 'DC-DC变换器与软开关', [212,589,945]),
]

def main():
    ev=read(AUDIT/'evidence/audit_samples.json')
    if any(c['case_id']=='O17' for c in ev['cases']):
        print('Already extended; retaining original selections.'); return
    topics=pd.read_csv(BASE/'results/final_topics.csv').set_index('final_topic_id')
    mapping=pd.read_csv(BASE/'results/raw_to_final.csv')
    cards=read(BASE/'review/topic_cards.json')
    old=pq.read_table(RAW/'evidence/review_documents.parquet').to_pandas()
    excluded=set(old.row_id)|{r['row_id'] for r in ev['records']}
    for f in ['fresh_random_audit.json','fresh_synonym_audit_v2.json']:
        excluded.update(r['row_id'] for r in read(BASE/'evidence'/f)['records'])
    ys=np.load(BASE/'results/final_labels.npy',mmap_mode='r')
    raws=np.load(RAW/'results/raw_labels.npy',mmap_mode='r')
    rng=np.random.default_rng(2026092504)
    chosen={}
    for i in sorted({i for _,_,ids in ADDITIONAL for i in ids}):
        tid=f'S{i:04d}'
        for raw_id in mapping.loc[mapping.final_topic_id==tid,'raw_cluster1000']:
            c=cards[int(raw_id)]
            dominant=max([('paper',c['papers']),('patent',c['patents']),('policy',c['policies'])],key=lambda x:x[1])[0]
            for r in old[(old.cluster==raw_id)&(old.source==dominant)].itertuples():
                if not set(r.selection_roles.split('|'))&{'center:1','center:2'}:continue
                ev['records'].append(dict(row_id=int(r.row_id),topic_id=tid,raw_cluster=int(r.cluster),source=r.source,
                    title=r.title,body_excerpt=str(r.body)[:1000],body_sha256=r.body_sha256,
                    selection='existing_'+r.selection_roles,source_part=r.source_part,url=r.url))
        ids=np.flatnonzero(ys==int(topics.loc[tid].final_topic_index))
        ids=ids[~np.isin(ids,np.array(sorted(excluded)))]
        for rid in rng.choice(ids,6,replace=False):chosen[int(rid)]=tid
    for part in read(CORPUS/'data/INPUT_MANIFEST.json')['parts']:
        ids=sorted(r for r in chosen if part['first_row']<=r<part['first_row']+part['n'])
        if not ids:continue
        table=pq.read_table(CORPUS/part['file'],columns=['row_id','doc_id','source','title','body','url','quality_note','title_only'])
        for r in table.take(pa.array([i-part['first_row'] for i in ids])).to_pylist():
            body=r.pop('body') or ''
            r.update(topic_id=chosen[r['row_id']],raw_cluster=int(raws[r['row_id']]),body_excerpt=body[:1000],
                body_sha256=hashlib.sha256(body.encode()).hexdigest(),full_body_characters=len(body),
                selection='fresh_random:seed2026092504',source_part=part['file'])
            ev['records'].append(r)
    ev['cases'] += [dict(case_id=c,title=t,topics=[f'S{i:04d}' for i in ids]) for c,t,ids in ADDITIONAL]
    ev['records'].sort(key=lambda r:(r['topic_id'],r['selection'],r['row_id']))
    ev['selected_topics']=len({r['topic_id'] for r in ev['records']})
    ev['fresh_records']=sum(r['selection'].startswith('fresh') for r in ev['records'])
    ev['total_records']=len(ev['records'])
    ev['additional_seed']=2026092504
    dump(AUDIT/'evidence/audit_samples.json',ev)
    print('Saved',ev['total_records'],'records;',ev['selected_topics'],'topics;',ev['fresh_records'],'new random records')

if __name__=='__main__':main()
