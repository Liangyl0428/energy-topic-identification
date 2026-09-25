"""Give previously unsupported definitions retrieval candidates, not approved seed classes.

Actual label acceptance still requires explicit object/task in the document TITLE,
semantic corroboration, no competing task, and post-run evidence inspection.
"""
from refine_common import *

def main():
    p=BASE/'review/taxonomy_rules.json';d=read(p);spec=d['rules'];ret=read(BASE/'models/rule_retrieval.json')
    descriptors=np.load(BASE/'models/rule_name_vectors.npy');centroids=np.load(NEW/'models/topic_centroids.npy')
    sims=descriptors@centroids.T;added=[]
    for i,r in enumerate(spec):
        if r['candidate_seed_clusters1000']:continue
        ids=[int(c) for c in np.argsort(sims[i])[-3:][::-1] if sims[i,c]>=.45]
        if not ids:continue
        r['candidate_seed_clusters1000']=ids
        r['seed_status']='descriptor_retrieval_only_not_sample_approved'
        r['seed_evidence']=[]
        for c in ids:ret['by_raw1000'][c]=sorted(set(ret['by_raw1000'][c])|{i})
        added.append(dict(rule_id=r['rule_id'],candidate_clusters=ids,maximum_name_cosine=float(sims[i,ids[0]])))
    d['descriptor_only_retrieval_note']='Nearest cluster to the bilingual-capable rule-name embedding is a retrieval aid, not a semantic validation of that cluster. These labels require the same explicit-title gate as all other assignments.'
    dump(p,d);dump(BASE/'models/rule_retrieval.json',ret);dump(BASE/'review/descriptor_only_candidates.json',added)
    frame=pd.read_csv(BASE/'results/taxonomy_rules.csv').fillna('')
    for i,r in enumerate(spec):
        frame.loc[i,'seed_status']=r['seed_status']
        frame.loc[i,'candidate_seed_clusters1000']='|'.join(f'T{x:04d}' for x in r['candidate_seed_clusters1000'])
    frame.to_csv(BASE/'results/taxonomy_rules.csv',index=False,encoding='utf-8-sig')
    progress('candidate_retrieval_complete',rules=len(spec),sample_or_keyword_supported=sum(r['seed_status']!='descriptor_retrieval_only_not_sample_approved' and bool(r['candidate_seed_clusters1000']) for r in spec),
        descriptor_only_retrieval=len(added),unsupported_rules=sum(not r['candidate_seed_clusters1000'] for r in spec))

if __name__=='__main__':main()
