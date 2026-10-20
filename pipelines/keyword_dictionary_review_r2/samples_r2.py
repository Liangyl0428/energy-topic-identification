from common import *
import pyarrow.parquet as pq

def main():
    c=connect();oldroot=ROOT/'work/keyword_dictionary_multilabel_20261019'
    old=pd.read_parquet(oldroot/'new_topic_samples.parquet')
    prior=pd.read_parquet(ROOT/'work/nmf500_multilabel_scope_20261019/acceptance_20261019/paper_samples.parquet')
    excluded=pd.concat([old[['row_id']],prior[['row_id']]]).drop_duplicates()
    c.register('excluded_sample_ids',excluded)
    samples=c.execute('''WITH selected AS (
       SELECT e.row_id,e.topic_code,p.doc_id,
       row_number() OVER(PARTITION BY e.topic_code ORDER BY md5(p.doc_id||e.topic_code||'semantic-review-r2-fresh')) sample_rank
       FROM topic_relations e JOIN papers p USING(row_id) ANTI JOIN excluded_sample_ids x USING(row_id)
       WHERE NOT p.retracted AND NOT p.template_record QUALIFY sample_rank<=2)
       SELECT e.*,s.doc_id,s.sample_rank,a.anchor_keywords,a.anchor_topic_codes
       FROM selected s JOIN topic_relations e USING(row_id,topic_code) JOIN assignments a USING(row_id)
       ORDER BY e.topic_code,s.sample_rank''').df()
    samples['evidence_id']=[f'R{i+1:03d}' for i in range(len(samples))]
    changes=pd.read_csv(WORK/'term_semantic_review.csv').fillna('')
    direct=changes[changes.decision.eq('direct') & ~changes.prior_decision.eq('direct')]
    c.register('new_direct_terms',direct[['keyword_code']])
    term_samples=c.execute('''SELECT h.row_id,h.topic_code,p.doc_id,h.keyword_code,h.display_name,
       row_number() OVER(PARTITION BY h.keyword_code ORDER BY md5(p.doc_id||h.keyword_code||'new-direct-term-r2')) sample_rank
       FROM candidate_hits h JOIN new_direct_terms n USING(keyword_code) JOIN papers p USING(row_id)
       WHERE NOT p.retracted AND NOT p.template_record
       QUALIFY sample_rank=1 ORDER BY h.keyword_code''').df()
    term_samples['evidence_id']=[f'N{i+1:03d}' for i in range(len(term_samples))]
    ids=set(samples.row_id)|set(term_samples.row_id)|set(old.row_id)
    frames=[]
    for part in sorted(CORPUS.glob('part-*.parquet')):
        st=pq.ParquetFile(part).metadata.row_group(0).column(0).statistics
        own=sorted(int(i) for i in ids if st.min<=i<=st.max)
        if own:frames.append(pd.read_parquet(part,columns=['row_id','doc_id','title','body','language','date','url'],filters=[('row_id','in',own)]))
    meta=pd.concat(frames,ignore_index=True)
    for frame,name in [(samples,'fresh_topic_samples'),(term_samples,'new_direct_term_samples')]:
        frame=frame.merge(meta,on=['row_id','doc_id'],validate='many_to_one');frame['body_excerpt']=frame.body.fillna('').str[:2500]
        frame.drop(columns='body').to_parquet(WORK/f'{name}.parquet',index=False)
    meta.to_parquet(WORK/'review_metadata.parquet',index=False)
    c.register('sampleids',pd.concat([samples[['row_id','evidence_id']],term_samples[['row_id','evidence_id']]]))
    c.execute('''SELECT s.evidence_id,k.raw_name,d.decision,d.topic_code,o.score
       FROM sampleids s JOIN observations o USING(row_id) JOIN keyword_lookup k USING(keyword_id)
       JOIN dictionary d USING(keyword_code) ORDER BY evidence_id,k.raw_name''').df().to_csv(WORK/'sample_source_keywords.csv',index=False)
    notes=pd.read_csv(oldroot/'sample_review.csv')
    old=old.merge(notes,on='evidence_id',validate='one_to_one');c.register('prior_semantic_samples',old[['row_id','topic_code','evidence_id','title','review_status','review_note']])
    regression=c.execute('''SELECT o.*,e.row_id IS NOT NULL still_assigned_to_original_topic,
       a.doc_id,a.classification_status,a.topic_codes final_topic_codes
       FROM prior_semantic_samples o JOIN assignments a USING(row_id)
       LEFT JOIN topic_relations e USING(row_id,topic_code) ORDER BY o.evidence_id''').df()
    regression.to_parquet(WORK/'previous_semantic_review_regression.parquet',index=False)
    regression['final_topic_codes']=regression.final_topic_codes.map(lambda x:' | '.join(x))
    regression[~regression.review_status.isin(['题名支持','正文支持'])].to_csv(WORK/'previous_semantic_issues.csv',index=False,encoding='utf-8-sig')
    write(WORK/'SAMPLES.json',{'fresh_topic_relations':len(samples),'topics':int(samples.topic_code.nunique()),
       'new_direct_term_examples':len(term_samples),'old_sample_papers_excluded':len(excluded),
       'new_sample_no_overlap_with_v1':not bool(set(samples.row_id)&set(excluded.row_id)),
       'sampling':'2 md5-ranked nonflagged paper relations per topic, excluding all v1 142 semantic samples and the previous 150 NMF audit papers; additional one example per new direct keyword.'})
    print('FRESH',len(samples),'NEW_DIRECT_TERM_EXAMPLES',len(term_samples),flush=True)

if __name__=='__main__':main()
