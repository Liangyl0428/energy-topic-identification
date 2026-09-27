"""Build full paper centroids, assign every transfer record, and verify coverage."""
from common import *
import sys
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import duckdb
from threadpoolctl import threadpool_limits
sys.path.insert(0,str(REPO/'pipelines/keyword_nmf/src'))
from components import nearest_centroid_assign


def main():
    for marker in ['PREPARE_COMPLETE.json','TRAINING_COMPLETE.json','INFERENCE_COMPLETE.json','ENCODING_COMPLETE.json']:
        if not (RUN/marker).exists():
            raise RuntimeError('Missing full stage: '+marker)
    sums=np.zeros((K,1024),np.float64); counts=np.zeros(K,np.int64)
    out=RUN/'assignments';out.mkdir(exist_ok=True)
    expected={}; total=0
    # Use every assigned paper with a valid text embedding, without time/sample selection.
    for p in parts():
        meta=pq.read_table(p,columns=['row_id','source']).to_pandas()
        expected.update(meta.source.value_counts().add(pd.Series(expected,dtype='int64'),fill_value=0).astype(int).to_dict())
        total+=len(meta)
        label_file=RUN/'paper_assignments'/p.name
        if not label_file.exists():
            continue
        labels=pd.read_parquet(label_file)
        frame=meta.merge(labels,on='row_id',how='left',validate='one_to_one')
        emb=np.load(RUN/'embeddings'/(p.stem+'.npy'),mmap_mode='r')
        valid=frame.source.eq('paper') & frame.topic_id.fillna(-1).ge(0) & (np.linalg.norm(emb,axis=1)>1e-12)
        ids=frame.topic_id[valid].to_numpy(dtype=int)
        # sparse membership aggregation avoids a Python loop over 4.8M vectors.
        from scipy import sparse
        membership=sparse.csr_matrix((np.ones(len(ids)),(ids,np.arange(len(ids)))),shape=(K,len(ids)))
        sums+=membership @ np.asarray(emb[valid])
        counts+=np.bincount(ids,minlength=K)
    means=sums/np.maximum(counts[:,None],1)
    norms=np.linalg.norm(means,axis=1,keepdims=True)
    centers=(means/np.maximum(norms,1e-12)).astype(np.float32)
    np.save(RUN/'topic_centroid_sums.npy',sums)
    np.save(RUN/'topic_centroid_counts.npy',counts)
    np.save(RUN/'topic_centroids.npy',centers)
    active=np.flatnonzero(counts>0)
    source_stats=[]; checks=[]; sample_frames=[]
    for p in parts():
        meta=pq.read_table(p,columns=['row_id','doc_id','source','date','title','title_only','retracted','template_record','usable']).to_pandas()
        emb=np.load(RUN/'embeddings'/(p.stem+'.npy'),mmap_mode='r')
        f=meta.copy(); f['topic_id']=-1; f['assignment_status']='unusable_text'
        f['nmf_relative_top1']=np.nan;f['nmf_relative_margin']=np.nan
        for rank in range(1,4):
            f[f'topic_{rank}_id']=-1;f[f'topic_{rank}_cosine']=np.nan
        label_file=RUN/'paper_assignments'/p.name
        if label_file.exists():
            lab=pd.read_parquet(label_file).set_index('row_id')
            mask=f.source.eq('paper')
            for col in ['topic_id','assignment_status','nmf_relative_top1','nmf_relative_margin']:
                f.loc[mask,col]=f.loc[mask,'row_id'].map(lab[col]).to_numpy()
        transfer=f.source.ne('paper')
        valid=transfer.to_numpy() & (np.linalg.norm(emb,axis=1)>1e-12)
        if valid.any():
            ids,scores=nearest_centroid_assign(np.asarray(emb[valid]),centers,active,top_n=3)
            for j in range(3):
                f.loc[valid,f'topic_{j+1}_id']=ids[:,j]
                f.loc[valid,f'topic_{j+1}_cosine']=scores[:,j]
            f.loc[valid,'topic_id']=ids[:,0]
            f.loc[valid,'assignment_status']='paper_centroid_cosine_candidate'
            checks.append(bool((scores[:,:-1]>=scores[:,1:]).all()))
            # Independent dot-product check for every transfer record, not just a sample.
            for lo in range(0,len(ids),4096):
                vectors=np.asarray(emb[np.flatnonzero(valid)[lo:lo+4096]],dtype=np.float32)
                vectors/=np.linalg.norm(vectors,axis=1,keepdims=True)
                actual=vectors@centers[active].T
                expect=active[actual.argmax(1)]
                if not np.array_equal(expect,ids[lo:lo+4096,0]):
                    # Float32 renormalization can move numerical ties; verify score tolerance.
                    assigned=ids[lo:lo+4096,0]
                    got=(vectors*centers[assigned]).sum(1)
                    if not np.allclose(got,actual.max(1),atol=2e-6,rtol=0):
                        raise ValueError('Not a cosine maximum')
        f['topic_id']=f.topic_id.astype('int32')
        f['category_id']=[f'F{i+1:04d}' if i>=0 else '' for i in f.topic_id]
        f['top1_top2_margin']=f.topic_1_cosine-f.topic_2_cosine
        f['needs_review']=True
        f['assignment_method']=np.where(transfer,'BGE-M3 full-paper-centroid cosine','fixed-H-l2-contribution-v2')
        f.to_parquet(out/p.name,index=False)
        for source,g in f.groupby('source'):
            source_stats.append({'source':source,'input_records':len(g),'assigned_records':int(g.topic_id.ge(0).sum()),'unassigned_records':int(g.topic_id.lt(0).sum())})
        # A reproducible per-part random review sample, retaining raw source IDs.
        sample_frames.append(f.sample(min(30,len(f)),random_state=17))
        print('FINALIZE',p.stem,flush=True)
    stats=pd.DataFrame(source_stats).groupby('source',as_index=False).sum()
    stats.to_csv(RUN/'coverage.csv',index=False)
    con=duckdb.connect();con.execute('SET threads=4')
    actual=con.sql(f"SELECT count(*),count(DISTINCT row_id),count(DISTINCT doc_id),min(row_id),max(row_id) FROM read_parquet('{out}/*.parquet')").fetchone()
    if actual!=(total,total,total,0,total-1):
        raise ValueError(('Row identity coverage mismatch',actual,total))
    for filename,field,want in [('PREPARE_COMPLETE.json','paper_count',expected['paper']),
                                ('INFERENCE_COMPLETE.json','papers',expected['paper']),
                                ('ENCODING_COMPLETE.json','documents',total)]:
        stage=json.loads((RUN/filename).read_text())
        if stage.get(field)!=want:
            raise ValueError(('Stage population mismatch',filename,stage.get(field),want))
    if not np.isfinite(centers).all() or not np.allclose(np.linalg.norm(centers[active],axis=1),1,atol=1e-6):
        raise ValueError('Invalid normalized topic centers')
    if not all(checks):
        raise ValueError('Top3 cosine order failed')
    dump(RUN/'ASSIGNMENTS_MANIFEST.json',{'files':{p.name:sha(out/p.name) for p in parts()},'records':total})
    catalog=pd.read_csv(RUN/'topic_catalog.csv')
    catalog['centroid_papers']=counts
    grouped=con.sql(f"SELECT topic_id,source,count(*) n FROM read_parquet('{out}/*.parquet') WHERE topic_id>=0 GROUP BY ALL").df()
    for source in ['patent','policy']:
        lookup=grouped[grouped.source.eq(source)].set_index('topic_id').n
        catalog[source+'_documents']=catalog.topic_id.map(lookup).fillna(0).astype(int)
    catalog.to_csv(RUN/'topic_catalog.csv',index=False)
    quality=con.sql(f"""SELECT topic_id,count(*) paper_documents,
        median(nmf_relative_top1) median_relative_contribution,
        median(nmf_relative_margin) median_relative_margin,
        avg(CASE WHEN nmf_relative_margin<0.05 THEN 1.0 ELSE 0.0 END) margin_below_005_fraction
        FROM read_parquet('{out}/*.parquet') WHERE source='paper' AND topic_id>=0 GROUP BY ALL ORDER BY topic_id""").df()
    quality.to_csv(RUN/'topic_assignment_quality.csv',index=False)
    similarity=centers[active]@centers[active].T
    np.fill_diagonal(similarity,-np.inf)
    nearest=similarity.max(1)
    sizes=catalog.paper_documents.to_numpy() if 'paper_documents' in catalog else counts
    diagnostics={'active_topics':len(active),'largest_topic_papers':int(sizes.max()),
        'largest_topic_share':float(sizes.max()/max(sizes.sum(),1)),
        'centroid_nearest_cosine_median':float(np.median(nearest)),
        'centroid_nearest_cosine_max':float(nearest.max()),
        'topics_with_nearest_cosine_over_095':int((nearest>.95).sum()),
        'semantic_accuracy_measured':False,'note':'Geometric overlap and label margins are diagnostics, not semantic accuracy or calibrated probabilities.'}
    dump(RUN/'QUALITY_DIAGNOSTICS.json',diagnostics)
    review=pd.concat(sample_frames,ignore_index=True)
    review.to_parquet(RUN/'review_samples.parquet',index=False)
    summary={'population_records':total,'papers':int(expected['paper']),'patents':int(expected['patent']),'policies':int(expected['policy']),
        'requested_topics':K,'active_centroids':len(active),'centroid_papers':int(counts.sum()),
        'assigned_records':int(stats.assigned_records.sum()),'unassigned_records':int(stats.unassigned_records.sum()),
        'full_training':True,'full_inference':True,'full_transfer':True,'embedding':'BAAI/bge-m3',
        'centroid_rule':'arithmetic mean of all assigned paper embeddings with usable text, then L2 normalization',
        'transfer_rule':'cosine Top1; also retain Top3 and margin; all mappings require semantic review',
        'input_corpus':str(CORPUS),'model_sha256':sha(RUN/'selected_nmf.joblib'),'centroids_sha256':sha(RUN/'topic_centroids.npy'),
        'assignments_manifest_sha256':sha(RUN/'ASSIGNMENTS_MANIFEST.json'),
        'training_used_all_years':True,'not_independent_temporal_validation':True,'semantic_accuracy_measured':False}
    dump(RUN/'SUMMARY.json',summary)
    (RUN/'REPORT.md').write_text(f"# 全量论文NMF与专利／政策匹配\n\n"
        f"覆盖{total:,}条冻结记录：论文{expected['paper']:,}篇、专利{expected['patent']:,}条、政策{expected['policy']:,}条。"
        f"已分配{summary['assigned_records']:,}条，未分配{summary['unassigned_records']:,}条；具体原因保留在逐条分类中。\n\n"
        f"500组件NMF在全部有效关键词论文上训练5轮，全部论文用固定H统一推断。"
        f"{int(counts.sum()):,}篇已归类且向量有效的论文参与{len(active)}个主题中心，先算术平均再L2归一化。"
        "全部可用专利与政策在同一BGE-M3空间取余弦最高的主题作为候选，同时保留Top3。\n\n"
        "全量是全部冻结记录，不是最新滚动采集记录或PDF全文；缺有效关键词、缺文本的记录不强行归类。"
        "新主题编号F0001–F0500，不继承旧主题语义审核与成熟度等级。模型使用全部年份，历史趋势仅作回溯描述。"
        "尚未测得人工语义准确率；几何诊断见QUALITY_DIAGNOSTICS.json。\n")
    dump(RUN/'VALIDATION.json',{'passed':True,'exact_identity_coverage':True,'transfer_argmax_checked_all':True,'top3_order':all(checks),
        'centroids_unit_norm':bool(np.allclose(np.linalg.norm(centers[active],axis=1),1,atol=1e-6)),
        'source_counts':stats.to_dict('records')})
    dump(RUN/'COMPLETE.json',{'summary_sha256':sha(RUN/'SUMMARY.json'),'validation_sha256':sha(RUN/'VALIDATION.json')})
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    with threadpool_limits(4):
        main()
