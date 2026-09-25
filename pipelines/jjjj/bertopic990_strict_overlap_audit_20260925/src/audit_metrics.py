"""Read-only audit of all 990 topics, exact weighted centroids and all 489555 pairs."""
from pathlib import Path
import sys
AUDIT=Path(__file__).resolve().parents[1]
ROOT=AUDIT.parents[1]
sys.path.insert(0,str(ROOT/'jjjj/bertopic1000_semantic_merged_20260925/src'))
from merge_common import *
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import sparse
from sklearn.preprocessing import normalize
from threadpoolctl import threadpool_limits

def main():
    threadpool_limits(4)
    topics=pd.read_csv(BASE/'results/final_topics.csv').fillna('')
    mapping=pd.read_csv(BASE/'results/raw_to_final.csv').fillna('')
    y=np.load(BASE/'results/final_labels.npy',mmap_mode='r')
    raw=np.load(RAW/'results/raw_labels.npy',mmap_mode='r')
    source=np.load(RAW/'data/source_codes.npy',mmap_mode='r')
    assert len(topics)==990 and len(y)==5119004
    metadata=read(RAW/'models/CLUSTER_AUDIT.json')
    weights=np.array([metadata['per_document_training_weights'][s] for s in ['paper','patent','policy']])
    parts=read(CORPUS/'data/INPUT_MANIFEST.json')['parts']
    sums=np.zeros((990,384),dtype=np.float64)
    raw_sums=np.zeros((1000,384),dtype=np.float64)
    for n,p in enumerate(parts):
        ids=np.arange(p['first_row'],p['first_row']+p['n'])
        good=y[ids]>=0
        x=np.load(CORPUS/'models/embeddings'/f'{Path(p["file"]).stem}.npy').astype(np.float32)[good]
        ids=ids[good]
        reduction=sparse.csr_matrix((weights[source[ids]],(y[ids],np.arange(len(ids)))),shape=(990,len(ids)))
        sums+=reduction@x
        reduction=sparse.csr_matrix((weights[source[ids]],(raw[ids],np.arange(len(ids)))),shape=(1000,len(ids)))
        raw_sums+=reduction@x
        if (n+1)%40==0:
            print('weighted embedding aggregation',n+1,len(parts),flush=True)
    original=np.load(RAW/'models/topic_centroids.npy')
    error=float(np.max(np.abs(normalize(raw_sums)-original)))
    assert error<1e-6,error
    centroids=normalize(sums)
    np.save(AUDIT/'results/final_centroids.npy',centroids)
    semantic=centroids@centroids.T
    lexical=normalize(sparse.load_npz(BASE/'models/ctfidf.npz'))
    lexical=(lexical@lexical.T).toarray()
    print('all pair cosine matrices calculated',flush=True)
    np.save(AUDIT/'results/semantic_cosines.npy',semantic)
    np.save(AUDIT/'results/lexical_cosines.npy',lexical)
    # Original PCA k-means runner-up is a diagnostic, not a recomputed final-topic posterior.
    secondary=np.load(RAW/'results/secondary_labels.npy',mmap_mode='r')
    margin=np.load(RAW/'results/distance_margin.npy',mmap_mode='r')
    good=(y>=0)&(secondary>=0)
    sec=mapping.final_topic_index.to_numpy()[secondary[good]]
    first=y[good]
    flow=np.bincount(first.astype(np.int64)*990+sec,minlength=990**2).reshape(990,990)
    near=np.bincount((first.astype(np.int64)*990+sec)[margin[good]<.02],minlength=990**2).reshape(990,990)
    np.save(AUDIT/'results/secondary_flow_counts.npy',flow)
    np.save(AUDIT/'results/low_margin_flow_counts.npy',near)
    a,b=np.triu_indices(990,k=1)
    pairs=pd.DataFrame(dict(a_index=a,b_index=b,a=topics.final_topic_id.to_numpy()[a],b=topics.final_topic_id.to_numpy()[b],
        semantic_cosine=semantic[a,b],lexical_cosine=lexical[a,b],
        a_runner_up_b=flow[a,b],b_runner_up_a=flow[b,a],
        a_runner_up_b_fraction=flow[a,b]/topics.documents.to_numpy()[a],
        b_runner_up_a_fraction=flow[b,a]/topics.documents.to_numpy()[b],
        low_margin_a_to_b=near[a,b],low_margin_b_to_a=near[b,a]))
    pairs['bidirectional_runner_up_sum']=pairs.a_runner_up_b_fraction+pairs.b_runner_up_a_fraction
    assert len(pairs)==489555
    pairs.to_parquet(AUDIT/'results/all_489555_pairs.parquet',index=False)
    stats=[]
    for metric,thresholds in [('semantic_cosine',[.90,.94,.95,.97]),('lexical_cosine',[.80,.85,.90])]:
        for threshold in thresholds:
            x=pairs[pairs[metric]>=threshold]
            stats.append(dict(metric=metric,threshold=threshold,pairs=len(x),topics=len(set(x.a)|set(x.b))))
    mask=np.eye(990,dtype=bool)
    semantic[mask]=-1
    lexical[mask]=-1
    neighbors=np.argsort(semantic,axis=1)[:,-5:]
    lexical_neighbors=np.argsort(lexical,axis=1)[:,-5:]
    selected={(min(i,int(j)),max(i,int(j))) for i in range(990) for j in np.r_[neighbors[i],lexical_neighbors[i]]}
    selected.update(zip(pairs.loc[(pairs.semantic_cosine>=.90)|(pairs.lexical_cosine>=.80),'a_index'],
        pairs.loc[(pairs.semantic_cosine>=.90)|(pairs.lexical_cosine>=.80),'b_index']))
    chosen=pairs[[tuple(v) in selected for v in zip(pairs.a_index,pairs.b_index)]].copy()
    chosen['a_keywords']=topics.keywords.to_numpy()[chosen.a_index]
    chosen['b_keywords']=topics.keywords.to_numpy()[chosen.b_index]
    chosen['a_label']=topics.final_topic_label.to_numpy()[chosen.a_index]
    chosen['b_label']=topics.final_topic_label.to_numpy()[chosen.b_index]
    chosen.sort_values('semantic_cosine',ascending=False).to_csv(AUDIT/'results/candidate_pairs.csv',index=False,encoding='utf-8-sig')
    top=np.argmax(semantic,axis=1)
    inventory=topics.copy()
    inventory['nearest_topic']=topics.final_topic_id.to_numpy()[top]
    inventory['nearest_semantic_cosine']=semantic[np.arange(990),top]
    inventory['nearest_lexical_cosine']=lexical[np.arange(990),top]
    inventory['automatic_keyword_name']=inventory.final_topic_label.str.match(r'^\d+_')
    inventory['title_only_fraction']=inventory.title_only_documents/inventory.documents
    inventory['dominant_source_fraction']=inventory[['papers','patents','policies']].max(axis=1)/inventory.documents
    inventory.to_csv(AUDIT/'results/topic_audit_inventory.csv',index=False,encoding='utf-8-sig')
    same=int(flow.trace())
    summary=dict(created_utc=now(),topics=990,all_pairs=len(pairs),candidate_pairs=len(chosen),threshold_screens=stats,
        automatic_keyword_names=int(inventory.automatic_keyword_name.sum()),
        previously_only_inventory_screened=int((topics.final_label_status=='完成清单初筛；保留原类及自动标签').sum()),
        previous_detailed_review_topics=int((topics.final_label_status!='完成清单初筛；保留原类及自动标签').sum()),
        source_assigned=topics[['papers','patents','policies']].sum().to_dict(),
        dominant_source_fraction_ge_095=int((inventory.dominant_source_fraction>=.95).sum()),
        low_margin_documents=int(((margin<.02)&(y>=0)).sum()),
        mapped_runner_up_same_as_primary=same,
        raw_centroid_reconstruction_max_abs_error=error,
        thresholds_are_semantic_overlap_verdicts=False,
        semantics='All vectors are reconstructed from the full original cached embeddings and original source weights, aggregated by current final labels. Cosines measure representation similarity, not overlap probability.',
        runner_up_limit='Original PCA64 k-means runner-up mapped to final classes; a diagnostic only, not recomputed final-class second nearest or probability.',
        input_directory=str(BASE),input_delivery_manifest_sha256=sha(BASE/'DELIVERY_MANIFEST.json'),
        labels_modified=False)
    dump(AUDIT/'results/METRICS.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    main()
