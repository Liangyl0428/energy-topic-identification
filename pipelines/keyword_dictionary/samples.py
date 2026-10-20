from common import *
import pyarrow.parquet as pq

def main():
    c=connect()
    sample=c.execute('''WITH chosen AS (SELECT e.row_id,e.topic_code,p.doc_id,row_number() OVER(PARTITION BY topic_code ORDER BY
       md5(p.doc_id||topic_code||'dictionary-review-v1')) sample_rank
       FROM topic_relations e JOIN papers p USING(row_id)
       WHERE NOT p.retracted AND NOT p.template_record
       QUALIFY sample_rank<=2) SELECT e.*,s.doc_id,s.sample_rank,a.anchor_keywords,a.anchor_topic_codes FROM chosen s JOIN topic_relations e USING(row_id,topic_code) JOIN assignments a USING(row_id) ORDER BY topic_code,sample_rank''').df()
    old=ROOT/'work/nmf500_multilabel_scope_20261019/acceptance_20261019/paper_samples.parquet'
    old_samples=pd.read_parquet(old)[['row_id','doc_id','title','body','evidence_id']]
    ids=set(sample.row_id)|set(old_samples.row_id)
    # Include the clearly wrong source-keyword battery references as regression evidence.
    ids|={2788864,4813066}
    frames=[]
    for p in sorted(CORPUS.glob('part-*.parquet')):
        pf=pq.ParquetFile(p);st=pf.metadata.row_group(0).column(0).statistics
        own=sorted(int(i) for i in ids if st.min<=i<=st.max)
        if own:frames.append(pd.read_parquet(p,columns=['row_id','doc_id','title','body','language','date','url'],filters=[('row_id','in',own)]))
    meta=pd.concat(frames,ignore_index=True)
    sample=sample.merge(meta,on=['row_id','doc_id'],validate='many_to_one')
    sample['evidence_id']=[f'D{i+1:03d}' for i in range(len(sample))]
    sample['body_excerpt']=sample.body.fillna('').str[:1600]
    sample.drop(columns='body').to_parquet(WORK/'new_topic_samples.parquet',index=False)
    c.register('oldids',old_samples[['row_id','evidence_id']])
    comparison=c.execute('''SELECT o.evidence_id,a.* FROM oldids o JOIN assignments a USING(row_id) ORDER BY o.evidence_id''').df()
    comparison.merge(old_samples[['evidence_id','title']],on='evidence_id').to_parquet(WORK/'previous_audit_regression.parquet',index=False)
    meta.to_parquet(WORK/'review_metadata.parquet',index=False)
    sample_keys=sample[['evidence_id','row_id']].drop_duplicates();c.register('sample_keys',sample_keys)
    sample_words=c.execute('''SELECT s.evidence_id,o.row_id,k.raw_name,d.decision,d.topic_code
        FROM sample_keys s JOIN observations o USING(row_id) JOIN keyword_lookup k USING(keyword_id)
        JOIN dictionary d USING(keyword_code) ORDER BY evidence_id,k.raw_name''').df()
    sample_words.to_csv(WORK/'sample_all_keywords.csv',index=False)
    print('NEW_SAMPLES',len(sample),'TOPICS',sample.topic_code.nunique(),'OLD_REGRESSION',len(comparison))

if __name__=='__main__':main()
