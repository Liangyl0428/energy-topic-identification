"""Strict whole-cluster mapping. Never uses negative labels as NumPy indices."""
from merge_common import *
import numpy as np

def make_mapping(groups,k=1000):
    if k<=0:raise ValueError('k must be positive')
    anchor=np.arange(k,dtype=np.int16);seen=set();names=set();ids=set()
    for g in groups:
        members=g['members']
        if len(members)<2 or len(set(members))!=len(members):raise ValueError('merge must have >=2 distinct members')
        if not g.get('canonical_name') or g['canonical_name'] in names:raise ValueError('missing or duplicate canonical name')
        if not g.get('decision_id') or g['decision_id'] in ids:raise ValueError('missing or duplicate decision ID')
        for i in members:
            if type(i) is not int or not 0<=i<k:raise ValueError('invalid topic member')
            if i in seen:raise ValueError('overlapping merge groups are forbidden')
            seen.add(i)
        anchor[members]=min(members);names.add(g['canonical_name']);ids.add(g['decision_id'])
    anchors=np.unique(anchor);dense=np.searchsorted(anchors,anchor).astype(np.int16)
    return anchor,dense,anchors

def map_labels(labels,lookup,allowed_negative=(-2,)):
    y=np.asarray(labels)
    if y.dtype.kind not in 'iu':raise ValueError('labels must be integers')
    good=y>=0
    if np.any(y[good]>=len(lookup)):raise ValueError('raw topic outside mapping')
    if not np.isin(y[~good],allowed_negative).all():raise ValueError('unexpected negative label')
    out=y.astype(np.int16,copy=True)
    out[good]=np.asarray(lookup)[y[good]]
    return out

class SemanticTopicModel:
    """Predict with the frozen 1000 model, then apply the reviewed mapping.

    New merged centroids must NOT be used to reassign documents. transform returns
    no new confidence/probability: raw1000 margins are not final-topic confidence.
    Inputs must use the original model's normalized text/384d embedding contract.
    """
    def __init__(self,base=BASE):
        import pandas as pd
        self.base=Path(base)
        self.mapping=pd.read_csv(self.base/'results/raw_to_final.csv').fillna('')
        self.lookup=self.mapping.sort_values('raw_cluster1000').final_topic_index.to_numpy(dtype=np.int16)
        self.topics=pd.read_csv(self.base/'results/final_topics.csv').fillna('')
        self._model=None
    def _load(self):
        if self._model is None:
            import joblib
            sys.path[:0]=[str(RAW/'src'),str(CORPUS/'src')]
            self._model=joblib.load(RAW/'models/bertopic1000.joblib')
        return self._model
    def predict_labels(self,documents,embeddings):
        import pandas as pd
        raw,_=self._load().transform(documents,embeddings=embeddings)
        raw=np.asarray(raw,dtype=np.int64);final=map_labels(raw,self.lookup)
        byindex=self.topics.set_index('final_topic_index')
        return pd.DataFrame({'raw_cluster1000':raw,'final_topic_index':final,
           'final_topic_id':[byindex.loc[int(i),'final_topic_id'] if i>=0 else 'UNUSABLE' for i in final],
           'final_topic_label':[byindex.loc[int(i),'final_topic_label'] if i>=0 else '不可用文本（未分类）' for i in final]})
    def transform(self,documents,embeddings):
        frame=self.predict_labels(documents,embeddings)
        return frame.final_topic_index.tolist(),None
