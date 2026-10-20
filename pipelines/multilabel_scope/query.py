"""Look up a document at any saved threshold >=.05 without renormalization."""
from run import *
import duckdb


def lookup(doc_id,threshold=.10):
    if not .05<=threshold<=1:raise ValueError('Saved edges support thresholds from .05 to 1; lower values require inference.')
    c=duckdb.connect();c.execute('SET threads=4')
    a=c.execute('SELECT * FROM read_parquet(?,union_by_name=true) WHERE doc_id=?',
        [str(OUT/'business_assignments/*.parquet'),doc_id]).df()
    if a.empty:return {'doc_id':doc_id,'found':False}
    row=a.iloc[0];rid=int(row.row_id)
    edges=c.execute('SELECT * FROM read_parquet(?,union_by_name=true) WHERE row_id=? AND relative_contribution>=? ORDER BY relative_contribution DESC,topic_id',
        [str(OUT/'business_edges_ge_005/*.parquet'),rid,threshold]).df()
    eligible=edges.quality_gate_pass&~edges.relation_review_rejected
    core=bool((eligible&edges.scope_state.eq('keep_core')).any())
    context=bool(row.energy_anchor_present) or core
    keep=eligible&(edges.scope_state.eq('keep_core')|(edges.scope_state.eq('keep_supporting')&context))
    catalog=pd.read_csv(OUT/'topic_catalog_reviewed.csv').set_index('topic_id')
    labels=pd.read_csv(OUT/'review/topic_display_labels.csv').set_index('topic_id').display_name_zh.to_dict()
    records=[]
    for pos,r in enumerate(edges.itertuples()):
        records.append({'topic_code':catalog.loc[r.topic_id,'topic_code'],'display_name':labels.get(r.topic_id,catalog.loc[r.topic_id,'name']),
            'raw_name':catalog.loc[r.topic_id,'name'],'contribution':float(r.relative_contribution),'score_kind':r.score_kind,
            'scope_state':r.scope_state,'included':bool(keep.iloc[pos]),'relation_review_rejected':bool(r.relation_review_rejected)})
    return {'doc_id':doc_id,'found':True,'source':row.source,'threshold':threshold,
        'requires_semantic_review':bool(row.requires_semantic_review),'post_scope_renormalized':False,
        'topics':records,'included_topics':sum(r['included'] for r in records)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('doc_id');p.add_argument('--threshold',type=float,default=.10);args=p.parse_args()
    print(json.dumps(lookup(args.doc_id,args.threshold),ensure_ascii=False,indent=2))
