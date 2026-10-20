"""Remove general disciplines, compare NMF K, and export multiple memberships.

Only this directory is written. Original data, models and previous experiments
are immutable inputs. See PROTOCOL.json for selection and evaluation boundaries.
"""
import os
os.environ.setdefault('OMP_NUM_THREADS', '4')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '4')
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import itertools
import json
import sys
import time
import joblib
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy import sparse
from sklearn.preprocessing import normalize
from sklearn.decomposition._nmf import _initialize_nmf
from sklearn.metrics import silhouette_samples, adjusted_rand_score
from threadpoolctl import threadpool_limits
from fast_nmf import GpuMiniBatchNMF

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
OLD = ROOT / 'work/nmf_keyword_control_20261019'
RUN = ROOT / 'energy-topic-identification/work/full_nmf500_20260926'
CORPUS = ROOT / 'jjjj/bertopic500_all_sources_20260925/data/corpus'
SEEDS = [17, 29, 43]
INITIAL_K = [200, 300, 500, 800, 1000]
THRESHOLDS = [.05, .10, .15, .20, .25, .30]
EPOCHS, BATCH, DEFAULT_THRESHOLD = 5, 4096, .10
BROAD = ['Materials science','Chemistry','Engineering','Computer science','Physics',
         'Mathematics','Biology','Medicine','Economics','Business','Geography','Geology',
         'Political science','Sociology','Psychology','History','Philosophy','Art',
         'Linguistics','Environmental science']

def stamp(): return datetime.now(timezone.utc).isoformat()
def read(p): return json.loads(Path(p).read_text())
def write(p, data):
    p = Path(p); q = p.with_suffix(p.suffix + '.tmp')
    q.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    q.replace(p)
def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20), b''): h.update(b)
    return h.hexdigest()
def progress(stage, **kw):
    d = {'time':stamp(), 'stage':stage, **kw}
    write(OUT/'PROGRESS.json', d); print(json.dumps(d, ensure_ascii=False), flush=True)
def clean(x, mask):
    x = x.copy(); x.data[mask[x.indices]] = 0; x.eliminate_zeros()
    return normalize(x, copy=False)
def nonzero(x): return np.diff(x.indptr) > 0
def relative_contributions(w, h):
    c = w * np.linalg.norm(h, axis=1)
    return np.divide(c, c.sum(1, keepdims=True), out=np.zeros_like(c), where=c.sum(1, keepdims=True)>0)
def infer(model, x):
    p = np.zeros((x.shape[0], model.n_components), np.float32)
    ix = np.flatnonzero(nonzero(x))
    for lo in range(0, len(ix), BATCH):
        rows=ix[lo:lo+BATCH]
        p[rows]=relative_contributions(model.transform(x[rows]), model.components_)
    return p
def assignments(p, threshold):
    if not 0 < threshold <= 1: raise ValueError('Threshold must be in (0,1]')
    return p >= threshold
def threshold_metrics(p, feature_valid):
    rows=[]
    for t in THRESHOLDS:
        a=assignments(p,t); n=a.sum(1); mass=np.where(a,p,0).sum(1)
        rows.append({'threshold':t,'documents':len(p),'feature_valid_documents':int(feature_valid.sum()),
            'assigned_documents':int((n>0).sum()),'coverage_all':float((n>0).mean()),
            'coverage_feature_valid':float((n[feature_valid]>0).mean()),
            'mean_topics_all':float(n.mean()),'mean_topics_feature_valid':float(n[feature_valid].mean()),
            'mean_topics_assigned':float(n[n>0].mean()) if (n>0).any() else 0.,
            'multiple_topic_fraction_all':float((n>=2).mean()),'p95_topics':float(np.quantile(n,.95)),
            'max_topics':int(n.max()),'mean_retained_contribution_feature_valid':float(mass[feature_valid].mean()),
            'no_features':int((~feature_valid).sum()),'below_threshold':int(((n==0)&feature_valid).sum())})
    return rows

def metric_context(emb, valid, evaluation=None):
    eligible=np.flatnonzero(valid & (np.linalg.norm(emb,axis=1)>1e-12))
    if evaluation is None:
        evaluation=np.sort(np.random.default_rng(2026101903).choice(eligible,min(10000,len(eligible)),replace=False))
    else: evaluation=evaluation[np.isin(evaluation,eligible)]
    e=emb[evaluation]
    d=np.clip(1-e@e.T,0,2);np.fill_diagonal(d,0)
    np.fill_diagonal(d,np.inf);neighbors=np.argpartition(d,10,axis=1)[:,:10]
    np.fill_diagonal(d,0)
    return {'emb':emb,'valid':valid,'evaluation':evaluation,'distances':d,'neighbors':neighbors}

def evaluate(p, context, k):
    labels=p.argmax(1);labels[p.sum(1)<=0]=-1
    ev=context['evaluation']; y=labels[ev]
    assert (y>=0).all()
    silhouettes=silhouette_samples(context['distances'],y,metric='precomputed')
    sizes=np.bincount(y,minlength=k)
    chance=float(np.sum(sizes*(sizes-1))/(len(y)*(len(y)-1)))
    agreement=float(np.mean(y[:,None]==y[context['neighbors']]))
    valid=context['valid']&(np.linalg.norm(context['emb'],axis=1)>1e-12)&(labels>=0)
    emb=context['emb'][valid]; lab=labels[valid]
    membership=sparse.csr_matrix((np.ones(len(lab)),(lab,np.arange(len(lab)))),shape=(k,len(lab)))
    sums=np.asarray(membership@emb); counts=np.bincount(lab,minlength=k)
    dot=(emb*sums[lab]).sum(1);many=counts[lab]>1
    loo=(dot[many]-1)/np.sqrt(np.maximum((sums*sums).sum(1)[lab[many]]+1-2*dot[many],1e-15))
    centers=normalize(sums[counts>0]);sim=centers@centers.T;np.fill_diagonal(sim,-np.inf)
    return {'cosine_silhouette':float(silhouettes.mean()),'negative_silhouette_fraction':float((silhouettes<0).mean()),
        'knn10_adjusted':(agreement-chance)/(1-chance),'knn10_agreement':agreement,
        'leave_one_out_cosine':float(loo.mean()),'nearest_center_cosine':float(sim.max(1).mean()),
        'active_topics':int((counts>0).sum()),'largest_topic_share':float(counts.max()/counts.sum()),
        'median_topic_size':float(np.median(counts[counts>0])),
        'topics_under_10_documents':int((counts<10).sum()),'evaluation_documents':len(y),
        'semantic_documents':len(lab)}, labels, silhouettes

def keyword_coherence(h, binary, vocab):
    ranks=np.argsort(-h,axis=1,kind='stable')[:,:10]
    terms=np.unique(ranks);x=binary[:,terms].astype(np.float32)
    cooc=(x.T@x).tocsr();df=cooc.diagonal();n=x.shape[0]
    index=np.full(h.shape[1],-1,dtype=int);index[terms]=np.arange(len(terms))
    scores=[]
    for top in ranks:
        ix=index[top]; vals=[]
        for a,b in itertools.combinations(ix,2):
            cnt=float(cooc[a,b])
            if cnt<=0:vals.append(-1.);continue
            joint=cnt/n
            vals.append(float(np.log(joint/((df[a]/n)*(df[b]/n)))/max(-np.log(joint),1e-12)))
        scores.append(float(np.mean(vals)))
    return {'keyword_npmi':float(np.mean(scores)),'keyword_top10_diversity':float(len(terms)/ranks.size)},scores

def prepare():
    if (OUT/'PREPARED.json').exists():return
    vocab=pd.read_csv(RUN/'vocabulary.csv');mask=vocab.display_name.isin(BROAD).to_numpy()
    assert mask.sum()==20
    np.save(OUT/'broad_mask.npy',mask)
    vocab.assign(column_id=np.arange(len(vocab))).loc[mask].to_csv(OUT/'removed_keywords.csv',index=False)
    vocab.assign(column_id=np.arange(len(vocab))).loc[~mask].to_csv(OUT/'retained_vocabulary.csv',index=False)
    protocol={'registered_at':stamp(),'removed_terms':BROAD,'initial_topic_counts':INITIAL_K,'seeds':SEEDS,
        'epochs':EPOCHS,'batch_size':BATCH,'transform_max_iter':200,'forget_factor':1.,
        'training':'Reuse prior uniform 200,000-paper sample; remove empty-after-deletion rows in BOTH arms; same row order per epoch.',
        'validation':'Prior 60,000 heldout papers; common nonempty-after-deletion subset for all model quality comparisons; report total coverage separately.',
        'confirmation':'Fresh uniform 30,000 original-nonzero papers excluding prior 260,000; inspected only after K selection.',
        'primary_selection':'Highest three-seed mean BGE cosine silhouette on validation; exact ties prefer smaller K. Secondary metrics and tradeoffs always reported; no claim of global or expert optimality.',
        'boundary_expansion':'None: user explicitly requested only 200, 300, 500, 800, 1000.',
        'baseline':'Retained-discipline K=500 retrained on identical common training rows. Initial W and retained H columns are paired; removed H columns are initialized at exact zero.',
        'input':'Existing score*IDF matrices; set named discipline columns to exact zero, eliminate sparse zeros, and re-normalize rows. Preserve column indices for traceability. No document relevance filtering.',
        'multilabel':{'formula':'p_ij = W_ij * L2(H_j) / sum_k(W_ik * L2(H_k))','rule':'assign every p_ij >= threshold; no top-N cap or forced argmax fallback',
            'thresholds':THRESHOLDS,'provisional_export_threshold':DEFAULT_THRESHOLD,
            'meaning':'Relative NMF contributions, not calibrated probabilities, semantic accuracy or a claimed optimal threshold.'},
        'final_fit':'Refit selected K, seed=17, five epochs on all nonempty frozen papers after feature deletion; evaluate confirmation before this fit; export full-corpus multi-memberships separately from original model.',
        'limitations':['Only these 20 terms are removed; there is no available per-keyword ontology level used here.',
            'Corpus scope is unchanged; irrelevant documents, subfield terms and wrong-sense keywords may remain.',
            'Original full-corpus vocabulary/IDF are reused: confirmation excludes NMF fitting but is not an end-to-end unseen vocabulary test.',
            'Validation papers were inspected in a previous ablation; fresh confirmation reduces tuning reuse but BGE is not expert ground truth.',
            'Different K may favor different resolution; the declared primary criterion can prefer coarse themes.',
            'Fixed five epochs are a matched training budget, not proof of convergence. Three seeds measure initialization sensitivity, not sampling uncertainty.',
            'The final all-data refit has no remaining heldout population; sample-confirmation scores are not final-model accuracy.'],
        'inputs':{'original_model_sha256':sha(RUN/'selected_nmf.joblib'),'vocabulary_sha256':sha(RUN/'vocabulary.csv'),
            'previous_train_sha256':sha(OLD/'train.npz'),'previous_validation_sha256':sha(OLD/'heldout.npz'),
            'code_sha256':sha(__file__),'gpu_code_sha256':sha(OUT/'fast_nmf.py')}}
    write(OUT/'PROTOCOL.json',protocol)
    raw_train=sparse.load_npz(OLD/'train.npz');raw_val=sparse.load_npz(OLD/'heldout.npz')
    a=clean(raw_train,mask);b=clean(raw_val,mask)
    np.save(OUT/'train_valid.npy',nonzero(a));np.save(OUT/'validation_valid.npy',nonzero(b))
    oldids=np.concatenate([np.load(OLD/'train_row_ids.npy'),np.load(OLD/'test_row_ids.npy')])
    paths=sorted((RUN/'matrices').glob('part-*.npz'));eligible=[];audit=[];focus=[]
    for i,p in enumerate(paths):
        x=sparse.load_npz(p);ids=np.load(p.with_suffix('.rows.npy'));z=clean(x,mask)
        good=nonzero(x);zg=nonzero(z)
        eligible.append(ids[good & ~np.isin(ids,oldids)])
        audit.append({'part':p.stem,'papers':len(ids),'original_nonzero':int(good.sum()),'removed_only':int((good&~zg).sum()),'remaining_nonzero':int(zg.sum()),
            'original_nnz':x.nnz,'remaining_nnz':z.nnz,'matrix_sha256':sha(p),'row_ids_sha256':sha(p.with_suffix('.rows.npy'))})
        f=pd.read_parquet(RUN/'paper_assignments'/(p.stem+'.parquet'),columns=['row_id','category_id'])
        assert np.array_equal(ids,f.row_id)
        f['no_features_after_removal']=~zg
        focus.append(f.groupby('category_id',dropna=False).no_features_after_removal.agg(['size','sum']).reset_index())
        if i%50==0:progress('audit_full_corpus',part=i,total=len(paths))
    ids=np.sort(np.random.default_rng(2026101902).choice(np.concatenate(eligible),30000,replace=False))
    assert not np.intersect1d(ids,oldids).size
    np.save(OUT/'confirmation_row_ids.npy',ids)
    xs=[];es=[];metas=[]
    for i,p in enumerate(paths):
        rows=np.load(p.with_suffix('.rows.npy'));sel=np.isin(rows,ids)
        if not sel.any():continue
        xs.append(sparse.load_npz(p)[sel]);es.append(np.asarray(np.load(RUN/'embeddings'/(p.stem+'.npy'),mmap_mode='r')[sel]).copy())
        f=pq.read_table(CORPUS/(p.stem+'.parquet'),columns=['row_id','doc_id','title','body','date','title_only']).to_pandas()
        f=f[f.row_id.isin(rows[sel])];assert np.array_equal(f.row_id,rows[sel]);metas.append(f)
        if i%50==0:progress('extract_confirmation',part=i,total=len(paths))
    sparse.save_npz(OUT/'confirmation_raw.npz',sparse.vstack(xs,format='csr'))
    np.save(OUT/'confirmation_embeddings.npy',normalize(np.concatenate(es)).astype('float32'))
    pd.concat(metas,ignore_index=True).to_parquet(OUT/'confirmation_metadata.parquet',index=False)
    pd.DataFrame(audit).to_csv(OUT/'full_corpus_feature_audit.csv',index=False)
    f=pd.concat(focus).groupby('category_id',dropna=False)[['size','sum']].sum().reset_index()
    f.columns=['original_category_id','papers','no_features_after_removal'];f['no_features_fraction']=f.no_features_after_removal/f.papers
    f.to_csv(OUT/'original_topics_feature_loss.csv',index=False)
    write(OUT/'PREPARED.json',{'completed_at':stamp(),'original_training_documents':len(nonzero(a)),
        'common_training_documents':int(nonzero(a).sum()),'validation_documents':b.shape[0],
        'validation_nonzero':int(nonzero(b).sum()),'confirmation_documents':len(ids),
        'full_corpus_totals':pd.DataFrame(audit).select_dtypes('number').sum().astype(int).to_dict(),
        'hashes':{name:sha(OUT/name) for name in ['broad_mask.npy','train_valid.npy','validation_valid.npy','confirmation_row_ids.npy','confirmation_raw.npz','confirmation_embeddings.npy','confirmation_metadata.parquet']}})
    progress('prepared')

def train_one(k,seed,arm,raw_train,raw_val,mask,context,binary):
    folder=OUT/f'{arm}_k{k}_seed{seed}';folder.mkdir(exist_ok=True)
    if (folder/'COMPLETE.json').exists():return read(folder/'COMPLETE.json')
    started=time.monotonic();good=np.load(OUT/'train_valid.npy')
    a=raw_train[good] if arm=='retained' else clean(raw_train,mask)[good]
    b=raw_val if arm=='retained' else clean(raw_val,mask)
    orders=[np.random.default_rng(1700+epoch).permutation(a.shape[0]) for epoch in range(EPOCHS)]
    w0,h0=_initialize_nmf(raw_train[good][orders[0][:BATCH]],n_components=k,init='random',random_state=seed)
    init_hash=hashlib.sha256(w0.tobytes()+h0.tobytes()).hexdigest()
    if arm=='removed':h0[:,mask]=0
    applied_init_hash=hashlib.sha256(w0.tobytes()+h0.tobytes()).hexdigest()
    model=GpuMiniBatchNMF(n_components=k,init='custom',random_state=seed,batch_size=BATCH,max_iter=1,
        max_no_improvement=None,tol=1e-4,forget_factor=1.,fresh_restarts=False,transform_max_iter=200)
    visits=0;history=[]
    for epoch,order in enumerate(orders):
        for lo in range(0,len(order),BATCH):
            batch=a[order[lo:lo+BATCH]]
            if visits==0:model.partial_fit(batch,W=w0.copy(),H=h0.copy())
            else:model.partial_fit(batch)
            visits+=batch.shape[0]
        z=a[:2048];w=model.transform(z);h=model.components_
        err=float(z.multiply(z).sum()-2*np.sum(w*(z@h.T))+np.sum((w@(h@h.T))*w))
        history.append({'epoch':epoch+1,'relative_training_error':float(np.sqrt(max(0,err)/z.multiply(z).sum()))})
        progress('train_grid',arm=arm,k=k,seed=seed,epoch=epoch+1,seconds=round(time.monotonic()-started,1))
    assert visits==a.shape[0]*EPOCHS
    if arm=='removed':assert (model.components_[:,mask]==0).all()
    p=infer(model,b);metric,labels,sils=evaluate(p,context,k)
    coherence,per_topic=keyword_coherence(model.components_,binary,pd.read_csv(RUN/'vocabulary.csv'))
    metric.update(coherence)
    # All K in the removed arm reconstruct the same target and cohort.
    ix=np.flatnonzero(context['valid']);sq=cross=recon=0.
    for lo in range(0,len(ix),BATCH):
        z=b[ix[lo:lo+BATCH]];w=model.transform(z);h=model.components_
        sq+=float(z.multiply(z).sum());cross+=float(np.sum(w*(z@h.T)));recon+=float(np.sum((w@(h@h.T))*w))
    metric['relative_validation_reconstruction_error']=float(np.sqrt(max(0,sq-2*cross+recon)/sq))
    vocab=pd.read_csv(RUN/'vocabulary.csv');h=model.components_;tops=np.argsort(-h,axis=1,kind='stable')[:,:15]
    counts=np.bincount(labels[labels>=0],minlength=k)
    catalog=pd.DataFrame([{'topic_id':i,'topic_code':f'K{k}-T{i+1:04d}','name':' / '.join(vocab.display_name.iloc[top[:3]]),
        'top_keywords':' | '.join(vocab.display_name.iloc[top]),'validation_top1_documents':int(counts[i]),'npmi_top10':per_topic[i]} for i,top in enumerate(tops)])
    catalog.to_csv(folder/'topic_catalog.csv',index=False)
    np.save(folder/'components.npy',h);np.save(folder/'validation_labels.npy',labels)
    np.save(folder/'validation_contributions.npy',p);np.save(folder/'silhouettes.npy',sils)
    joblib.dump(model,folder/'model.joblib',compress=1)
    pd.DataFrame(threshold_metrics(p,nonzero(b))).to_csv(folder/'threshold_sensitivity.csv',index=False)
    d={'k':k,'seed':seed,'arm':arm,'completed_at':stamp(),'initialization_sha256':init_hash,
        'applied_initialization_sha256':applied_init_hash,'removed_columns_initially_zero':arm=='removed',
        'training_documents':a.shape[0],'training_visits':visits,'history':history,'metrics':metric,
        'elapsed_seconds':time.monotonic()-started}
    write(folder/'COMPLETE.json',d);progress('grid_fit_complete',k=k,seed=seed,arm=arm,metrics=metric)
    del model,p,a,b;GpuMiniBatchNMF._cuda().get_default_memory_pool().free_all_blocks()
    return d

def summarize_grid():
    records=[read(p) for p in sorted(OUT.glob('*_k*_seed*/COMPLETE.json'))]
    records=[r for r in records if (r['arm']=='removed' and r['k'] in INITIAL_K) or (r['arm']=='retained' and r['k']==500)]
    frame=pd.DataFrame([{'arm':r['arm'],'k':r['k'],'seed':r['seed'],**r['metrics']} for r in records])
    frame.to_csv(OUT/'metrics_by_seed.csv',index=False)
    stability=[];valid=np.load(OUT/'validation_valid.npy')
    for (arm,k),g in frame.groupby(['arm','k']):
        for a,b in itertools.combinations(sorted(g.seed),2):
            ya=np.load(OUT/f'{arm}_k{k}_seed{a}/validation_labels.npy')[valid]
            yb=np.load(OUT/f'{arm}_k{k}_seed{b}/validation_labels.npy')[valid]
            stability.append({'arm':arm,'k':k,'seed_a':a,'seed_b':b,'ARI':float(adjusted_rand_score(ya,yb))})
    stab=pd.DataFrame(stability);stab.to_csv(OUT/'seed_stability.csv',index=False)
    agg=frame.groupby(['arm','k']).agg({c:['mean','std'] for c in frame.columns if c not in ['arm','k','seed']})
    agg.columns=['_'.join(c) for c in agg.columns];agg=agg.reset_index()
    agg=agg.merge(stab.groupby(['arm','k']).ARI.mean().reset_index().rename(columns={'ARI':'seed_ARI_mean'}),on=['arm','k'])
    agg.to_csv(OUT/'metrics_summary.csv',index=False)
    return agg

def grid():
    assert sha(__file__)==read(OUT/'PROTOCOL.json')['inputs']['code_sha256']
    if (OUT/'SELECTION.json').exists():return
    mask=np.load(OUT/'broad_mask.npy');raw_train=sparse.load_npz(OLD/'train.npz');raw_val=sparse.load_npz(OLD/'heldout.npz')
    valid=np.load(OUT/'validation_valid.npy');emb=np.load(OLD/'heldout_embeddings.npy')
    context=metric_context(emb,valid,np.load(OLD/'evaluation_indices.npy'))
    np.save(OUT/'validation_evaluation_indices.npy',context['evaluation'])
    binary=raw_val[valid].copy();binary.data[:]=1
    for k in INITIAL_K:
        for seed in SEEDS:train_one(k,seed,'removed',raw_train,raw_val,mask,context,binary)
    for seed in SEEDS:train_one(500,seed,'retained',raw_train,raw_val,mask,context,binary)
    summary=summarize_grid();removed=summary[summary.arm.eq('removed')]
    best=int(removed.sort_values(['cosine_silhouette_mean','k'],ascending=[False,True]).iloc[0].k)
    for seed in SEEDS:
        assert read(OUT/f'retained_k500_seed{seed}/COMPLETE.json')['initialization_sha256']==read(OUT/f'removed_k500_seed{seed}/COMPLETE.json')['initialization_sha256']
    write(OUT/'SELECTION.json',{'selected_at':stamp(),'selected_k':best,'deployment_seed':17,
        'selection_criterion':'maximum validation mean BGE cosine silhouette over three seeds',
        'tested_k':sorted(removed.k.astype(int).tolist()),'boundary_winner':best in [int(removed.k.min()),int(removed.k.max())],
        'default_threshold':DEFAULT_THRESHOLD,'threshold_status':'preregistered provisional default, not an expert-validated optimum',
        'confirmation_used_for_selection':False,'selected_validation_metrics':removed[removed.k.eq(best)].iloc[0].to_dict()})
    progress('selection_complete',selected_k=best)

def confirm():
    if (OUT/'CONFIRMATION.json').exists():return
    selected=read(OUT/'SELECTION.json')['selected_k'];mask=np.load(OUT/'broad_mask.npy')
    raw=sparse.load_npz(OUT/'confirmation_raw.npz');x=clean(raw,mask);valid=nonzero(x)
    emb=np.load(OUT/'confirmation_embeddings.npy');context=metric_context(emb,valid)
    np.save(OUT/'confirmation_evaluation_indices.npy',context['evaluation'])
    binary=raw[valid].copy();binary.data[:]=1
    records=[];sensitivities=[]
    for arm,k in [('removed',k) for k in sorted({selected,500})]+[('retained',500)]:
        for seed in SEEDS:
            folder=OUT/f'{arm}_k{k}_seed{seed}';model=joblib.load(folder/'model.joblib')
            p=infer(model,x if arm=='removed' else raw);metric,labels,sils=evaluate(p,context,k)
            coherence,_=keyword_coherence(model.components_,binary,None);metric.update(coherence)
            records.append({'arm':arm,'k':k,'seed':seed,**metric})
            np.save(folder/'confirmation_contributions.npy',p)
            sensitivities.extend([{'arm':arm,'k':k,'seed':seed,**r} for r in threshold_metrics(p,valid if arm=='removed' else nonzero(raw))])
            progress('confirmation',arm=arm,k=k,seed=seed,metrics=metric)
    pd.DataFrame(records).to_csv(OUT/'confirmation_metrics.csv',index=False)
    pd.DataFrame(sensitivities).to_csv(OUT/'confirmation_threshold_sensitivity.csv',index=False)
    write(OUT/'CONFIRMATION.json',{'completed_at':stamp(),'selected_k_locked_before_evaluation':selected,
        'documents':raw.shape[0],'remaining_nonzero':int(valid.sum()),'empty_after_removal':int((~valid).sum()),
        'no_training_validation_overlap':True,'metrics':records,'selection_not_revised':True})

def full_fit():
    if (OUT/'full_model/TRAINING_COMPLETE.json').exists():return
    assert (OUT/'CONFIRMATION.json').exists()
    folder=OUT/'full_model';folder.mkdir(exist_ok=True)
    k=read(OUT/'SELECTION.json')['selected_k'];mask=np.load(OUT/'broad_mask.npy')
    paths=sorted((RUN/'matrices').glob('part-*.npz'))
    model=GpuMiniBatchNMF(n_components=k,init='custom',random_state=17,batch_size=BATCH,max_iter=1,
        max_no_improvement=None,tol=1e-4,forget_factor=1.,fresh_restarts=False,transform_max_iter=200)
    checkpoint=folder/'checkpoint.joblib';start_epoch=0;visits=0;history=[]
    if checkpoint.exists():
        state=joblib.load(checkpoint);model=state['model'];start_epoch=state['epoch'];visits=state['visits'];history=state['history']
    for epoch in range(start_epoch,EPOCHS):
        order=np.random.default_rng(1700+epoch).permutation(len(paths))
        for j,i in enumerate(order):
            x=clean(sparse.load_npz(paths[i]),mask);ix=np.flatnonzero(nonzero(x))
            np.random.default_rng(170000+epoch*1000+int(i)).shuffle(ix)
            for lo in range(0,len(ix),BATCH):
                batch=x[ix[lo:lo+BATCH]]
                if visits==0:
                    w0,h0=_initialize_nmf(batch,n_components=k,init='random',random_state=17)
                    h0[:,mask]=0
                    model.partial_fit(batch,W=w0,H=h0)
                else:model.partial_fit(batch)
                visits+=len(ix[lo:lo+BATCH])
            if j%30==0:progress('full_training',k=k,epoch=epoch+1,part=j+1,parts=len(paths),visits=visits)
        h=model.components_;z=clean(sparse.load_npz(paths[0]),mask);z=z[np.flatnonzero(nonzero(z))[:2048]];w=model.transform(z)
        sq=float(z.multiply(z).sum());err=sq-2*float(np.sum(w*(z@h.T)))+float(np.sum((w@(h@h.T))*w))
        history.append({'epoch':epoch+1,'relative_diagnostic_error':float(np.sqrt(max(0,err)/sq)),'visits':visits})
        joblib.dump({'epoch':epoch+1,'visits':visits,'model':model,'history':history},checkpoint)
        progress('full_epoch_complete',k=k,**history[-1])
    expected=read(OUT/'PREPARED.json')['full_corpus_totals']['remaining_nonzero']*EPOCHS
    assert visits==expected and (model.components_[:,mask]==0).all()
    joblib.dump(model,folder/'model.joblib',compress=1);np.save(folder/'components.npy',model.components_)
    write(folder/'TRAINING_COMPLETE.json',{'k':k,'seed':17,'epochs':EPOCHS,'visits':visits,'history':history,
        'model_sha256':sha(folder/'model.joblib'),'training_population':expected//EPOCHS,'completed_at':stamp()})

def export_full():
    folder=OUT/'full_model'
    if (folder/'EXPORT_COMPLETE.json').exists():return
    model=joblib.load(folder/'model.joblib');k=model.n_components;mask=np.load(OUT/'broad_mask.npy')
    (folder/'paper_assignments').mkdir(exist_ok=True);(folder/'contribution_edges_ge_005').mkdir(exist_ok=True)
    vocab=pd.read_csv(RUN/'vocabulary.csv');tops=np.argsort(-model.components_,axis=1,kind='stable')[:,:15]
    primary_counts=np.zeros(k,np.int64);multi_counts=np.zeros(k,np.int64);weighted=np.zeros(k,np.float64)
    dist=np.zeros(22,np.int64);summary=[];fullsens=[];examples=[]
    focus_ids=set(r['doc_id'] for r in read(OLD/'fixed_focus_review.json'))
    for i,path in enumerate(sorted((RUN/'matrices').glob('part-*.npz'))):
        raw=sparse.load_npz(path);x=clean(raw,mask);valid=nonzero(x);p=infer(model,x);ids=np.load(path.with_suffix('.rows.npy'))
        original=pd.read_parquet(RUN/'paper_assignments'/(path.stem+'.parquet'),columns=['row_id','category_id'])
        meta=pq.read_table(CORPUS/(path.stem+'.parquet'),columns=['row_id','doc_id','title','date','title_only']).to_pandas()
        assert np.array_equal(meta.row_id,ids) and np.array_equal(original.row_id,ids)
        a=assignments(p,DEFAULT_THRESHOLD);n=a.sum(1);best=p.argmax(1);top1=p.max(1)
        primary_counts+=np.bincount(best[valid],minlength=k);multi_counts+=a.sum(0);weighted+=np.where(a,p,0).sum(0)
        dist+=np.bincount(n,minlength=len(dist))[:len(dist)]
        labels=[];scores=[]
        for row in range(len(ids)):
            ix=np.flatnonzero(a[row]);ix=ix[np.argsort(-p[row,ix],kind='stable')]
            labels.append([int(t) for t in ix]);scores.append([float(p[row,t]) for t in ix])
        status=np.where(~nonzero(raw),'original_no_features',np.where(~valid,'only_removed_discipline_features',np.where(n==0,'below_contribution_threshold','assigned')))
        frame=meta[['row_id','doc_id']].copy();frame['original_category_id']=original.category_id
        frame['primary_topic_id']=np.where(valid,best,-1);frame['primary_contribution']=top1
        frame['topic_ids']=labels;frame['topic_contributions']=scores;frame['topic_count']=n
        frame['retained_contribution']=np.where(a,p,0).sum(1);frame['assignment_status']=status
        frame.to_parquet(folder/'paper_assignments'/(path.stem+'.parquet'),index=False)
        rr,cc=np.nonzero(p>=.05)
        pd.DataFrame({'row_id':ids[rr],'topic_id':cc.astype('int32'),'relative_contribution':p[rr,cc]}).to_parquet(folder/'contribution_edges_ge_005'/(path.stem+'.parquet'),index=False)
        summary.append({'part':path.stem,'papers':len(ids),'feature_valid':int(valid.sum()),'assigned':int((n>0).sum()),
            'multiple':int((n>1).sum()),'below_threshold':int(((n==0)&valid).sum()),'edges_default':int(n.sum()),'edges_ge_005':len(rr)})
        fullsens.extend([{'part':path.stem,**r} for r in threshold_metrics(p,valid)])
        selected=np.flatnonzero(meta.doc_id.isin(focus_ids))
        for j in selected:
            examples.append({'doc_id':meta.doc_id.iloc[j],'title':meta.title.iloc[j],'original_category_id':original.category_id.iloc[j],
                'status':status[j],'primary_topic_id':int(best[j]) if valid[j] else -1,
                'topic_ids':labels[j],'contributions':scores[j],
                'topic_names':[' / '.join(vocab.display_name.iloc[tops[t,:3]]) for t in labels[j]]})
        if i%20==0:progress('export_full',part=i+1,total_parts=242,k=k)
    catalog=pd.DataFrame([{'topic_id':j,'topic_code':f'RBK{k}-T{j+1:04d}','name':' / '.join(vocab.display_name.iloc[top[:3]]),
        'top_keywords':' | '.join(vocab.display_name.iloc[top]),'primary_documents':int(primary_counts[j]),
        'multilabel_documents':int(multi_counts[j]),'assigned_contribution_sum':float(weighted[j]),
        'scope_review_status':'not_reviewed'} for j,top in enumerate(tops)])
    catalog.to_csv(folder/'topic_catalog.csv',index=False)
    pd.DataFrame(summary).to_csv(folder/'export_parts.csv',index=False)
    pd.DataFrame(fullsens).to_csv(folder/'threshold_sensitivity_by_part.csv',index=False)
    pd.DataFrame({'topic_count':np.arange(len(dist)),'documents':dist}).to_csv(folder/'topics_per_document_distribution.csv',index=False)
    write(folder/'fixed_focus_review.json',examples)
    total=pd.DataFrame(summary).select_dtypes('number').sum().astype(int).to_dict()
    assert total['papers']==4831088 and primary_counts.sum()==total['feature_valid'] and multi_counts.sum()==total['edges_default']
    write(folder/'EXPORT_COMPLETE.json',{'completed_at':stamp(),'k':k,'threshold':DEFAULT_THRESHOLD,'totals':total,
        'topic_id_indexing':'zero-based integers; use topic_catalog.csv for display codes; IDs are not original F IDs',
        'membership_semantics':'Every relative contribution >= threshold, no fallback, no cap. Primary topic is diagnostic and may be below membership threshold.',
        'edges_file_minimum':.05,'all_thresholds_at_or_above_005_recoverable_from_edges':True,
        'lower_thresholds_require_model_inference':True,'raw_data_and_original_model_unchanged':True})
    progress('export_complete',**total)

def tests():
    # Scaling invariance, exact threshold inclusivity and zero-feature abstention.
    h=np.array([[3.,4.,0.],[0.,0.,2.]],np.float32);w=np.array([[.5,1.],[0.,0.]],np.float32)
    p=relative_contributions(w,h);s=np.array([7.,.2],np.float32)
    assert np.allclose(p,relative_contributions(w/s,h*s[:,None]))
    assert np.allclose(p.sum(1),[1,0]) and not assignments(p,.1)[1].any()
    assert assignments(np.array([[.1,.2,.7]],np.float32),.1).all()
    x=sparse.csr_matrix([[2.,0.,0.],[2.,3.,0.],[0.,0.,0.]],dtype=np.float32)
    z=clean(x,np.array([True,False,False]));assert np.array_equal(nonzero(z),[False,True,False])
    assert z.nnz==1 and z[1,1]==1
    write(OUT/'UNIT_CHECKS.json',{'contribution_scaling_invariance':True,'threshold_inclusive':True,'empty_input_abstains':True,'exact_feature_removal':True})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','grid','confirm','full_fit','export','all','test']);args=parser.parse_args()
    with threadpool_limits(4):
        tests()
        if args.stage in ['prepare','all']:prepare()
        if args.stage in ['grid','all']:grid()
        if args.stage in ['confirm','all']:confirm()
        if args.stage in ['full_fit','all']:full_fit()
        if args.stage in ['export','all']:export_full()
