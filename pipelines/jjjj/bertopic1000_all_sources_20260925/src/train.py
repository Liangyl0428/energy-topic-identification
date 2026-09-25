"""Full-corpus independent K=1000 training; no source files are changed."""
from common import *
import argparse, time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import joblib
from scipy import sparse
from sklearn.cluster import MiniBatchKMeans
from sklearn.preprocessing import normalize
from threadpoolctl import threadpool_limits
from bertopic._bertopic import TopicMapper
from experiment_components import FrozenClusterer, CachedCountVectorizer, FiniteClassTfidf, CachedBERTopic
from lexical import analyzer  # Needed to load the original, local cached vectorizer.

def train():
    threadpool_limits(4)
    for d in ['models','results','logs','evidence','data']:
        (BASE/d).mkdir(parents=True,exist_ok=True)
    if (BASE/'models/CLUSTER_AUDIT.json').exists():
        raise RuntimeError('Completed run exists; preserve it instead of overwriting')
    start=time.time()
    inp=read(SOURCE/'data/INPUT_MANIFEST.json')
    embedding=read(SOURCE/'models/EMBEDDING_AUDIT.json')
    assert embedding['input_sha256']==sha(SOURCE/'data/INPUT_MANIFEST.json')
    parts=inp['parts'];n=inp['documents']
    config={'clusters':K,'seed':SEED,'documents':n,'source':str(SOURCE.relative_to(ROOT)),
            'embedding_model':embedding['model'],'embedding_revision':embedding['revision'],
            'reused_projection':'source-weighted PCA64 + L2 normalization',
            'training_source_mass':{'paper':.70,'patent':.25,'policy':.05},
            'initialization_documents':100000,'all_document_passes':3,
            'change_vs_500':'n_clusters only; same snapshot, embeddings, PCA, source weights, seed and training schedule',
            'old_labels_used_for_fit':False,'whole_cluster_split_constraint':False,'automatic_merging':False,
            'source_files_read_only':True,'started_utc':now()}
    dump(BASE/'RUN_CONFIG.json',config)
    protected=['data/INPUT_MANIFEST.json','models/EMBEDDING_AUDIT.json','models/BOW_AUDIT.json',
               'models/CLUSTER_AUDIT.json','models/projection.joblib','models/reduced.npy',
               'models/kmeans500.joblib','models/vectorizer.joblib','models/topic_centroids.npy',
               'results/raw_labels.npy','results/raw_to_merged.csv','results/merged_topics.csv','VALIDATION.json']
    baseline={'source':str(SOURCE),'files':[{'path':p,'sha256':sha(SOURCE/p)} for p in protected]}
    dump(BASE/'data/SOURCE_BASELINE.json',baseline)
    dump(BASE/'data/INPUT_REFERENCE.json',{'manifest_path':str(SOURCE/'data/INPUT_MANIFEST.json'),
         'manifest_sha256':sha(SOURCE/'data/INPUT_MANIFEST.json'),'documents':n,'parts':parts})
    source=np.empty(n,dtype=np.uint8);usable=np.empty(n,dtype=bool)
    codes={'paper':0,'patent':1,'policy':2}
    for p in parts:
        path=SOURCE/p['file'];t=pq.read_table(path,columns=['row_id','source','usable']).to_pydict()
        ids=np.asarray(t['row_id']);assert np.array_equal(ids,np.arange(p['first_row'],p['first_row']+p['n']))
        source[ids]=[codes[s] for s in t['source']];usable[ids]=t['usable']
    count=np.bincount(source[usable],minlength=3)
    weights=np.array([.70,.25,.05])*count[0]/(.70*count)
    np.save(BASE/'data/source_codes.npy',source);np.save(BASE/'data/usable.npy',usable)
    projection=joblib.load(SOURCE/'models/projection.joblib')
    z=np.load(SOURCE/'models/reduced.npy',mmap_mode='r')
    assert z.shape==(n,64)
    rng=np.random.default_rng(SEED)
    initial=np.concatenate([rng.choice(np.flatnonzero((source==i)&usable),min(int(q*100000),int(count[i])),replace=False) for i,q in enumerate([.70,.25,.05])])
    rng.shuffle(initial)
    km=MiniBatchKMeans(n_clusters=K,batch_size=4096,init_size=50000,n_init=3,max_iter=60,
                      max_no_improvement=15,reassignment_ratio=.001,random_state=SEED)
    progress('initializing',documents=n,initialization_sample=len(initial),clusters=K)
    km.fit(np.array(z[initial]))
    all_ids=np.flatnonzero(usable)
    for epoch in range(3):
        order=rng.permutation(all_ids)
        for j in range(0,len(order),8192):
            ix=order[j:j+8192]
            km.partial_fit(np.array(z[ix]),sample_weight=weights[source[ix]].astype(np.float32))
            if j%(8192*80)==0:
                progress('full_corpus_training',pass_number=epoch+1,passes=3,processed=j+len(ix),total=len(order))
        joblib.dump(km,BASE/'models/kmeans1000_checkpoint.joblib')
    joblib.dump(km,BASE/'models/kmeans1000.joblib')
    joblib.dump(projection,BASE/'models/projection.joblib')
    progress('assigning_documents',clusters=K)
    labels=np.full(n,-2,dtype=np.int16);second=np.full(n,-2,dtype=np.int16)
    margin=np.full(n,np.nan,dtype=np.float32);distance=np.full(n,np.nan,dtype=np.float32)
    raw_sum=np.zeros((K,384),dtype=np.float64);counts=np.zeros((K,3),dtype=np.int64)
    embedding_files=[];ties=0
    for i,p in enumerate(parts):
        path=SOURCE/p['file'];ids=np.arange(p['first_row'],p['first_row']+p['n']);good=usable[ids];ix=ids[good]
        ep=SOURCE/'models/embeddings'/f'{path.stem}.npy';x=np.load(ep).astype(np.float32)
        assert x.shape==(len(ids),384) and np.isfinite(x).all()
        if len(ix):
            distances=np.maximum(0,(z[ix]**2).sum(1)[:,None]+(km.cluster_centers_**2).sum(1)[None,:]-2*z[ix]@km.cluster_centers_.T)
            predicted=km.predict(np.array(z[ix]));nearest=distances.argmin(1)
            delta=distances[np.arange(len(ix)),predicted]-distances.min(1)
            assert float(delta.max())<1e-4
            ties+=int((predicted!=nearest).sum())
            d=distances[np.arange(len(ix)),predicted].copy()
            distances[np.arange(len(ix)),predicted]=np.inf
            alternative=distances.argmin(1)
            labels[ix]=predicted;second[ix]=alternative;distance[ix]=d
            margin[ix]=np.maximum(0,distances[np.arange(len(ix)),alternative]-d)
            aggregate=sparse.csr_matrix((weights[source[ix]],(predicted,np.arange(len(ix)))),shape=(K,len(ix)))
            raw_sum+=aggregate@x[good]
            counts+=np.bincount(predicted*3+source[ix],minlength=K*3).reshape(K,3)
            # Compare cached PCA coordinates with a fresh projection of this part.
            sample=np.flatnonzero(good)[:3]
            assert np.allclose(projection.transform(x[sample]),z[ids[sample]],atol=2e-6)
        embedding_files.append({'file':str(ep.relative_to(SOURCE)),'sha256':sha(ep),'rows':len(ids)})
        if i%20==0:progress('assigning_documents',parts_done=i+1,parts_total=len(parts))
    assert set(labels[usable])==set(range(K)) and int(counts.sum())==int(usable.sum())
    for name,value in [('raw_labels',labels),('secondary_labels',second),('distance_margin',margin),('distance_squared',distance),('source_counts',counts)]:
        np.save(BASE/f'results/{name}.npy',value)
    centers=normalize(raw_sum).astype(np.float32);np.save(BASE/'models/topic_centroids.npy',centers)
    dump(BASE/'data/REUSED_EMBEDDINGS.json',{'parts':embedding_files,'model':embedding['model'],'reencoded':False})
    dump(BASE/'results/FIXED_LABELS_READY.json',{'documents':n,'usable':int(usable.sum()),'clusters':K,'created_utc':now()})
    cv=joblib.load(SOURCE/'models/vectorizer.joblib')
    online=CachedCountVectorizer(cv.vocabulary_,K)
    bt=CachedBERTopic(language='multilingual',embedding_model=None,umap_model=projection,
          hdbscan_model=FrozenClusterer(km),vectorizer_model=online,ctfidf_model=FiniteClassTfidf(reduce_frequent_words=True),
          calculate_probabilities=False,top_n_words=20,verbose=False)
    bt.topic_mapper_=TopicMapper(list(range(K)))
    bt.topic_representations_={i:[('initializing',0.)] for i in range(K)}
    bt.topic_sizes_={i:0 for i in range(K)}
    pending=sparse.csr_matrix((K,len(cv.vocabulary_)),dtype=np.int64)
    batch_embeddings=[];batch_ids=[];bow_inputs=[];stream_checks=[]
    for i,p in enumerate(parts):
        path=SOURCE/p['file'];ids=np.arange(p['first_row'],p['first_row']+p['n']);good=usable[ids];ix=ids[good];y=labels[ix]
        bp=SOURCE/'models/bow'/f'{path.stem}.npz';meta=read(bp.with_suffix('.json'))
        assert meta['input_sha256']==p['sha256']
        bow=sparse.load_npz(bp);assert bow.shape==(len(ids),len(cv.vocabulary_))
        aggregate=sparse.csr_matrix((np.ones(len(ix),dtype=np.int64),(y,np.arange(len(ix)))),shape=(K,len(ix)))
        pending=(pending+aggregate@bow[good]).tocsr()
        batch_embeddings.append(np.load(SOURCE/'models/embeddings'/f'{path.stem}.npy').astype(np.float32)[good]);batch_ids.append(ix)
        bow_inputs.append({'file':str(bp.relative_to(SOURCE)),'sha256':sha(bp),'source_sha256':meta['input_sha256']})
        if len(batch_ids)==8 or i==len(parts)-1:
            ix=np.concatenate(batch_ids);x=np.concatenate(batch_embeddings)
            online.pending=pending
            # The adapter consumes cached full-text counts, never tokenizes these IDs.
            bt.partial_fit([f'cached-row-{rid}' for rid in ix],embeddings=x)
            assert np.array_equal(np.asarray(bt.topics_),labels[ix])
            stream_checks.append({'parts_through':i+1,'rows':len(ix),'labels_equal':True})
            pending=sparse.csr_matrix((K,len(cv.vocabulary_)),dtype=np.int64);batch_embeddings=[];batch_ids=[]
            progress('bertopic_full_text_counts',parts_done=i+1,parts_total=len(parts))
    assert all(bt.topic_sizes_[i]==int(counts[i].sum()) for i in range(K))
    direct=FiniteClassTfidf(reduce_frequent_words=True).fit_transform(online.X_)
    diff=(direct-bt.c_tf_idf_).tocsr();error=float(np.max(np.abs(diff.data))) if diff.nnz else 0.
    assert error<1e-12 and np.isfinite(bt.c_tf_idf_.data).all()
    bt.topic_embeddings_=centers;bt.topics_=labels[usable].astype(int).tolist()
    joblib.dump(bt,BASE/'models/bertopic1000.joblib',compress=3)
    sparse.save_npz(BASE/'models/ctfidf.npz',bt.c_tf_idf_)
    sparse.save_npz(BASE/'models/class_word_counts.npz',online.X_)
    rows=[{'topic_id':f'T{i:04d}','cluster':i,'documents':int(counts[i].sum()),'papers':int(counts[i,0]),
           'patents_2026':int(counts[i,1]),'policies':int(counts[i,2]),'keywords':' | '.join(w for w,_ in bt.get_topic(i)),
           'automatic_label':bt.topic_labels_[i],'review_status':'unreviewed'} for i in range(K)]
    pd.DataFrame(rows).to_csv(BASE/'results/raw_1000_topics.csv',index=False,encoding='utf-8-sig')
    dump(BASE/'data/REUSED_BOW.json',{'parts':bow_inputs,'text_basis':'full title and body counts inherited unchanged'})
    dump(BASE/'models/STREAMING_VALIDATION.json',{'updates':stream_checks,'all_topic_counts_match':True,
         'direct_ctfidf_max_abs_error':error,'text_placeholders':'row IDs only; exact cached full-text counts supply all lexical evidence'})
    unchanged=all(sha(SOURCE/r['path'])==r['sha256'] for r in baseline['files'])
    assert unchanged
    dump(BASE/'models/CLUSTER_AUDIT.json',{**config,'assigned_usable_documents':int(usable.sum()),
         'unusable_text_documents':int((~usable).sum()),'per_document_training_weights':dict(zip(codes,map(float,weights))),
         'actual_nonempty_clusters':len(rows),'bertopic_version':'0.17.3','source_protected_files_unchanged':unchanged,
         'float32_nearest_distance_ties':ties,'ctfidf_direct_check':error,'elapsed_seconds':time.time()-start,'completed_utc':now()})
    progress('clustering_complete',clusters=K,assigned=int(usable.sum()),elapsed_seconds=time.time()-start)

if __name__=='__main__':train()
