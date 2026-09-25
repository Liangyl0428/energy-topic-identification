from merge_common import *
import numpy as np, pandas as pd, pyarrow.parquet as pq
from scipy import sparse
from sklearn.preprocessing import normalize
from threadpoolctl import threadpool_limits
threadpool_limits(4)
t=pd.read_csv(RAW/'results/topics1000_with_comparison.csv').fillna('')
e=pq.read_table(RAW/'evidence/review_documents.parquet').to_pandas()
c=np.load(RAW/'models/topic_centroids.npy');s=c@c.T;np.fill_diagonal(s,-1)
x=normalize(sparse.load_npz(RAW/'models/ctfidf.npz'));l=(x@x.T).toarray();np.fill_diagonal(l,-1)
np.save(BASE/'review/semantic_cosines.npy',s);np.save(BASE/'review/lexical_cosines.npy',l)
near=np.argsort(s,axis=1)[:,::-1][:,:3]
pairs={(min(i,int(j)),max(i,int(j))) for i in range(1000) for j in near[i]}
pairs.update((int(i),int(j)) for i,j in zip(*np.where(np.triu((s>=.90)|(l>=.8),1))))
candidates=[dict(a=f'T{i:04d}',b=f'T{j:04d}',semantic_cosine=float(s[i,j]),lexical_cosine=float(l[i,j]),a_keywords=t.iloc[i].keywords,b_keywords=t.iloc[j].keywords) for i,j in pairs]
pd.DataFrame(candidates).sort_values('semantic_cosine',ascending=False).to_csv(BASE/'review/candidates.csv',index=False,encoding='utf-8-sig')
cards=[]
for r in t.itertuples():
 i=int(r.cluster);v=e[e.cluster==i];d={}
 for role in ['center:1','random:1']:
  z=v[v.selection_roles.str.split('|').apply(lambda q:role in q)]
  # Show the dominant source, avoiding rare-source samples dominating the screen.
  if len(z):
   dominant=max([('paper',r.papers),('patent',r.patents_2026),('policy',r.policies)],key=lambda p:p[1])[0]
   z=z[z.source==dominant]
   if len(z):
    q=z.iloc[0];d[role]={'row_id':int(q.row_id),'title':str(q.title)}
 card={'cluster':i,'topic_id':r.topic_id,'documents':r.documents,'papers':r.papers,'patents':r.patents_2026,'policies':r.policies,'keywords':r.keywords,'automatic_label':r.automatic_label,'nearest':[{'cluster':int(j),'semantic_cosine':float(s[i,j]),'lexical_cosine':float(l[i,j])} for j in near[i]],'samples':d}
 cards.append(card)
dump(BASE/'review/topic_cards.json',cards)
# Screen text is exactly what will be read in bounded batches; it does not imply full-text review.
lines=[]
for c in cards:
 kw=' / '.join(c['keywords'].split(' | ')[:6])
 if len(kw)>90:kw=kw[:90]
 ex=c['samples'].get('center:1',{});title=ex.get('title','').replace('\n',' ')[:85]
 nb=c['nearest'][0]
 lines.append(f"{c['cluster']:03d} n={c['documents']} near={nb['cluster']:03d}:{nb['semantic_cosine']:.3f} | {kw} | {title}")
(BASE/'review/inventory_screen.txt').write_text('\n'.join(lines)+'\n')
dump(BASE/'review/INPUT_BASELINE.json',{'created_utc':now(),'raw_directory':str(RAW),'corpus_directory':str(CORPUS),'files':[{**v} for v in read(RAW/'DELIVERY_MANIFEST.json')['files']],'delivery_manifest_sha256':sha(RAW/'DELIVERY_MANIFEST.json')})
dump(BASE/'review/PREPARATION.json',{'topics':len(t),'saved_samples':len(e),'candidate_pairs':len(pairs),'rules':['union of top3 centroid neighbors per topic, centroid cosine >=0.90, lexical cosine >=0.80','candidate thresholds are NOT merge thresholds','entire inventory screen plus sampled evidence; no exhaustive pairwise semantic proof'],'semantic_pairs_ge_094':int(np.triu(s>=.94,1).sum()),'created_utc':now()})
print('ready',len(cards),'topic cards;',len(pairs),'candidate pairs; evidence columns',list(e))
