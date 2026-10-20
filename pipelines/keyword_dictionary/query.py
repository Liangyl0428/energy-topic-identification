from common import *
import argparse

def lookup(doc_id):
    c=duckdb.connect();c.execute('SET threads=2')
    a=c.execute('SELECT * FROM read_parquet(?) WHERE doc_id=?',[str(WORK/'paper_assignments/*.parquet'),doc_id]).df()
    if a.empty:return {'doc_id':doc_id,'found':False}
    r=a.iloc[0]
    edges=c.execute('SELECT * FROM read_parquet(?) WHERE row_id=? ORDER BY topic_code',[str(WORK/'paper_topic_relations/*.parquet'),int(r.row_id)]).df()
    topics=pd.read_csv(WORK/'topic_catalog.csv').set_index('topic_code')
    raw=c.execute('SELECT keyword_id,score FROM read_parquet(?) WHERE row_id=?',[str(FROZEN/'keyword_parts/*.parquet'),int(r.row_id)]).df()
    d=pd.read_csv(WORK/'keyword_dictionary.csv');aliases=pd.read_csv(WORK/'keyword_aliases.csv')
    raw=raw.merge(aliases[['keyword_id','raw_name','keyword_code']],on='keyword_id').merge(d[['keyword_code','decision','decision_reason']],on='keyword_code')
    return {'doc_id':doc_id,'found':True,'classification_status':r.classification_status,
        'quality_eligible':bool(r.quality_eligible),'anchor_keywords':r.anchor_keywords.tolist(),
        'topics':[{'topic_code':x.topic_code,'name':topics.loc[x.topic_code,'name'],
                   'direct':bool(x.has_direct_hit),'matched_keywords':x.matched_keywords.tolist(),
                   'matched_keyword_codes':x.matched_keyword_codes.tolist()} for x in edges.itertuples()],
        'source_keywords':raw.to_dict('records')}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('doc_id');args=p.parse_args()
    print(json.dumps(lookup(args.doc_id),ensure_ascii=False,indent=2))
