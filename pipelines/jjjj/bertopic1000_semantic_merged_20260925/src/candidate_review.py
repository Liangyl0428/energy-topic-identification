"""Include explicitly reviewed cross-language pairs even when vector retrieval missed them."""
from merge_common import *
import itertools
import numpy as np
import pandas as pd

def export_candidate_decisions(decisions):
    candidates=pd.read_csv(BASE/'review/candidates.csv').fillna('')
    candidates['candidate_origin']='precomputed_similarity_retrieval'
    pair_decisions={}
    for g in decisions['merge_groups']+decisions['keep_or_defer']:
        for a,b in itertools.combinations(sorted(g['members']),2):
            key=(f'T{a:04d}',f'T{b:04d}')
            assert key not in pair_decisions, f'duplicate or conflicting pair: {key}'
            pair_decisions[key]=g
    seen=set(zip(candidates.a,candidates.b))
    cards=read(BASE/'review/topic_cards.json')
    semantic=np.load(BASE/'review/semantic_cosines.npy')
    lexical=np.load(BASE/'review/lexical_cosines.npy')
    extra=[]
    for key in sorted(set(pair_decisions)-seen):
        a,b=[int(x[1:]) for x in key]
        extra.append(dict(a=key[0],b=key[1],semantic_cosine=float(semantic[a,b]),
            lexical_cosine=float(lexical[a,b]),a_keywords=cards[a]['keywords'],
            b_keywords=cards[b]['keywords'],candidate_origin='explicit_semantic_inventory_review'))
    if extra:
        candidates=pd.concat([candidates,pd.DataFrame(extra)],ignore_index=True)
    for key,default in [('decision','未逐对审定；未合并'),('decision_id',''),('reason','')]:
        candidates[key]=[pair_decisions.get((r.a,r.b),{}).get(key,default) for r in candidates.itertuples()]
    candidates['screen_scope']=['已有明确抽样语义决策；详见decision_id' if x else '相似度召回候选；未逐对语义审定' for x in candidates.decision_id]
    candidates.to_csv(BASE/'review/candidate_decisions.csv',index=False,encoding='utf-8-sig')
    validate_candidate_decisions(decisions,candidates)
    return candidates

def validate_candidate_decisions(decisions,candidates=None):
    if candidates is None:
        candidates=pd.read_csv(BASE/'review/candidate_decisions.csv').fillna('')
    assert not candidates.duplicated(['a','b']).any()
    pairs={(r.a,r.b):r for r in candidates.itertuples()}
    for g in decisions['merge_groups']+decisions['keep_or_defer']:
        for a,b in itertools.combinations(sorted(g['members']),2):
            r=pairs[(f'T{a:04d}',f'T{b:04d}')]
            assert r.decision==g['decision'] and r.decision_id==g['decision_id']
    return len(candidates)
