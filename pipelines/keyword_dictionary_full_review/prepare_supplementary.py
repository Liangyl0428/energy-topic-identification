"""Targeted exact-term diagnostic contexts for the two unresolved risk terms."""
from common import *


def main():
    assert not (WORK/'supplementary_context_queue.parquet').exists()
    names = {'Scram':r'(?i)\bscram\b',
             'Short circuit ratio':r'(?i)short[ -]circuit[ -]ratio'}
    d = pd.read_csv(WORK/'term_review_ledger.csv',keep_default_na=False)
    t = d[d.display_name.isin(names)].copy()
    t['text_pattern'] = t.display_name.map(names)
    assert len(t) == 2
    c = connect()
    c.register('supplement_terms',t)
    base = pd.read_parquet(WORK/'frozen_context_queue.parquet')
    c.register('existing_contexts',base[['row_id','keyword_code']])
    corpus = str(CORPUS/'part-*.parquet').replace("'","''")
    q = c.execute(f'''WITH ids AS (
        SELECT DISTINCT o.row_id,k.keyword_code
        FROM observations o JOIN keyword_lookup k USING(keyword_id)
        JOIN supplement_terms t USING(keyword_code)
        ANTI JOIN existing_contexts e ON o.row_id=e.row_id AND k.keyword_code=e.keyword_code
      ), matched AS (
        SELECT p.row_id,p.doc_id,p.title,p.body,p.url,p.language,p.date,
          t.keyword_code,t.display_name,t.review_index,t.decision,t.topic_code,
          regexp_matches(coalesce(p.title,''),t.text_pattern) title_names_exact_term,
          row_number() OVER(PARTITION BY t.keyword_code ORDER BY p.retracted OR p.template_record,
            regexp_matches(coalesce(p.title,''),t.text_pattern) DESC,
            md5(p.doc_id||t.keyword_code||'targeted-supplement-v1')) sample_rank
        FROM ids JOIN read_parquet('{corpus}') p USING(row_id)
        JOIN supplement_terms t USING(keyword_code)
        WHERE regexp_matches(coalesce(p.title,'')||' '||coalesce(p.body,''),t.text_pattern)
      ) SELECT * FROM matched WHERE sample_rank<=3 ORDER BY keyword_code,sample_rank''').df()
    assert q.keyword_code.nunique()==2
    q['evidence_id']=[f'S{i+1:04d}' for i in range(len(q))]
    q.to_parquet(WORK/'supplementary_context_queue.parquet',index=False)
    c.register('supplement_samples',q[['row_id','evidence_id']])
    source=c.execute('''SELECT s.evidence_id,o.row_id,k.keyword_code,k.keyword_id,k.raw_name,o.score
        FROM supplement_samples s JOIN observations o USING(row_id)
        JOIN keyword_lookup k USING(keyword_id)
        ORDER BY s.evidence_id,k.keyword_code''').df()
    source.to_parquet(WORK/'supplementary_source_keywords.parquet',index=False)
    write(WORK/'SUPPLEMENTARY_PREPARED.json',{
        'terms':2,'contexts':len(q),'queue_sha256':sha(WORK/'supplementary_context_queue.parquet'),
        'source_keywords_sha256':sha(WORK/'supplementary_source_keywords.parquet'),
        'selection':'Targeted exact-term title/body retrieval among actually keyword-tagged papers, excluding existing same-term contexts; prefer unflagged exact-title cases, then deterministic md5.',
        'purpose':'Resolve specific word senses after broad-source samples were inconclusive.',
        'selection_is_diagnostic_not_representative':True,'semantic_labels_automatic':False})
    print('Supplementary contexts prepared:',len(q),flush=True)


if __name__=='__main__':
    main()
