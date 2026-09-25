from audit_metrics import *
import pyarrow as pa

CASES=[
 ('O01','钙钛矿太阳能电池',[66,220,384,787]),
 ('O02','TiO2光催化',[308,768,866]),
 ('O03','OLED',[393,966]),
 ('O04','聚合物电解质',[49,126,940]),
 ('O05','电池状态估计',[375,893]),
 ('O06','厌氧消化',[772,785]),
 ('O07','沼气/产甲烷',[274,623,702,805]),
 ('O08','超级电容器',[59,268,603,650,773,858]),
 ('O09','活性炭',[347,946]),
 ('O10','ZnO光催化',[203,933]),
 ('O11','析氢电催化',[363,561]),
 ('O12','电池单体及结构',[264,735]),
 ('O13','电价',[619,651]),
 ('O14','荧光粉',[503,886]),
 ('O15','地热',[538,638,641]),
 ('O16','正极活性材料',[199,776,850]),
 ('C01','DSSC不同部件核对',[360,534,608]),
 ('C02','微电网不同任务核对',[104,791]),
 ('Q01','疑似非主题/模板类',[205,316,568,576,700,888,952]),
]

def main():
    topics=pd.read_csv(BASE/'results/final_topics.csv').fillna('')
    mapping=pd.read_csv(BASE/'results/raw_to_final.csv').fillna('')
    cards=read(BASE/'review/topic_cards.json')
    e=pq.read_table(RAW/'evidence/review_documents.parquet').to_pandas()
    old=set(e.row_id)
    for name in ['fresh_random_audit.json','fresh_synonym_audit_v2.json']:
        old.update(r['row_id'] for r in read(BASE/'evidence'/name)['records'])
    selected=sorted({i for _,_,g in CASES for i in g})
    records=[]
    for i in selected:
        final_id=f'S{i:04d}'
        members=mapping[mapping.final_topic_id==final_id].raw_cluster1000.tolist()
        assert len(members)
        for raw_id in members:
            t=cards[raw_id]
            dominant=max([('paper',t['papers']),('patent',t['patents']),('policy',t['policies'])],key=lambda s:s[1])[0]
            v=e[(e.cluster==raw_id)&(e.source==dominant)]
            for r in v.itertuples():
                if not set(r.selection_roles.split('|'))&{'center:1','center:2'}:
                    continue
                records.append(dict(row_id=int(r.row_id),topic_id=final_id,raw_cluster=int(r.cluster),
                    source=r.source,title=r.title,body_excerpt=str(r.body)[:1000],body_sha256=r.body_sha256,
                    selection='existing_'+r.selection_roles,source_part=r.source_part,url=r.url))
    y=np.load(BASE/'results/final_labels.npy',mmap_mode='r')
    raw=np.load(RAW/'results/raw_labels.npy',mmap_mode='r')
    excluded=np.array(sorted(old))
    rng=np.random.default_rng(2026092503)
    chosen={}
    for i in selected:
        fid=f'S{i:04d}'
        fi=int(topics[topics.final_topic_id==fid].iloc[0].final_topic_index)
        ids=np.flatnonzero(y==fi)
        ids=ids[~np.isin(ids,excluded)]
        for rid in rng.choice(ids,6,replace=False):chosen[int(rid)]=fid
    for n,p in enumerate(read(CORPUS/'data/INPUT_MANIFEST.json')['parts']):
        ids=sorted(r for r in chosen if p['first_row']<=r<p['first_row']+p['n'])
        if not ids:continue
        table=pq.read_table(CORPUS/p['file'],columns=['row_id','doc_id','source','title','body','url','quality_note','title_only'])
        for r in table.take(pa.array([x-p['first_row'] for x in ids])).to_pylist():
            body=r.pop('body') or ''
            r.update(topic_id=chosen[r['row_id']],raw_cluster=int(raw[r['row_id']]),body_excerpt=body[:1000],
                body_sha256=hashlib.sha256(body.encode()).hexdigest(),full_body_characters=len(body),
                selection='fresh_random:seed2026092503',source_part=p['file'])
            records.append(r)
        if n%50==0:print('sampling parts',n,'records',len(records),flush=True)
    assert sum(r['selection'].startswith('fresh') for r in records)==len(chosen)
    records.sort(key=lambda r:(r['topic_id'],r['selection'],r['row_id']))
    dump(AUDIT/'evidence/audit_samples.json',dict(seed=2026092503,fresh_samples_per_topic=6,
        selected_topics=len(selected),fresh_records=len(chosen),total_records=len(records),
        cases=[dict(case_id=c,title=t,topics=[f'S{i:04d}' for i in g]) for c,t,g in CASES],records=records,
        scope='Saved evidence, not a claim of full-text reading. Rendered excerpts logged separately.'))
    print('saved',len(records),'records for',len(selected),'current topics',flush=True)

if __name__=='__main__':main()
