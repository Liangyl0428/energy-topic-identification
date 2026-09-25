"""Export full final label shards with all old fields retained; read back every row."""
from merge_common import *
from semantic_mapping import make_mapping,map_labels
from candidate_review import export_candidate_decisions
import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq
from scipy import sparse
from sklearn.preprocessing import normalize
from threadpoolctl import threadpool_limits
import joblib,collections

def main():
    threadpool_limits(4)
    decisions=read(BASE/'review/decisions.json');groups=decisions['merge_groups']
    anchor,lookup,anchors=make_mapping(groups);k=len(anchors)
    t=pd.read_csv(RAW/'results/topics1000_with_comparison.csv').fillna('')
    assert t.cluster.tolist()==list(range(1000))
    old=np.load(RAW/'results/raw_labels.npy',mmap_mode='r');final=map_labels(old,lookup)
    np.save(BASE/'results/final_labels.npy',final)
    np.save(BASE/'models/raw_to_final_index.npy',lookup)
    np.save(BASE/'models/raw_to_final_anchor.npy',anchor)
    groupby={i:g for g in groups for i in g['members']}
    inspected=read(BASE/'review/ACTUALLY_INSPECTED.json');detailed=set(inspected['detailed_topics'])
    rows=[]
    for r in t.itertuples():
        i=int(r.cluster);g=groupby.get(i)
        status='经抽样语义复核合并；含边界噪声' if g else ('已抽样复核；保留原类；名称仍为自动标签' if i in detailed else '完成清单初筛；保留原类及自动标签')
        rows.append(dict(raw_cluster1000=i,raw_topic_id=r.topic_id,raw_automatic_label=r.automatic_label,
           final_topic_index=int(lookup[i]),final_topic_id=f'S{anchor[i]:04d}',
           final_topic_label=g['canonical_name'] if g else r.automatic_label,
           semantic_merge_applied=bool(g),merge_decision_id=g['decision_id'] if g else '',
           final_label_status=status,raw_documents=int(r.documents),raw_papers=int(r.papers),
           raw_patents=int(r.patents_2026),raw_policies=int(r.policies)))
    mapping=pd.DataFrame(rows);mapping.to_csv(BASE/'results/raw_to_final.csv',index=False,encoding='utf-8-sig')
    previous_path=BASE/'history/v1_998_before_synonym_merge/results/raw_to_final.csv'
    previous=pd.read_csv(previous_path).fillna('') if previous_path.exists() else None
    if previous is not None:
        assert previous.raw_cluster1000.tolist()==mapping.raw_cluster1000.tolist()
    # Aggregate exact document word counts, then refit the same c-TF-IDF formula.
    counts=sparse.load_npz(RAW/'models/class_word_counts.npz').tocsr()
    reduction=sparse.csr_matrix((np.ones(1000,dtype=np.int64),(lookup,np.arange(1000))),shape=(k,1000))
    mergedcounts=(reduction@counts).tocsr()
    np.testing.assert_array_equal(np.asarray(mergedcounts.sum(axis=0)),np.asarray(counts.sum(axis=0)))
    tf=normalize(mergedcounts.astype(np.float64),norm='l1',axis=1)
    tf.data=np.sqrt(tf.data)
    idf=np.log1p(int(mergedcounts.sum(axis=1).mean())/np.maximum(np.asarray(mergedcounts.sum(axis=0)).ravel(),1))
    ctf=(tf@sparse.diags(idf)).tocsr();assert np.isfinite(ctf.data).all()
    sparse.save_npz(BASE/'models/class_word_counts.npz',mergedcounts)
    sparse.save_npz(BASE/'models/ctfidf.npz',ctf)
    sys.path[:0]=[str(CORPUS/'src')]
    vec=joblib.load(CORPUS/'models/vectorizer.joblib');words=vec.get_feature_names_out()
    topics=[]
    for fi,a in enumerate(anchors):
        members=np.flatnonzero(anchor==a);m=mapping.iloc[members];r=m.iloc[0]
        row=ctf.getrow(fi);order=np.argsort(row.data)[::-1][:20]
        topics.append(dict(final_topic_index=fi,final_topic_id=r.final_topic_id,final_topic_label=r.final_topic_label,
           final_label_status=r.final_label_status,raw_topic_members='|'.join(f'T{i:04d}' for i in members),
           raw_topic_count=len(members),documents=int(m.raw_documents.sum()),papers=int(m.raw_papers.sum()),
           patents=int(m.raw_patents.sum()),policies=int(m.raw_policies.sum()),keywords=' | '.join(words[row.indices[order]]),
           merge_decision_id=r.merge_decision_id,
           title_only_documents=int(t.iloc[members].title_only_documents.sum()),
           retracted_documents=int(t.iloc[members].retracted_documents.sum()),
           template_record_documents=int(t.iloc[members].template_record_documents.sum())))
    topics=pd.DataFrame(topics);topics.to_csv(BASE/'results/final_topics.csv',index=False,encoding='utf-8-sig')
    all_counts=np.zeros(k,dtype=np.int64);source_counts=np.zeros((k,3),dtype=np.int64)
    source_lookup={'paper':0,'patent':1,'policy':2}
    inmanifest=read(RAW/'results/ASSIGNMENT_MANIFEST.json');parts=[];cursor=0;changed=0
    finalids=mapping.final_topic_id.to_numpy();names=mapping.final_topic_label.to_numpy()
    statuses=mapping.final_label_status.to_numpy();groupflags=mapping.semantic_merge_applied.to_numpy();decisionids=mapping.merge_decision_id.to_numpy()
    def strings(y,values,invalid):return pa.array([values[int(i)] if i>=0 else invalid for i in y])
    for ix,p in enumerate(inmanifest['parts']):
        path=RAW/p['file'];assert sha(path)==p['sha256'],f'input hash changed: {path}'
        table=pq.read_table(path);ids=table['row_id'].to_numpy();y=table['new_cluster1000'].to_numpy()
        np.testing.assert_array_equal(ids,np.arange(cursor,cursor+len(ids)));cursor+=len(ids)
        np.testing.assert_array_equal(y,old[ids])
        z=map_labels(y,lookup);good=y>=0;sec=table['secondary_candidate1000'].to_numpy()
        # Raw secondary candidates are references, not recomputed merged-topic probabilities.
        assert ((sec>=0)&(sec<1000)|np.isin(sec,[-1,-2])).all()
        flags=np.zeros(len(y),dtype=bool);flags[good]=groupflags[y[good]]
        same=np.zeros(len(y),dtype=bool);validsecond=(sec>=0)&good
        same[validsecond]=lookup[sec[validsecond]]==z[validsecond]
        additions={'final_topic_index':pa.array(z),'final_topic_id':strings(y,finalids,'UNUSABLE'),
          'final_topic_label':strings(y,names,'不可用文本（未分类）'),
          'final_label_status':strings(y,statuses,'不可用文本；保留未分类'),
          'semantic_merge_applied':pa.array(flags),'merge_decision_id':strings(y,decisionids,''),
          'final_secondary_topic_id':strings(sec,finalids,'UNUSABLE'),
          'secondary_maps_to_primary':pa.array(same)}
        out=table
        for col,a in additions.items():out=out.append_column(col,a)
        dest=BASE/'results/assignments'/path.name;pq.write_table(out,dest,compression='zstd')
        check=pq.read_table(dest)
        # pandas equality handles NaN sentinels in the raw margin/cosine columns.
        assert check.select(table.column_names).to_pandas().equals(table.to_pandas()),f'raw fields changed: {dest}'
        for col,a in additions.items():assert check[col].combine_chunks().equals(a),f'final column mismatch: {col}'
        np.testing.assert_array_equal(check['final_topic_index'].to_numpy(),final[ids])
        assert (check['final_topic_id'].to_numpy()[~good]=='UNUSABLE').all()
        all_counts+=np.bincount(z[good],minlength=k)
        source=np.array([source_lookup[s] for s in table['source'].to_pylist()])
        source_counts+=np.bincount(z[good].astype(np.int64)*3+source[good],minlength=k*3).reshape(k,3)
        changed+=int(flags.sum())
        parts.append({'file':str(dest.relative_to(BASE)),'rows':len(ids),'first_row':int(ids[0]),'last_row':int(ids[-1]),'sha256':sha(dest),
                      'raw_assignment_file':p['file'],'raw_assignment_sha256':p['sha256'],'corpus_part':p['source_part'],'corpus_sha256':p['source_sha256']})
        if (ix+1)%25==0 or ix+1==len(inmanifest['parts']):
            msg={'stage':'writing_and_reading_back_labels','parts':ix+1,'total_parts':len(inmanifest['parts']),'rows':cursor,'updated_utc':now()};dump(BASE/'PROGRESS.json',msg);print(json.dumps(msg),flush=True)
    assert cursor==len(old)==inmanifest['documents']
    np.testing.assert_array_equal(all_counts,topics.documents.to_numpy())
    np.testing.assert_array_equal(source_counts,topics[['papers','patents','policies']].to_numpy())
    assert (all_counts>0).all() and k==1000-sum(len(g['members'])-1 for g in groups)
    assert np.array_equal(final<0,old<0) and (final[old<0]==-2).all()
    np.save(BASE/'results/source_counts.npy',source_counts)
    dump(BASE/'results/ASSIGNMENT_MANIFEST.json',{'version':decisions['version'],'created_utc':now(),'documents':cursor,'assigned':int((old>=0).sum()),'unusable':int((old<0).sum()),'all_rows_read_back':True,'parts':parts})
    cand=export_candidate_decisions(decisions)
    merge_table=[]
    for g in groups:
        m=mapping[mapping.raw_cluster1000.isin(g['members'])]
        merge_table.append(dict(decision_id=g['decision_id'],raw_topics='|'.join(m.raw_topic_id),final_topic_id=m.iloc[0].final_topic_id,final_topic_label=g['canonical_name'],documents=int(m.raw_documents.sum()),papers=int(m.raw_papers.sum()),patents=int(m.raw_patents.sum()),policies=int(m.raw_policies.sum()),reason=g['reason'],limits=g['limits'],evidence_row_ids='|'.join(map(str,g['evidence_row_ids']))))
    pd.DataFrame(merge_table).to_csv(BASE/'results/merge_summary.csv',index=False,encoding='utf-8-sig')
    summary={'created_utc':now(),'version':decisions['version'],'raw_topics':1000,'final_topics':k,'merge_groups':len(groups),'raw_topics_in_merges':len(groupby),
       'topics_reduced':1000-k,'documents':cursor,'assigned_documents':int((old>=0).sum()),'unusable_documents':int((old<0).sum()),
       'documents_in_merged_groups':changed,'documents_reanchored':int(((old>=0)&(map_labels(old,anchor)!=old)).sum()),
       'assigned_by_source':dict(zip(source_lookup,map(int,source_counts.sum(0)))),'assignment_parts':len(parts),
       'detailed_review_topics':len(detailed),'reviewed_documents':inspected['unique_documents'],
       'additional_random_documents':inspected.get('additional_random_documents',96),
       'current_review_documents':inspected.get('current_review_unique_documents',inspected['unique_documents']),
       'current_additional_random_documents':inspected.get('current_additional_random_documents',96),
       'pair_decisions':len(groups)+len(decisions['keep_or_defer']),'candidate_pairs':len(cand),'all1000_inventory_screened':True,
       'no_topic_split':True,'no_individual_reassignment':True,'semantic_accuracy':None,'independent_expert_review':False,'trl_crl_recalculated':False,
       'labels_updated_in':'results/assignments/*.parquet','raw_inputs_modified':False}
    if previous is not None:
        changed_id=previous.final_topic_id.to_numpy()!=mapping.final_topic_id.to_numpy()
        changed_name=previous.final_topic_label.to_numpy()!=mapping.final_topic_label.to_numpy()
        changed_index=previous.final_topic_index.to_numpy()!=mapping.final_topic_index.to_numpy()
        summary.update(previous_final_topics=int(previous.final_topic_index.nunique()),
            new_merge_groups=decisions.get('new_merge_groups',0),
            new_topics_reduced=int(previous.final_topic_index.nunique())-k,
            documents_with_topic_id_changed_vs_previous=int(mapping.loc[changed_id,'raw_documents'].sum()),
            documents_with_topic_name_changed_vs_previous=int(mapping.loc[changed_name,'raw_documents'].sum()),
            documents_with_dense_index_changed_vs_previous=int(mapping.loc[changed_index,'raw_documents'].sum()),
            previous_snapshot='history/v1_998_before_synonym_merge',
            interpretation='stable final_topic_id tracks semantic identity; dense index can shift for untouched classes')
    dump(BASE/'results/SUMMARY.json',summary)
    dump(BASE/'models/MODEL_CONTRACT.json',{'raw_model':str(RAW/'models/bertopic1000.joblib'),'raw_model_sha256':sha(RAW/'models/bertopic1000.joblib'),
       'prediction':'frozen BERTopic1000.transform -> raw_to_final mapping','final_topic_index':'dense indices, use raw_to_final.csv; S ID suffix is an anchor raw ID, NOT the dense index',
       'final_topic_id':'S + four-digit minimum original cluster ID, stable; non-contiguous IDs are intentional',
       'ctfidf':'exact aggregation of raw class word counts, row L1 normalization, square root tf, finite log1p IDF refit',
       'probabilities':'not recomputed; raw1000 cosine/margin/secondary retained with raw field names; mapped secondary may equal primary',
       'new_document_quality':'caller must apply original unusable-text screening before inference; unusable records remain -2',
       'api':'src/semantic_mapping.py:SemanticTopicModel','maturity':'TRL/CRL must be evaluated separately for final topic IDs; no inherited values'})
    dump(BASE/'VALIDATION.json',{'passed':False,'stage':'all_assignment_rows_verified_pending_final_checks','checks':{'mapping_complete_1000':True,'all259_shards_read_back':len(parts)==259,'all_original_columns_preserved':True,'all_final_columns_verified':True,'every_raw_topic_maps_to_one_final_topic':True,'all_topic_and_source_counts_exact':True,'unusable_sentinel_preserved':True,'exact_word_counts_aggregated':True},'created_utc':now()})
    print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
