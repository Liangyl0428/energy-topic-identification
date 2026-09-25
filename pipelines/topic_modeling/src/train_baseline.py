from topic_common import *
import time, collections, numpy as np, pandas as pd, joblib
import pyarrow as pa, pyarrow.parquet as pq
from scipy import sparse
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics import pairwise_distances_argmin_min
from sklearn.preprocessing import normalize
from threadpoolctl import threadpool_limits
from bertopic._bertopic import TopicMapper
from components import FrozenProjection, FrozenMiniBatchClusterer, PrecomputedOnlineCountVectorizer, FiniteClassTfidf, StreamingBERTopic
from lexical import analyzer

def main():
    if (BASE / 'models/CLUSTER_AUDIT.json').exists():
        raise RuntimeError('Completed baseline exists; preserve it and use a separate checkout for a new run')
    threadpool_limits(4)
    require(BASE / 'data/INPUT_MANIFEST.json', BASE / 'models/EMBEDDING_AUDIT.json', BASE / 'models/BOW_AUDIT.json')
    (BASE / 'results').mkdir(parents=True, exist_ok=True)
    inp = json.loads((BASE / 'data/INPUT_MANIFEST.json').read_text())
    parts = [BASE / p['file'] for p in inp['parts']]
    N = inp['documents']; K = 500; D = 64
    manifest = {'created_utc': now(), 'bertopic_version': '0.17.3', 'n_clusters': K, 'seed': 500, 'sources_target_training_mass': {'paper': .70, 'patent': .25, 'policy': .05}, 'all_usable_documents_in_fit': True, 'old_401_labels_used': False, 'no_inference_api': True}
    source_ids = {'paper': 0, 'patent': 1, 'policy': 2}
    source = np.empty(N, dtype=np.uint8); usable = np.empty(N, dtype=bool)
    for part in parts:
        t = pq.read_table(part, columns=['row_id', 'source', 'usable']).to_pydict()
        ids = np.array(t['row_id']); source[ids] = [source_ids[s] for s in t['source']]; usable[ids] = t['usable']
    count = np.bincount(source[usable], minlength=3)
    weights_by_source = np.array([.70, .25, .05]) * count[0] / (.70 * count)
    manifest['usable_source_counts'] = {s: int(count[i]) for s, i in source_ids.items()}
    manifest['per_document_training_weights'] = {s: float(weights_by_source[i]) for s, i in source_ids.items()}
    print('TRAINING_INPUT', manifest['usable_source_counts'], manifest['per_document_training_weights'], flush=True)

    projection_file = BASE / 'models/projection.joblib'
    if not projection_file.exists():
        sums = np.zeros(384, dtype=np.float64); outer = np.zeros((384, 384), dtype=np.float64); total_weight = 0
        for part in parts:
            r = pq.read_table(part, columns=['row_id']).column(0).to_numpy(); good = usable[r]
            X = np.load(BASE / 'models/embeddings' / (part.stem + '.npy')).astype(np.float32)[good]
            w = weights_by_source[source[r][good]].astype(np.float32)
            sums += (X * w[:, None]).sum(0, dtype=np.float64)
            outer += (X * w[:, None]).T @ X
            total_weight += float(w.sum(dtype=np.float64))
        mean = sums / total_weight; cov = outer / total_weight - np.outer(mean, mean)
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        projection = FrozenProjection(mean.astype(np.float32), eigenvectors[:, -D:][:, ::-1].T.astype(np.float32))
        joblib.dump(projection, projection_file)
        dump(BASE / 'models/PCA_AUDIT.json', {'dimensions': D, 'all_usable_documents': int(usable.sum()), 'source_weighted': True, 'explained_variance_ratio': float(eigenvalues[-D:].sum() / eigenvalues.sum()), 'no_sampling': True})
    else: projection = joblib.load(projection_file)

    reduced_file = BASE / 'models/reduced.npy'
    if not reduced_file.exists():
        Z = np.lib.format.open_memmap(reduced_file.with_suffix('.partial.npy'), mode='w+', dtype=np.float32, shape=(N, D))
        for part in parts:
            r = pq.read_table(part, columns=['row_id']).column(0).to_numpy()
            X = np.load(BASE / 'models/embeddings' / (part.stem + '.npy')).astype(np.float32)
            Z[r] = projection.transform(X)
        Z.flush(); del Z
        reduced_file.with_suffix('.partial.npy').replace(reduced_file)
    Z = np.load(reduced_file, mmap_mode='r')
    km_file = BASE / 'models/kmeans500.joblib'
    rng = np.random.default_rng(500)
    if not km_file.exists():
        initial = np.concatenate([rng.choice(np.flatnonzero((source == i) & usable), min(int(q * 100000), int(count[i])), replace=False) for i, q in enumerate([.70, .25, .05])])
        rng.shuffle(initial)
        km = MiniBatchKMeans(n_clusters=K, batch_size=4096, init_size=50000, n_init=3, max_iter=60, max_no_improvement=15, reassignment_ratio=.001, random_state=500)
        print('INITIALIZING', len(initial), now(), flush=True)
        km.fit(np.array(Z[initial]))
        all_ids = np.flatnonzero(usable)
        for epoch in range(3):
            order = rng.permutation(all_ids)
            for j in range(0, len(order), 8192):
                ix = order[j:j+8192]
                km.partial_fit(np.array(Z[ix]), sample_weight=weights_by_source[source[ix]].astype(np.float32))
            print('ALL_DOCUMENT_TRAINING_PASS', epoch + 1, len(order), now(), flush=True)
            dump(BASE / 'PROGRESS.json', {'stage': 'clustering', 'all_document_passes': epoch + 1, 'usable_documents': int(usable.sum()), 'updated_utc': now()})
        joblib.dump(km, km_file)
    else: km = joblib.load(km_file)

    labels = np.full(N, -2, dtype=np.int16)
    secondary = np.full(N, -2, dtype=np.int16)
    margin = np.full(N, np.nan, dtype=np.float32)
    raw_sum = np.zeros((K, 384), dtype=np.float64); raw_mass = np.zeros(K, dtype=np.float64)
    source_counts = np.zeros((K, 3), dtype=np.int64)
    numerical_ties = 0
    for part in parts:
        ids = pq.read_table(part, columns=['row_id']).column(0).to_numpy(); good = usable[ids]; ix = ids[good]
        X = np.load(BASE / 'models/embeddings' / (part.stem + '.npy')).astype(np.float32)[good]
        distances = ((Z[ix] ** 2).sum(1)[:, None] + (km.cluster_centers_ ** 2).sum(1)[None, :] - 2 * Z[ix] @ km.cluster_centers_.T)
        top = np.argpartition(distances, kth=1, axis=1)[:, :2]
        values = np.take_along_axis(distances, top, axis=1); order = np.argsort(values, axis=1)
        top = np.take_along_axis(top, order, axis=1); values = np.take_along_axis(values, order, axis=1)
        predicted = km.predict(np.array(Z[ix]))
        disagreement = predicted != top[:, 0]
        if disagreement.any():
            delta = distances[np.arange(len(ix)), predicted] - values[:, 0]
            assert float(delta[disagreement].max()) < 1e-4, 'Prediction distances inconsistent'
            numerical_ties += int(disagreement.sum())
        primary_distance = distances[np.arange(len(ix)), predicted].copy()
        distances[np.arange(len(ix)), predicted] = np.inf
        second = np.argmin(distances, axis=1)
        labels[ix] = predicted; secondary[ix] = second
        margin[ix] = np.maximum(0, distances[np.arange(len(ix)), second] - primary_distance)
        w = weights_by_source[source[ix]]
        np.add.at(raw_sum, labels[ix], X * w[:, None]); np.add.at(raw_mass, labels[ix], w)
        np.add.at(source_counts, (labels[ix], source[ix]), 1)
    assert len(np.unique(labels[usable])) == K
    raw_centroids = normalize(raw_sum).astype(np.float32)
    np.save(BASE / 'models/topic_centroids.npy', raw_centroids)
    np.save(BASE / 'results/raw_labels.npy', labels)
    np.save(BASE / 'results/secondary_labels.npy', secondary)
    np.save(BASE / 'results/distance_margin.npy', margin)
    np.save(BASE / 'results/source_counts.npy', source_counts)
    dump(BASE / 'results/FIXED_LABELS_READY.json', {'documents':N,'usable':int(usable.sum()),'clusters':500,'created_utc':now()})
    print('FIXED_500_LABELS_READY', int(usable.sum()), now(), flush=True)

    require(BASE / 'models/BOW_AUDIT.json')
    cv = joblib.load(BASE / 'models/vectorizer.joblib')
    online = PrecomputedOnlineCountVectorizer(cv.vocabulary_)
    bt = StreamingBERTopic(language='multilingual', embedding_model=None, umap_model=projection, hdbscan_model=FrozenMiniBatchClusterer(km), vectorizer_model=online, ctfidf_model=FiniteClassTfidf(reduce_frequent_words=True), calculate_probabilities=False, top_n_words=20, verbose=False)
    bt.topic_mapper_ = TopicMapper(list(range(K)))
    bt.topic_representations_ = {i: [('initializing', 0.)] for i in range(K)}
    bt.topic_sizes_ = {i: 0 for i in range(K)}
    for n, part in enumerate(parts):
        rows = pq.read_table(part, columns=['row_id', 'title', 'body']).to_pydict()
        ids = np.array(rows['row_id']); good = usable[ids]; ix = ids[good]; y = labels[ix]
        Xbow = sparse.load_npz(BASE / 'models/bow' / (part.stem + '.npz'))[good]
        aggregation = sparse.csr_matrix((np.ones(len(y), dtype=np.int64), (y, np.arange(len(y)))), shape=(K, len(y)))
        online.pending = aggregation @ Xbow
        texts = [rows['title'][i] + '. ' + rows['body'][i] for i in np.flatnonzero(good)]
        X = np.load(BASE / 'models/embeddings' / (part.stem + '.npy')).astype(np.float32)[good]
        bt.partial_fit(texts, embeddings=X)
        assert np.array_equal(bt.topics_, y)
        if n % 10 == 0: print('BERTOPIC_CTFIDF', n + 1, '/', len(parts), now(), flush=True)
    assert all(bt.topic_sizes_[i] == int(source_counts[i].sum()) for i in range(K))
    assert np.isfinite(bt.c_tf_idf_.data).all()
    bt.topic_embeddings_ = raw_centroids
    bt.topics_ = labels[usable].astype(int).tolist()
    joblib.dump(bt, BASE / 'models/bertopic500.joblib', compress=3)
    sparse.save_npz(BASE / 'models/ctfidf.npz', bt.c_tf_idf_)
    sparse.save_npz(BASE / 'models/class_word_counts.npz', online.X_)
    records = []
    for i in range(K):
        records.append({'raw_topic_id': f'B{i:03d}', 'cluster': i, 'documents': int(source_counts[i].sum()), 'papers': int(source_counts[i, 0]), 'patents_2026': int(source_counts[i, 1]), 'policies': int(source_counts[i, 2]), 'keywords': ' | '.join(w for w, _ in bt.get_topic(i)), 'training_label': bt.topic_labels_[i]})
    pd.DataFrame(records).to_csv(BASE / 'results/raw_500_topics.csv', index=False)
    dump(BASE / 'results/raw_500_topics.json', records)
    manifest.update({'documents': N, 'assigned_usable_documents': int(usable.sum()), 'unusable_text_documents': int((~usable).sum()), 'all_document_training_passes': 3, 'initialization_sample_only': len(initial) if 'initial' in locals() else 'cached', 'dimensionality_reduction': 'source-weighted PCA64 from covariance of all usable document vectors, followed by L2 normalization', 'clustering': 'MiniBatchKMeans500; stratified initialization, then3 shuffled full passes with source weights; frozen predictions during exact streaming BERTopic c-TF-IDF pass', 'ctfidf': 'all title+body counts in fixed vocabulary, no document or class sampling; source weights apply to clustering only, not reported counts', 'unusable_label': -2, 'assignment_is_not_accuracy': True, 'completed_utc': now()})
    manifest['float32_nearest_distance_ties_using_model_prediction'] = numerical_ties
    dump(BASE / 'models/CLUSTER_AUDIT.json', manifest)
    dump(BASE / 'PROGRESS.json', {'stage': '500_clusters_ready_for_review', 'documents': N, 'clusters': K, 'updated_utc': now()})
    print('CLUSTERING_COMPLETE', now(), flush=True)


if __name__ == '__main__':
    main()
