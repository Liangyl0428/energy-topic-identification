"""Apply the versioned scope ledger without deleting or renormalizing scores."""
from run import *
import pyarrow as pa
import pyarrow.parquet as pq
from review import ENERGY_PATTERN

STATES={'keep_core','keep_supporting','review','exclude'}
KEEP={'keep_core','keep_supporting'}
THRESHOLDS=[.05,.10,.15]


def scope_membership(topic_ids, contributions, states, threshold=.10, qualified=True):
    ids=np.asarray(topic_ids,dtype=int);p=np.asarray(contributions,dtype=float)
    if not qualified:return [],[]
    chosen=(p>=threshold)&np.isin(np.asarray(states)[ids],list(KEEP))
    order=np.flatnonzero(chosen);order=order[np.argsort(-p[order],kind='stable')]
    return ids[order].tolist(),p[order].tolist()


def ledger():
    path=OUT/'review/topic_scope_decisions.csv'
    f=pd.read_csv(path).fillna('').sort_values('topic_id')
    assert len(f)==K and np.array_equal(f.topic_id,np.arange(K)) and set(f.scope_state)<=STATES
    assert f.scope_reason.ne('').all() and f.reviewer.ne('').all()
    assert f.topic_code.tolist()==[f'RBK500-T{t+1:04d}' for t in range(K)]
    return f


def main():
    decisions=ledger();states=decisions.scope_state.to_numpy();kept=np.isin(states,list(KEEP));pending=states=='review'
    scope_hash=sha(OUT/'review/topic_scope_decisions.csv')
    override_path=OUT/'review/relation_review_overrides.csv'
    overrides=pd.read_csv(override_path) if override_path.exists() else pd.DataFrame(columns=['doc_id','topic_id','action'])
    rejected_pairs={(r.doc_id,int(r.topic_id)) for r in overrides.itertuples() if r.action=='reject'}
    target=OUT/'business_assignments';target.mkdir(exist_ok=True)
    (OUT/'business_edges_ge_005').mkdir(exist_ok=True)
    sensitivity=[];topic_stats=[];partstats=[]
    for file in sorted(CORPUS.glob('part-*.parquet')):
        meta=pd.read_parquet(file,columns=['row_id','doc_id','source','date','retracted','template_record','title','body'])
        document_text=meta.title.fillna('')+' '+meta.body.fillna('')
        anchor=document_text.str.contains(ENERGY_PATTERN).to_numpy()
        meta=meta.drop(columns=['title','body'])
        paper_file=OUT/'full_model/paper_assignments'/file.name
        transfer_file=OUT/'transfer/assignments'/file.name
        raw_parts=[]
        if paper_file.exists():
            p=pd.read_parquet(paper_file)
            p['source']='paper';p['score_kind']='nmf_l2_relative_contribution'
            p['quality_gate_pass']=True
            raw_parts.append(p[['row_id','doc_id','source','assignment_status','score_kind','quality_gate_pass']])
        if transfer_file.exists():
            p=pd.read_parquet(transfer_file)
            raw_parts.append(p[['row_id','doc_id','source','assignment_status','score_kind','quality_gate_pass']])
        raw=pd.concat(raw_parts,ignore_index=True).sort_values('row_id')
        assert np.array_equal(raw.row_id,meta.row_id) and np.array_equal(raw.doc_id,meta.doc_id)
        result=meta.merge(raw.drop(columns=['doc_id','source']),on='row_id',validate='one_to_one')
        result['quality_gate_pass'] &= ~result.retracted & ~result.template_record
        edge_parts=[]
        for folder in [OUT/'full_model/contribution_edges_ge_005',OUT/'transfer/contribution_edges_ge_005']:
            if (folder/file.name).exists():
                edge_parts.append(pd.read_parquet(folder/file.name)[['row_id','topic_id','relative_contribution']])
        e=pd.concat(edge_parts,ignore_index=True).sort_values(['row_id','relative_contribution','topic_id'],ascending=[True,False,True]).reset_index(drop=True)
        pos=np.searchsorted(meta.row_id,e.row_id)
        assert np.array_equal(meta.row_id.to_numpy()[pos],e.row_id)
        topic=e.topic_id.to_numpy();score=e.relative_contribution.to_numpy()
        qualified=result.quality_gate_pass.to_numpy()[pos]
        rejected=np.zeros(len(e),dtype=bool)
        if rejected_pairs and meta.source.ne('paper').any():
            for did,t in rejected_pairs:
                loc=meta.index[meta.doc_id==did]
                if len(loc):rejected|=(pos==loc[0])&(topic==t)
        qualified &= ~rejected
        core_coassignment=np.bincount(pos[(score>=.10)&qualified&(states[topic]=='keep_core')],minlength=len(meta))>0
        support_context=anchor|core_coassignment
        business_allowed=(states[topic]=='keep_core')|((states[topic]=='keep_supporting')&support_context[pos])
        e['source']=meta.source.to_numpy()[pos]
        e['score_kind']=result.score_kind.to_numpy()[pos]
        e['scope_state']=states[topic];e['quality_gate_pass']=qualified
        e['energy_anchor_present']=anchor[pos]
        e['relation_review_rejected']=rejected
        e['business_scope_eligible_at_010']=qualified&business_allowed
        e['business_included_at_010']=qualified&business_allowed&(score>=.10)
        e.to_parquet(OUT/'business_edges_ge_005'/file.name,index=False)
        retained=[[] for _ in range(len(meta))];weights=[[] for _ in range(len(meta))]
        pending_ids=[[] for _ in range(len(meta))];excluded_ids=[[] for _ in range(len(meta))]
        raw_count=np.bincount(pos[score>=.10],minlength=len(meta))
        for edge in np.flatnonzero((score>=.10)&qualified):
            row=int(pos[edge]);t=int(topic[edge])
            if business_allowed[edge]:retained[row].append(t);weights[row].append(float(score[edge]))
            elif pending[t] or states[t]=='keep_supporting':pending_ids[row].append(t)
            else:excluded_ids[row].append(t)
        result['topic_ids']=retained;result['topic_contributions']=weights
        result['topic_count']=[len(a) for a in retained]
        result['retained_contribution']=[sum(a) for a in weights]
        result['scope_review_topic_ids']=pending_ids;result['excluded_topic_ids']=excluded_ids
        result['raw_topic_count_at_010']=raw_count
        result['energy_anchor_present']=anchor
        result['support_context_eligible_at_010']=support_context
        result['requires_semantic_review']=result.source.ne('paper')
        result['business_status']=np.where(result.topic_count>0,np.where(result.source.eq('paper'),'assigned','assigned_candidate'),
            np.where(~result.quality_gate_pass,'quality_gate_abstained',
            np.where(np.array([len(x)>0 for x in pending_ids]),'scope_review_pending',
            np.where(np.array([len(x)>0 for x in excluded_ids]),'excluded_by_topic_scope',result.assignment_status))))
        reject_count=np.bincount(pos[rejected&(score>=.10)],minlength=len(meta))
        result['rejected_relation_count']=reject_count
        result.loc[(result.topic_count==0)&(reject_count>0),'business_status']='relation_review_rejected'
        result.to_parquet(target/file.name,index=False)
        for source,g in meta.groupby('source'):
            rows=g.index.to_numpy();s_mask=e.source.eq(source).to_numpy()
            partstats.append({'part':file.stem,'source':source,'records':len(g),'retained_documents':int((result.topic_count.iloc[rows]>0).sum()),'retained_edges':int(result.topic_count.iloc[rows].sum())})
            for threshold in THRESHOLDS:
                choose=s_mask&(score>=threshold)
                threshold_core=np.bincount(pos[(score>=threshold)&qualified&(states[topic]=='keep_core')],minlength=len(meta))>0
                threshold_context=anchor|threshold_core
                threshold_keep=(states[topic]=='keep_core')|((states[topic]=='keep_supporting')&threshold_context[pos])
                threshold_pending=pending[topic]|((states[topic]=='keep_supporting')&~threshold_context[pos])
                levels={'raw':choose,'quality_qualified':choose&qualified,'retained':choose&qualified&threshold_keep,
                    'pending':choose&qualified&threshold_pending,'excluded':choose&qualified&(states[topic]=='exclude')}
                for stage, mask in levels.items():
                    counts=np.bincount(pos[mask],minlength=len(meta))[rows]
                    total_mass=float(score[mask].sum(dtype='float64'))
                    sensitivity.append({'source':source,'threshold':threshold,'stage':stage,'records':len(g),
                        'assigned_documents':int((counts>0).sum()),'multiple_topic_documents':int((counts>1).sum()),
                        'edges':int(counts.sum()),'contribution_mass':total_mass})
                for mask_name,mask in [('quality_qualified',levels['quality_qualified']),('retained',levels['retained'])]:
                    count=np.bincount(topic[mask],minlength=K)
                    mass=np.bincount(topic[mask],weights=score[mask],minlength=K)
                    for t in np.flatnonzero(count):
                        topic_stats.append({'source':source,'threshold':threshold,'stage':mask_name,'topic_id':int(t),
                            'documents':int(count[t]),'contribution_mass':float(mass[t])})
        print('SCOPE_APPLY',file.stem,flush=True)
    s=pd.DataFrame(sensitivity).groupby(['source','threshold','stage'],as_index=False).sum()
    s['coverage']=s.assigned_documents/s.records
    s['mean_topics_assigned']=s.edges/s.assigned_documents.replace(0,np.nan)
    s.to_csv(OUT/'threshold_scope_sensitivity.csv',index=False)
    t=pd.DataFrame(topic_stats).groupby(['source','threshold','stage','topic_id'],as_index=False).sum()
    t.to_csv(OUT/'topic_counts_by_source_threshold.csv',index=False)
    pd.DataFrame(partstats).to_csv(OUT/'business_part_coverage.csv',index=False)
    catalog=pd.read_csv(OUT/'full_model/topic_catalog.csv').drop(columns=['scope_review_status'])
    catalog=catalog.merge(decisions.drop(columns=['name','top_keywords'],errors='ignore'),on=['topic_id','topic_code'],validate='one_to_one')
    catalog.to_csv(OUT/'topic_catalog_reviewed.csv',index=False,encoding='utf-8-sig')
    write(OUT/'SCOPE_APPLIED.json',{'completed_at':base.stamp(),'scope_ledger_sha256':scope_hash,'default_threshold':.10,
        'records':int(pd.DataFrame(partstats).records.sum()),'scope_counts':decisions.scope_state.value_counts().to_dict(),
        'no_post_exclusion_renormalization':True,'original_raw_scores_preserved':True,
        'relation_review_overrides_sha256':sha(override_path) if override_path.exists() else None,
        'explicitly_rejected_relations':len(rejected_pairs),
        'supporting_topic_document_rule':'Keep supporting-topic membership only when full frozen title/body matches the disclosed energy-anchor pattern or a core-topic membership passes the same threshold. Otherwise pending; absence of an anchor is not a finding of irrelevance.',
        'membership_tables':'business_assignments/*.parquet','all_edges':'business_edges_ge_005/*.parquet',
        'scope_authority':'Assistant preliminary review; no human expert approval is claimed.'})


if __name__=='__main__':main()
