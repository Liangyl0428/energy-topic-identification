"""Cached full-text counts must remain exact with a different topic count."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import common
import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer
from bertopic._bertopic import TopicMapper
from bertopic.dimensionality import BaseDimensionalityReduction
from experiment_components import CachedCountVectorizer,FiniteClassTfidf,FrozenClusterer,CachedBERTopic

class KnownGroups:
    def predict(self,X):return X[:,0].astype(int)

class CountTests(unittest.TestCase):
    def test_vectorizer_accepts_1000_topics_and_rejects_wrong_shape(self):
        v=CachedCountVectorizer({'alpha':0,'beta':1},1000)
        v.pending=sparse.csr_matrix(([2,3],([0,999],[0,1])),shape=(1000,2))
        result=v.update_bow(['']*1000)
        self.assertEqual(result[999,1],3)
        v.pending=sparse.csr_matrix((500,2))
        with self.assertRaises(ValueError):v.update_bow(['']*1000)

    def test_streaming_labels_and_ctfidf_equal_direct_full_text_counts(self):
        docs=['alpha solar panel','beta wind turbine','gamma battery storage','delta nuclear heat',
              'alpha solar energy','beta wind energy','gamma battery cycle','delta nuclear power']
        cv=CountVectorizer();bow=cv.fit_transform(docs)
        labels=np.array([0,1,2,3,0,1,2,3]);x=np.column_stack([labels,np.ones(8)])
        online=CachedCountVectorizer(cv.vocabulary_,4)
        bt=CachedBERTopic(embedding_model=None,umap_model=BaseDimensionalityReduction(),
            hdbscan_model=FrozenClusterer(KnownGroups()),vectorizer_model=online,
            ctfidf_model=FiniteClassTfidf(reduce_frequent_words=True),top_n_words=5)
        bt.topic_mapper_=TopicMapper(list(range(4)));bt.topic_representations_={i:[('init',0.)] for i in range(4)}
        bt.topic_sizes_={i:0 for i in range(4)}
        for ix in [np.array([0,1,4,5]),np.array([2,3,6,7])]:
            agg=sparse.csr_matrix((np.ones(len(ix),dtype=int),(labels[ix],np.arange(len(ix)))),shape=(4,len(ix)))
            online.pending=agg@bow[ix]
            bt.partial_fit([f'cached-row-{j}' for j in ix],embeddings=x[ix])
            np.testing.assert_array_equal(bt.topics_,labels[ix])
        full=sparse.csr_matrix((np.ones(8,dtype=int),(labels,np.arange(8))),shape=(4,8))@bow
        self.assertEqual((full!=online.X_).nnz,0)
        direct=FiniteClassTfidf(reduce_frequent_words=True).fit_transform(full)
        np.testing.assert_allclose(direct.toarray(),bt.c_tf_idf_.toarray(),atol=1e-12)
        self.assertEqual(bt.topic_sizes_,{i:2 for i in range(4)})

if __name__=='__main__':unittest.main(verbosity=2)
