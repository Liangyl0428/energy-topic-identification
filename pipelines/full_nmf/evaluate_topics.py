"""Retrospective matched-document comparison; never an accuracy benchmark.

Full-corpus geometry is streamed, silhouette is explicitly sampled. All methods
use identical documents within a comparison and identical normalized vectors.
Historical labels are evaluated as delivered, never silently corrected/refit.
"""
from common import *
import argparse
import itertools
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import duckdb
from scipy import sparse
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score
from sklearn.metrics.pairwise import cosine_distances
from threadpoolctl import threadpool_limits

OUT = RUN/'topic_evaluation'
FULL = {
    'legacy_486_parent':'bertopic486_hierarchical_refined_20260925/results/final_parent_labels.npy',
    'legacy_500_raw':'bertopic500_all_sources_20260925/results/raw_labels.npy',
    'legacy_750_final':'bertopic750_flat_refined_20260925/results/final_labels.npy',
    'legacy_990_merged':'bertopic1000_semantic_merged_20260925/results/final_labels.npy',
    'legacy_1000_raw':'bertopic1000_all_sources_20260925/results/raw_labels.npy',
}
SPACES = ['bge_m3_1024','legacy_minilm_pca64']
CURRENT = 'full_nmf500_current'


def identity_hash(ids):
    return hashlib.sha256(np.asarray(ids,dtype='<i8').tobytes()).hexdigest()


def unit(x):
    x=np.asarray(x,dtype=np.float64)
    norms=np.linalg.norm(x,axis=1)
    if not np.isfinite(x).all() or (norms<=1e-12).any():
        raise ValueError('Geometry requires finite, nonzero vectors')
    return x/norms[:,None]


def balance(y):
    _,counts=np.unique(y,return_counts=True)
    p=counts/counts.sum();s=np.sort(counts);k=len(s)
    return {'active_topics':k,'largest_topic_share':float(p.max()),
        'effective_topics':float(np.exp(-(p*np.log(p)).sum())),
        'size_gini':float(2*np.dot(np.arange(1,k+1),s)/(k*s.sum())-(k+1)/k)}


class Geometry:
    def __init__(self,k,d):
        self.count=np.zeros(k,np.int64);self.sums=np.zeros((k,d));self.ss=0.
        self.scatter=np.zeros(k)

    def add(self,x,y):
        if len(y)==0:return
        m=sparse.csr_matrix((np.ones(len(y)),(y,np.arange(len(y)))),shape=(len(self.count),len(y)))
        self.sums+=m@x;self.count+=np.bincount(y,minlength=len(self.count))
        self.ss+=float(np.square(x).sum())

    def centers(self):return self.sums/np.maximum(self.count[:,None],1)

    def add_scatter(self,x,y):
        self.scatter+=np.bincount(y,weights=np.linalg.norm(x-self.centers()[y],axis=1),minlength=len(self.count))

    def finish(self):
        active=self.count>0;c=self.count[active];means=self.centers()[active]
        n=int(c.sum());k=len(c)
        if k<2 or n<=k:raise ValueError('Geometry needs 2 <= active clusters < documents')
        within=max(0.,self.ss-float((c[:,None]*means**2).sum()))
        total=self.ss-float(np.square(self.sums.sum(0)).sum()/n)
        ch=((total-within)/(k-1))/(within/(n-k)) if within>0 else None
        norms=np.linalg.norm(means,axis=1)
        pair2=np.maximum(0.,np.square(means).sum(1)[:,None]+np.square(means).sum(1)[None,:]-2*means@means.T)
        distances=np.sqrt(pair2);np.fill_diagonal(distances,np.inf)
        scatter=self.scatter[active]/c
        if np.allclose(scatter,0) or np.allclose(np.where(np.isinf(distances),0,distances),0):db=0.
        else:
            distances[distances==0]=np.inf
            db=float(((scatter[:,None]+scatter[None,:])/distances).max(1).mean())
        centers=means/np.maximum(norms[:,None],1e-12)
        cosine=centers@centers.T;np.fill_diagonal(cosine,-np.inf)
        return {'documents':n,'active_topics':k,'calinski_harabasz':None if ch is None else float(ch),
            'davies_bouldin':db,'mean_cosine_to_own_center':float(np.average(norms,weights=c)),
            'nearest_center_cosine_median':float(np.median(cosine.max(1))),
            'within_squared_distance_mean':within/n}


def dense_geometry(x,y):
    _,y=np.unique(y,return_inverse=True);x=unit(x)
    g=Geometry(int(y.max())+1,x.shape[1]);g.add(x,y);g.add_scatter(x,y)
    return {**g.finish(),**balance(y)}


def sampled_silhouette(x,ys,ids,seeds=(20260927,20260928,20260929),limit=3000):
    rows=[]
    for seed in seeds:
        take=np.sort(np.random.default_rng(seed).choice(len(ids),min(limit,len(ids)),replace=False))
        d=cosine_distances(unit(x[take]));np.fill_diagonal(d,0)
        for name,y in ys.items():
            labels=y[take];k=len(np.unique(labels))
            value=float(silhouette_score(d,labels,metric='precomputed')) if 1<k<len(labels) else None
            rows.append({'method':name,'seed':seed,'sample_n':len(take),
                'sample_ids_sha256':identity_hash(ids[take]),'cosine_silhouette':value})
    return rows


def agreement(a,b):
    return {'ARI':float(adjusted_rand_score(a,b)),
        'NMI':float(normalized_mutual_info_score(a,b))}


def main():
    OUT.mkdir(exist_ok=True)
    summary=json.loads((RUN/'SUMMARY.json').read_text());n=summary['population_records']
    manifest=json.loads((RUN/'ASSIGNMENTS_MANIFEST.json').read_text())
    inputs={};coverage=[];geometry=[];silhouettes=[];agreements=[];cohorts=[]
    def track(p):inputs[str(p.relative_to(ROOT))]=sha(p)
    track(RUN/'ASSIGNMENTS_MANIFEST.json');track(RUN/'SUMMARY.json')
    current=np.full(n,-1,np.int32);paper=np.zeros(n,bool);valid=np.zeros(n,bool)
    legacy_path=ROOT/'jjjj/bertopic500_all_sources_20260925/models/reduced.npy'
    legacy=np.load(legacy_path,mmap_mode='r');track(legacy_path)
    labels={CURRENT:current};shards=[];offset=0
    for p in parts():
        ap=RUN/'assignments'/p.name
        if sha(ap)!=manifest['files'][p.name]:raise ValueError('Assignment changed: '+p.name)
        f=pq.read_table(ap,columns=['row_id','source','topic_id']).to_pandas()
        ids=f.row_id.to_numpy()
        if not np.array_equal(ids,np.arange(offset,offset+len(f))):raise ValueError('Frozen row order mismatch')
        audit=json.loads((RUN/'embeddings'/(p.stem+'.json')).read_text())
        if sha(p)!=audit['input_sha256']:raise ValueError('Embedding corpus changed')
        ep=RUN/'embeddings'/(p.stem+'.npy');x=np.load(ep,mmap_mode='r');track(ep)
        if inputs[str(ep.relative_to(ROOT))]!=audit['embedding_sha256'] or identity_hash(ids)!=audit['row_ids_sha256']:
            raise ValueError('Embedding checksum or identity mismatch')
        if x.shape!=(len(f),1024) or not np.isfinite(x).all():raise ValueError('Invalid embeddings')
        if legacy[ids].shape!=(len(f),64) or not np.isfinite(legacy[ids]).all():raise ValueError('Invalid legacy vectors')
        current[ids]=f.topic_id;paper[ids]=f.source.eq('paper')
        valid[ids]=(np.linalg.norm(x,axis=1)>1e-12)&(np.linalg.norm(legacy[ids],axis=1)>1e-12)
        shards.append((offset,offset+len(f),ep));offset+=len(f)
    if offset!=n or paper.sum()!=summary['papers']:raise ValueError('Incomplete census')
    for name,rel in FULL.items():
        p=ROOT/'jjjj'/rel;track(p);y=np.load(p,mmap_mode='r')
        if y.shape!=(n,) or not np.issubdtype(y.dtype,np.integer):raise ValueError('Legacy labels not aligned')
        labels[name]=y
    con=duckdb.connect();con.execute('SET threads=2')
    id_cache={}
    # Query only requested IDs, rather than allocating 4.8M Python strings.
    def align(p,col):
        f=pd.read_parquet(p,columns=['work_id',col]);track(p)
        if not f.work_id.is_unique or f.work_id.isna().any():raise ValueError('Duplicate/missing work IDs')
        if all(w in id_cache for w in f.work_id):
            return np.array([id_cache[w] for w in f.work_id],dtype=np.int64),f[col].to_numpy(dtype=np.int32)
        con.register('wanted',f[['work_id']])
        mapped=con.sql(f"SELECT replace(c.doc_id,'paper:','') work_id,c.row_id FROM read_parquet('{CORPUS}/*.parquet') c JOIN wanted w ON c.doc_id='paper:'||w.work_id WHERE c.source='paper'").df()
        g=f.merge(mapped,on='work_id',how='left',validate='one_to_one')
        if g.row_id.isna().any():raise ValueError('Historical documents missing from full corpus')
        ids=g.row_id.to_numpy(dtype=np.int64);y=g[col].to_numpy(dtype=np.int32)
        id_cache.update(zip(g.work_id,ids))
        return ids,y
    historical={}
    for version,folder in [('historical_sample_v020','nmf500'),('historical_sample_v021','nmf500_v021')]:
        ids,y=align(ROOT/f'energy-topic-hotspots/outputs/{folder}/paper_assignments.parquet','topic_id')
        historical[version]=(ids,y)
    def vectors(ids,space):
        if space==SPACES[1]:return np.asarray(legacy[ids],dtype=np.float32)
        result=np.empty((len(ids),1024),np.float32)
        for lo,hi,ep in shards:
            m=(ids>=lo)&(ids<hi)
            if m.any():result[m]=np.load(ep,mmap_mode='r')[ids[m]-lo]
        return result
    def describe(name,base,ys):
        good=valid[base].copy()
        for method,y in ys.items():
            coverage.append({'cohort':name,'method':method,'population':len(base),
                'assigned':int((y>=0).sum()),'assigned_fraction':float((y>=0).mean()),
                'assigned_and_vectors_valid':int(((y>=0)&valid[base]).sum())})
            good&=y>=0
        ids=base[good]
        cohorts.append({'cohort':name,'population':len(base),'common_n':len(ids),
            'common_fraction':len(ids)/len(base),'common_ids_sha256':identity_hash(ids),'methods':list(ys)})
        return ids,{name:y[good] for name,y in ys.items()}
    base=np.flatnonzero(paper)
    full_ids,full_y=describe('full_papers_common',base,{name:y[base] for name,y in labels.items()})
    selected=np.zeros(n,bool);selected[full_ids]=True
    print('FULL COMMON',len(full_ids),flush=True)
    for space,d in zip(SPACES,[1024,64]):
        gs={name:Geometry(int(y.max())+1,d) for name,y in labels.items()}
        for pass_id in [1,2]:
            for lo,hi,ep in shards:
                ids=np.flatnonzero(selected[lo:hi])+lo
                if not len(ids):continue
                x=unit(np.load(ep,mmap_mode='r')[ids-lo] if space==SPACES[0] else legacy[ids])
                for name,y in labels.items():
                    if pass_id==1:gs[name].add(x,y[ids])
                    else:gs[name].add_scatter(x,y[ids])
            print('FULL GEOMETRY',space,'pass',pass_id,flush=True)
        for name,g in gs.items():geometry.append({'cohort':'full_papers_common','space':space,'method':name,**g.finish(),**balance(full_y[name])})
        # Read only sampled vectors, but select samples from the entire common census.
        for seed in [20260927,20260928,20260929]:
            take=np.sort(np.random.default_rng(seed).choice(len(full_ids),min(3000,len(full_ids)),replace=False))
            sid=full_ids[take];sx=vectors(sid,space)
            for row in sampled_silhouette(sx,{k:v[take] for k,v in full_y.items()},sid,seeds=(seed,)):
                silhouettes.append({'cohort':'full_papers_common','space':space,**row})
        pd.DataFrame(geometry).to_csv(OUT/'geometry.csv',index=False)
    for a,b in itertools.combinations(full_y,2):
        agreements.append({'cohort':'full_papers_common','method_a':a,'method_b':b,'documents':len(full_ids),**agreement(full_y[a],full_y[b])})
    # Both historical sampled releases are compared on their common delivered IDs.
    base=np.intersect1d(*[v[0] for v in historical.values()]);ys={k:y[base] for k,y in labels.items()}
    for name,(ids,y) in historical.items():ys[name]=pd.Series(y,index=ids).loc[base].to_numpy()
    ids,ys=describe('historical_142k_common',base,ys)
    for space in SPACES:
        x=vectors(ids,space)
        for name,y in ys.items():geometry.append({'cohort':'historical_142k_common','space':space,'method':name,**dense_geometry(x,y)})
        silhouettes.extend({'cohort':'historical_142k_common','space':space,**r} for r in sampled_silhouette(x,ys,ids))
    for name,y in ys.items():
        if name!=CURRENT:agreements.append({'cohort':'historical_142k_common','method_a':CURRENT,'method_b':name,'documents':len(ids),**agreement(ys[CURRENT],y)})
    # Validation is historical, NOT a holdout for the full all-years model.
    vp=ROOT/'aaaa/data/validation.parquet';vf=pd.read_parquet(vp,columns=['work_id']);track(vp)
    methods={}
    for family in ['vector_bertopic','bge_m3','openalex_keywords_nmf']:
        for p in sorted((ROOT/'aaaa'/family/'results').glob('*/validation_assignments.parquet')):
            methods[family+'/'+p.parent.name]=align(p,'cluster_id')
    # Candidate label order follows DataBundle.metadata['validation'] in run_pipeline.py.
    # Obtain validation row IDs from a saved table via work_id, never its physical order.
    p=next((ROOT/'aaaa/bge_m3/results').glob('*/validation_assignments.parquet'))
    tab=pd.read_parquet(p,columns=['work_id']);rid,_=align(p,'cluster_id')
    base=pd.Series(rid,index=tab.work_id).loc[vf.work_id].to_numpy()
    for p in sorted((REPO/'pipelines/keyword_nmf/results/candidates').glob('k*/validation_labels.npy')):
        track(p);y=np.load(p)
        if y.shape!=(len(base),):raise ValueError('Candidate validation size mismatch')
        methods['keyword_nmf_candidate/'+p.parent.name]=(base,y)
    ys={name:y[base] for name,y in labels.items()}
    for name,(hid,hy) in historical.items():ys[name]=pd.Series(hy,index=hid).loc[base].to_numpy()
    for name,(mid,my) in methods.items():
        if set(mid)!=set(base):raise ValueError('Methods have different validation documents: '+name)
        ys[name]=pd.Series(my,index=mid).loc[base].to_numpy()
    strict_ids,strict_y=describe('historical_validation_12000',base,ys)
    print('VALIDATION',len(ys),'methods; strict common',len(strict_ids),flush=True)
    # Pairwise cohorts avoid the severe selection bias of intersecting all noise-heavy methods.
    for space in SPACES:
        x=vectors(base,space)
        for name,y in ys.items():
            if name==CURRENT:continue
            good=valid[base]&(ys[CURRENT]>=0)&(y>=0);ids=base[good]
            cohort='validation_pair/'+name
            pair={CURRENT:ys[CURRENT][good],name:y[good]}
            if space==SPACES[0]:
                cohorts.append({'cohort':cohort,'population':len(base),'common_n':len(ids),'common_fraction':len(ids)/len(base),'common_ids_sha256':identity_hash(ids),'methods':list(pair)})
                agreements.append({'cohort':cohort,'method_a':CURRENT,'method_b':name,'documents':len(ids),**agreement(*pair.values())})
            for method,lab in pair.items():geometry.append({'cohort':cohort,'space':space,'method':method,**dense_geometry(x[good],lab)})
            silhouettes.extend({'cohort':cohort,'space':space,**r} for r in sampled_silhouette(x[good],pair,ids,seeds=(20260927,),limit=2000))
        # Strict common is secondary, labelled explicitly, never the headline ranking.
        good=np.isin(base,strict_ids)
        for name,y in strict_y.items():geometry.append({'cohort':'validation_strict_intersection_secondary','space':space,'method':name,**dense_geometry(x[good],y)})
        print('VALIDATION COMPLETE',space,flush=True)
    for name,rows in [('coverage',coverage),('geometry',geometry),('silhouette',silhouettes),('agreement',agreements)]:
        pd.DataFrame(rows).to_csv(OUT/(name+'.csv'),index=False)
    dump(OUT/'COHORTS.json',cohorts);dump(OUT/'INPUTS.json',inputs)
    protocol={'classification_summary_sha256':sha(RUN/'SUMMARY.json'),'spaces':SPACES,
        'full_methods':list(labels),'validation_methods':list(ys),'full_common_papers':len(full_ids),
        'full_centroid_geometry':'Exact full-common-paper CH, DBI and normalized-vector cohesion; two streamed passes.',
        'silhouette':'Cosine; same IDs per comparison. Full and 142k: 3000 rows x 3 seeds; validation pairs: 2000 rows x 1 seed.',
        'legacy_alignment':'Legacy full arrays index frozen row_id in the shared corpus; historical tables joined by unique work_id.',
        'no_refit':True,'semantic_accuracy_measured':False,'independent_holdout':False,
        'limitations':['All-year full training includes historical validation documents; retrospective diagnostics only.',
            'BGE and legacy PCA are separate robustness views. Legacy clusters were optimized in the legacy space.',
            'Matched-pair validation populations differ; do not rank absolute scores across pairs.',
            'Strict all-method intersection is strongly selected by noise exclusions; secondary only.',
            'ARI/NMI measure agreement, not correctness; cluster IDs do not require manual matching.',
            'No expert gold labels: no accuracy/F1 claim and no patent/policy semantic precision claim.',
            'Geometry and size diversity are not keyword NPMI/coherence or expert interpretability.',
            'No new model refits or model-seed stability experiments in this comparison.']}
    dump(OUT/'PROTOCOL.json',protocol)
    main=pd.DataFrame(geometry);main=main[main.cohort.eq('full_papers_common')]
    report='# 主题识别效果：全量与历史方法统一口径对比\n\n'
    report+=f'全量论文共同有效集合：{len(full_ids):,} 篇。全量几何指标逐条计算；轮廓系数是明确标注的抽样诊断，不是抽样训练。\n\n'
    report+='## 全量共同论文结果\n\n'+main.to_csv(index=False)+'\n'
    report+='## 阅读口径\n\nCH、同簇余弦与轮廓系数越高通常越好，DBI越低通常越好；不同K、簇形状会影响指标，不能凭单一指标宣布语义最优。有效主题数、最大簇占比和Gini用于检查集中程度，不是越均匀越准确。\n\n'
    report+='coverage.csv保留各方法未分类情况；geometry.csv为同文献同空间几何指标；silhouette.csv含随机种子和抽样ID哈希；agreement.csv是ARI/NMI一致性而非准确率。COHORTS.json记录各比较的共同样本量和ID哈希，INPUTS.json记录输入文件哈希。\n\n'
    report+=f'历史验证集合共 {len(ys)} 个方法/版本；严格全方法交集仅 {len(strict_ids):,}/12,000 篇，因此主比较采用本次全量模型与每个历史方法的成对共同文献，不能横向混排不同成对子集。旧样本v020/v021作为历史结果名称保留，与本次重新发布的Git v0.2.0不是同一模型。\n\n'
    report+='## 局限\n\n'+'\n'.join('- '+s for s in protocol['limitations'])+'\n'
    (OUT/'REPORT.md').write_text(report)
    files={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name not in {'COMPLETE.json','runner.log'}}
    dump(OUT/'COMPLETE.json',{'passed':True,'classification_summary_sha256':sha(RUN/'SUMMARY.json'),'files':files})
    print('EVALUATION COMPLETE',flush=True)


if __name__=='__main__':
    with threadpool_limits(limits=2):main()
