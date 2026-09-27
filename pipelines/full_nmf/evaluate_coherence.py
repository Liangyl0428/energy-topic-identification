"""Matched-pair keyword coherence on the historical 12,000-document cohort.

Uses the same binary keyword incidence and document-level co-occurrence for
every method. This is in-sample descriptive coherence, not held-out accuracy.
"""
from evaluate_topics import *


def results_report(folder):
    geometry=pd.read_csv(folder/'geometry.csv')
    silhouette=pd.read_csv(folder/'silhouette.csv')
    coherence=pd.read_csv(folder/'keyword_coherence.csv')
    result='# 对比结果摘要\n\n以下是统一文献口径的回溯诊断，不是人工准确率排名。CH、DBI受主题数和簇形状影响，不能跨不同文献集合直接比较。\n'
    for cohort,title in [('full_papers_common','全量共同论文'),('historical_142k_common','历史样本共同论文')]:
        result+='\n## '+title+'\n'
        for space in SPACES:
            g=geometry[geometry.cohort.eq(cohort)&geometry.space.eq(space)]
            s=silhouette[silhouette.cohort.eq(cohort)&silhouette.space.eq(space)].groupby('method').cosine_silhouette.agg(['mean','min','max'])
            result+='\n### '+space+'\n\n|方法|文献数|有效主题|CH ↑|DBI ↓|簇内余弦 ↑|轮廓均值 ↑|3种子范围|\n|---|---:|---:|---:|---:|---:|---:|---|\n'
            for r in g.itertuples():
                v=s.loc[r.method]
                result+=f'|{r.method}|{r.documents:,}|{r.active_topics}|{r.calinski_harabasz:.2f}|{r.davies_bouldin:.4f}|{r.mean_cosine_to_own_center:.4f}|{v["mean"]:.4f}|{v["min"]:.4f}–{v["max"]:.4f}|\n'
            for metric,ascending in [('calinski_harabasz',False),('davies_bouldin',True),('mean_cosine_to_own_center',False)]:
                order=g.sort_values(metric,ascending=ascending).method.tolist()
                result+=f'\n当前全量模型的 {metric} 在本组 {len(order)} 个结果中按该单项指标排序为 {order.index(CURRENT)+1}；这不是综合语义排名。\n'
    result+='\n## 历史验证集：成对关键词对比\n\n|历史方法|共同文献|当前 NPMI|历史 NPMI|当前词多样性|历史词多样性|\n|---|---:|---:|---:|---:|---:|\n'
    for name,g in coherence.groupby('comparison',sort=True):
        a=g[g.method.eq(CURRENT)].iloc[0];b=g[g.method.eq(name)].iloc[0]
        result+=f'|{name}|{a.documents:,}|{a.npmi_macro:.4f}|{b.npmi_macro:.4f}|{a.topic_keyword_diversity:.4f}|{b.topic_keyword_diversity:.4f}|\n'
    result+='\n上述各行仅可比较同行的两个模型，不同方法的共同文献集合可能不同，不能按历史NPMI列横向排总榜。关键词指标基于12,000篇历史参考语料，不是全量NPMI。\n\n其他验证方法的同文献几何指标见geometry.csv中的validation_pair/行；完整覆盖率、输入溯源及限制见REPORT.md和PROTOCOL.json。\n'
    result+='\n历史全量类别原本在多来源记录上构造，本次NMF仅在论文关键词上建模。这里比较已交付结果，不是控制其他条件不变的数据规模消融。表内有效主题数是在共同论文上的实际数量，可能小于方法名称中的名义类别数。全量覆盖完成不自动意味着主题分离度优于旧版。\n'
    (folder/'RESULTS.md').write_text(result)


def keyword_quality(x,y,cooc,df,reference_n,top_n=10):
    _,y=np.unique(y,return_inverse=True);k=int(y.max())+1
    membership=sparse.csr_matrix((np.ones(len(y)),(y,np.arange(len(y)))),shape=(k,len(y)))
    counts=(membership@x).tocsr();all_words=[];scores=[];weights=[];eligible=0
    for j in range(k):
        row=counts.getrow(j);words=row.indices[np.lexsort((row.indices,-row.data))[:top_n]]
        all_words.extend(words.tolist())
        if len(words)<2:continue
        eligible+=1
        a,b=np.triu_indices(len(words),1)
        i=words[a];h=words[b]
        joint=np.asarray(cooc[i,h]).ravel()/reference_n
        product=df[i]*df[h]/reference_n**2
        values=np.full(len(joint),-1.)
        good=(joint>0)&(joint<1)
        values[good]=np.log(joint[good]/product[good])/(-np.log(joint[good]))
        values[joint>=1]=0.  # Both words occur in every document: no information.
        scores.append(float(values.mean()));weights.append(int((y==j).sum()))
    return {'topic_count':k,'topics_with_at_least_two_keywords':eligible,
        'top_keyword_slots':len(all_words),'top_keyword_unique':len(set(all_words)),
        'topic_keyword_diversity':len(set(all_words))/len(all_words) if all_words else None,
        'npmi_macro':float(np.mean(scores)) if scores else None,
        'npmi_document_weighted':float(np.average(scores,weights=weights)) if scores else None}


def main():
    complete=OUT/'COMPLETE.json'
    old=json.loads(complete.read_text())
    for name,digest in old['files'].items():
        if sha(OUT/name)!=digest:raise ValueError('Base evaluation changed')
    inputs=json.loads((OUT/'INPUTS.json').read_text())
    def track(p):inputs[str(p.relative_to(ROOT))]=sha(p)
    vp=ROOT/'aaaa/data/validation.parquet';vf=pd.read_parquet(vp,columns=['work_id']);track(vp)
    con=duckdb.connect();con.execute('SET threads=2');con.register('wanted',vf)
    mapped=con.sql(f"SELECT replace(a.doc_id,'paper:','') work_id,a.row_id,a.topic_id FROM read_parquet('{RUN}/assignments/*.parquet') a JOIN wanted w ON a.doc_id='paper:'||w.work_id WHERE a.source='paper'").df()
    f=vf.merge(mapped,on='work_id',how='left',validate='one_to_one')
    if f.row_id.isna().any():raise ValueError('Missing validation IDs')
    ids=f.row_id.to_numpy(dtype=np.int64);ys={CURRENT:f.topic_id.to_numpy(dtype=np.int32)}
    for name,rel in FULL.items():
        p=ROOT/'jjjj'/rel;track(p);ys[name]=np.load(p,mmap_mode='r')[ids]
    def table(p,col):
        track(p);t=pd.read_parquet(p,columns=['work_id',col])
        if not t.work_id.is_unique:raise ValueError('Duplicate method IDs')
        return t.set_index('work_id').loc[vf.work_id,col].to_numpy(dtype=np.int32)
    for version,folder in [('historical_sample_v020','nmf500'),('historical_sample_v021','nmf500_v021')]:
        ys[version]=table(ROOT/f'energy-topic-hotspots/outputs/{folder}/paper_assignments.parquet','topic_id')
    for family in ['vector_bertopic','bge_m3','openalex_keywords_nmf']:
        for p in sorted((ROOT/'aaaa'/family/'results').glob('*/validation_assignments.parquet')):
            ys[family+'/'+p.parent.name]=table(p,'cluster_id')
    for p in sorted((REPO/'pipelines/keyword_nmf/results/candidates').glob('k*/validation_labels.npy')):
        track(p);ys['keyword_nmf_candidate/'+p.parent.name]=np.load(p)
    xp=ROOT/'aaaa/openalex_keywords_nmf/models/validation_binary_counts.npz';track(xp)
    x=sparse.load_npz(xp).astype(np.float64).tocsr();x.eliminate_zeros();x.data[:]=1
    if x.shape[0]!=len(vf):raise ValueError('Keyword/document alignment mismatch')
    df=np.asarray(x.sum(0)).ravel();cooc=(x.T@x).tocsr()
    rows=[]
    for name,y in ys.items():
        if name==CURRENT:continue
        good=(y>=0)&(ys[CURRENT]>=0)
        for method,lab in [(CURRENT,ys[CURRENT]),(name,y)]:
            rows.append({'comparison':name,'method':method,'documents':int(good.sum()),
                'common_ids_sha256':identity_hash(ids[good]),
                **keyword_quality(x[good],lab[good],cooc,df,len(vf))})
    pd.DataFrame(rows).to_csv(OUT/'keyword_coherence.csv',index=False)
    results_report(OUT)
    protocol=json.loads((OUT/'PROTOCOL.json').read_text())
    protocol['keyword_coherence']={'reference_documents':len(vf),'vocabulary_size':x.shape[1],
        'top_n':10,'top_words':'Within-topic document frequency, descending; vocabulary index breaks ties.',
        'npmi':'Document-level co-occurrence in the same frozen historical 12000 papers for ALL methods. Zero co-occurrence = -1; universal pair = 0.',
        'cohorts':'Each method and current NMF on identical jointly assigned validation IDs; vectors not required for keyword metrics.',
        'limitations':'In-sample descriptive keyword consistency; same OpenAlex vocabulary can favor keyword-based methods. Not held-out or expert semantic accuracy. No sliding-window text coherence claim.'}
    protocol['limitations']=[s for s in protocol['limitations'] if not s.startswith('Geometry and size')]
    protocol['limitations'].append('Keyword NPMI is reported separately on the historical 12000-paper reference, not on all 4.8M papers.')
    protocol['limitations'].append('Legacy full clusters were built on multiple sources; current NMF on paper keywords. This compares delivered outcomes, not a controlled training-size ablation. Active topics are counted on each common paper cohort, not inferred from nominal K.')
    dump(OUT/'PROTOCOL.json',protocol);track(Path(__file__));track(REPO/'pipelines/full_nmf/evaluate_topics.py')
    dump(OUT/'INPUTS.json',inputs)
    report=OUT/'REPORT.md';text=report.read_text()
    text=text.replace('- Geometry and size diversity are not keyword NPMI/coherence or expert interpretability.','- 几何指标不等同于语义解释性；关键词 NPMI 的独立口径见下。')
    text+='\n## 关键词一致性与多样性\n\nkeyword_coherence.csv 在相同历史12,000篇参考文献、相同二值OpenAlex关键词上计算每个方法与本次模型的成对比较。每簇按文档频次选前10词，报告文档共现NPMI（宏平均和按簇文档数加权）及去重主题词/词槽比。缺少至少2个词的簇不计入NPMI，并报告有效簇数。此指标不是全量480万篇NPMI，也不是独立验证；使用OpenAlex词表可能有利于关键词方法。\n'
    report.write_text(text)
    dump(complete,{'passed':True,'classification_summary_sha256':sha(RUN/'SUMMARY.json'),
        'files':{p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name not in {'COMPLETE.json','runner.log'}}})
    print('KEYWORD COHERENCE COMPLETE',len(rows),'paired rows',flush=True)


if __name__=='__main__':
    with threadpool_limits(limits=2):main()
