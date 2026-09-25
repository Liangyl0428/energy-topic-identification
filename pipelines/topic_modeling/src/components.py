"""Importable components for all-document, memory-bounded BERTopic."""
import numpy as np
from scipy import sparse
from bertopic import BERTopic
from bertopic.vectorizers import ClassTfidfTransformer

class FrozenProjection:
    def __init__(self, mean, components):
        self.mean = mean
        self.components = components

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        z = (np.asarray(X, dtype=np.float32) - self.mean) @ self.components.T
        return z / np.maximum(np.linalg.norm(z, axis=1, keepdims=True), 1e-12)

class FrozenMiniBatchClusterer:
    """After all-document training, freeze labels while accumulating c-TF-IDF."""
    def __init__(self, model):
        self.model = model

    def fit(self, X, y=None):
        self.labels_ = self.model.predict(X)
        return self

    def partial_fit(self, X, y=None):
        return self.fit(X, y)

    def predict(self, X):
        return self.model.predict(X)

class PrecomputedOnlineCountVectorizer:
    """Exact streaming sum of counts precomputed with a fixed CountVectorizer.

    The caller provides a 500-by-vocabulary matrix for the current documents,
    aggregated by their frozen label. It is equivalent to concatenating full
    documents per class but avoids re-tokenization and giant in-memory strings.
    """
    def __init__(self, vocabulary):
        self.vocabulary_ = vocabulary
        self._words = np.empty(len(vocabulary), dtype=object)
        for word, i in vocabulary.items(): self._words[i] = word
        self.pending = None
        self.X_ = sparse.csr_matrix((500, len(vocabulary)), dtype=np.int64)

    def partial_fit(self, raw_documents):
        return self

    def update_bow(self, raw_documents):
        assert len(raw_documents) == 500 and self.pending is not None
        assert self.pending.shape == self.X_.shape
        self.X_ = (self.X_ + self.pending).tocsr()
        self.pending = None
        return self.X_

    def get_feature_names_out(self):
        return self._words

class FiniteClassTfidf(ClassTfidfTransformer):
    def fit(self, X, multiplier=None):
        frequency = np.asarray(X.sum(axis=0)).ravel()
        average = int(X.sum(axis=1).mean())
        idf = np.log1p(average / np.maximum(frequency, 1))
        if multiplier is not None: idf *= multiplier
        self.zero_frequency_columns_ = int((frequency == 0).sum())
        self._idf_diag = sparse.diags(idf, format='csr')
        return self

class StreamingBERTopic(BERTopic):
    def _preprocess_text(self, documents):
        return [str(d) for d in documents]
