from common import *
import time,numpy as np,pandas as pd
from scipy import sparse
from sklearn.preprocessing import normalize
while not (BASE/'evidence/EVIDENCE_AUDIT.json').exists():time.sleep(2)
raw=pd.read_csv(BASE/'results/raw_500_topics.csv')
centers=np.load(BASE/'models/topic_centroids.npy');semantic=centers@centers.T
words=normalize(sparse.load_npz(BASE/'models/ctfidf.npz'));lexical=(words@words.T).toarray()
previous=pd.read_csv(BASE/'evidence/merge_candidates.csv')
flows={(r.a,r.b):r.boundary_flow for r in previous.itertuples()}
seen=set();records=[]
for i in range(500):
    for j in set(np.argsort(semantic[i])[-9:])|set(np.argsort(lexical[i])[-5:]):
        if i==j:continue
        a,b=sorted((i,int(j)))
        if (a,b) in seen:continue
        seen.add((a,b));aa=f'B{a:03d}';bb=f'B{b:03d}'
        records.append(dict(a=aa,b=bb,semantic_cosine=float(semantic[a,b]),ctfidf_cosine=float(lexical[a,b]),boundary_flow=flows.get((aa,bb),np.nan),keywords_a=raw.iloc[a].keywords,keywords_b=raw.iloc[b].keywords))
path=BASE/'evidence/merge_candidates.csv';temp=path.with_suffix('.tmp.csv')
pd.DataFrame(records).sort_values('semantic_cosine',ascending=False).to_csv(temp,index=False);temp.replace(path)
audit=json.loads((BASE/'evidence/EVIDENCE_AUDIT.json').read_text());audit['candidate_pair_selection']='union of both directed top8 semantic and top4 lexical neighbor sets; all124750 pairs scored; candidates are not semantic merge judgments';audit['candidate_pairs']=len(records);audit['missing_boundary_flow']='blank for additional asymmetric-neighbor candidates; not zero'
dump(BASE/'evidence/EVIDENCE_AUDIT.json',audit)
print('SYMMETRIC_CANDIDATES',len(records),flush=True)
