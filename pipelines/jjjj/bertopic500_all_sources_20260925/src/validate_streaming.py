"""Verify streaming class counts, fixed IDs and model reload against direct counts."""
from common import *
import numpy as np, pyarrow.parquet as pq, joblib
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.cluster import MiniBatchKMeans
from sklearn.preprocessing import normalize
from threadpoolctl import threadpool_limits
from bertopic._bertopic import TopicMapper
from components import *

threadpool_limits(2)
rows = pq.read_table(BASE / 'data/corpus/part-00000.parquet', columns=['title', 'body']).to_pylist()[:1400]
texts = [r['title'] + '. ' + r['body'] for r in rows]
X = np.load(BASE / 'models/embeddings/part-00000.npy')[:len(rows)].astype(np.float32)
P = FrozenProjection(np.zeros(384, dtype=np.float32), np.eye(384, dtype=np.float32)[:64])
Z = P.transform(X)
km = MiniBatchKMeans(n_clusters=500, init=Z[:500], n_init=1, max_iter=2, batch_size=1000, random_state=500).fit(Z)
y = km.predict(Z)
cv = CountVectorizer(max_features=300).fit(texts)
counts = cv.transform(texts)
online = PrecomputedOnlineCountVectorizer(cv.vocabulary_)
bt = StreamingBERTopic(embedding_model=None, language='multilingual', umap_model=P, hdbscan_model=FrozenMiniBatchClusterer(km), vectorizer_model=online, ctfidf_model=FiniteClassTfidf(reduce_frequent_words=True))
bt.topic_mapper_ = TopicMapper(list(range(500)))
bt.topic_representations_ = {i: [('initializing', 0)] for i in range(500)}
bt.topic_sizes_ = {i: 0 for i in range(500)}
for a, b in [(0, 400), (400, 1000), (1000, len(rows))]:
    agg = sparse.csr_matrix((np.ones(b-a, dtype=np.int64), (y[a:b], np.arange(b-a))), shape=(500, b-a))
    online.pending = agg @ counts[a:b]
    bt.partial_fit(texts[a:b], embeddings=X[a:b])
    assert np.array_equal(bt.topics_, y[a:b]), 'Label mapping drift'
agg = sparse.csr_matrix((np.ones(len(y), dtype=np.int64), (y, np.arange(len(y)))), shape=(500, len(y)))
assert (online.X_ != agg @ counts).nnz == 0, 'Streaming counts differ'
assert all(bt.topic_sizes_[i] == int((y == i).sum()) for i in range(500))
assert np.isfinite(bt.c_tf_idf_.data).all()
temp = BASE / 'models/streaming_validation_model.joblib'
joblib.dump(bt, temp)
loaded = joblib.load(temp)
pred, _ = loaded.transform(texts[:20], embeddings=X[:20])
assert np.array_equal(pred, y[:20]), 'Reload predictions changed'
temp.unlink()
dump(BASE / 'models/STREAMING_VALIDATION.json', {'pass': True, 'documents': len(y), 'classes_reserved': 500, 'batches': 3, 'checks': ['missing classes preserve500 row order', 'streaming counts equal direct all-document aggregation', 'fixed labels and cumulative document counts', 'finite c-TF-IDF for initially absent vocabulary', 'serialized/reloaded model produces identical predictions'], 'created_utc': now()})
print('STREAMING_VALIDATION_PASS', flush=True)
