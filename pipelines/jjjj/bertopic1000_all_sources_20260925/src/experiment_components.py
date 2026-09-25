"""BERTopic components for exact reuse of per-document cached word counts."""
import numpy as np
from scipy import sparse
from bertopic import BERTopic
from bertopic.vectorizers import ClassTfidfTransformer

class FrozenClusterer:
    def __init__(self, model):
        self.model = model
    def fit(self, X, y=None):
        self.labels_ = self.model.predict(X)
        return self
    def partial_fit(self, X, y=None):
        return self.fit(X, y)
    def predict(self, X):
        return self.model.predict(X)

class CachedCountVectorizer:
    def __init__(self, vocabulary, n_clusters):
        self.vocabulary_ = vocabulary
        self._words = np.empty(len(vocabulary), dtype=object)
        for word, i in vocabulary.items(): self._words[i] = word
        self.n_clusters = n_clusters
        self.X_ = sparse.csr_matrix((n_clusters,len(vocabulary)),dtype=np.int64)
        self.pending = None
    def partial_fit(self, raw_documents):
        return self
    def update_bow(self, raw_documents):
        if len(raw_documents)!=self.n_clusters or self.pending is None or self.pending.shape!=self.X_.shape:
            raise ValueError('cached counts and frozen topic IDs are not aligned')
        self.X_ = (self.X_ + self.pending).tocsr()
        self.pending = None
        return self.X_
    def get_feature_names_out(self):
        return self._words

class FiniteClassTfidf(ClassTfidfTransformer):
    def fit(self, X, multiplier=None):
        frequency = np.asarray(X.sum(axis=0)).ravel()
        average = int(X.sum(axis=1).mean())
        idf = np.log1p(average / np.maximum(frequency,1))
        if multiplier is not None: idf *= multiplier
        self.zero_frequency_columns_ = int((frequency==0).sum())
        self._idf_diag = sparse.diags(idf,format='csr')
        return self

class CachedBERTopic(BERTopic):
    def _preprocess_text(self, documents):
        return [str(d) for d in documents]
