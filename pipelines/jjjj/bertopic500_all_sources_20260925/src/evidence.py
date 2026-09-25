"""Full assignments and reproducible center/random/boundary evidence for review."""
from common import *
import time, heapq, collections, numpy as np, pandas as pd
import pyarrow as pa, pyarrow.parquet as pq
from scipy import sparse
from sklearn.preprocessing import normalize

while not (BASE / 'results/FIXED_LABELS_READY.json').exists(): time.sleep(3)
inp = json.loads((BASE / 'data/INPUT_MANIFEST.json').read_text())
parts = [BASE / p['file'] for p in inp['parts']]
labels = np.load(BASE / 'results/raw_labels.npy', mmap_mode='r')
secondary = np.load(BASE / 'results/secondary_labels.npy', mmap_mode='r')
margin = np.load(BASE / 'results/distance_margin.npy', mmap_mode='r')
centers = np.load(BASE / 'models/topic_centroids.npy')
counts = np.load(BASE / 'results/source_counts.npy')
source_codes = {'paper': 0, 'patent': 1, 'policy': 2}
heaps = collections.defaultdict(list)
cos_sum = np.zeros(500); cos_sq = np.zeros(500); low_cos = np.zeros(500, dtype=np.int64); low_gap = np.zeros(500, dtype=np.int64)
title_only = np.zeros(500, dtype=np.int64); retracted = np.zeros(500, dtype=np.int64); template = np.zeros(500, dtype=np.int64)
boundary_flow = np.zeros((500, 500), dtype=np.int64)
years = collections.Counter()
out = BASE / 'results/assignments'; out.mkdir(exist_ok=True)

def keep(key, score, rowid, n):
    item = (float(score), int(rowid)); h = heaps[key]
    if len(h) < n: heapq.heappush(h, item)
    elif item > h[0]: heapq.heapreplace(h, item)

for p, part in enumerate(parts):
    table = pq.read_table(part); d = table.to_pydict()
    ids = np.array(d['row_id']); lab = np.asarray(labels[ids]); good = lab >= 0
    X = np.load(BASE / 'models/embeddings' / (part.stem + '.npy')).astype(np.float32)
    X /= np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)
    cosine = np.full(len(ids), np.nan, dtype=np.float32)
    cosine[good] = np.einsum('ij,ij->i', X[good], centers[lab[good]])
    sc = np.array([source_codes[s] for s in d['source']])
    y = lab[good]; ix = ids[good]; sim = cosine[good]; gap = np.asarray(margin[ix])
    cos_sum += np.bincount(y, weights=sim, minlength=500); cos_sq += np.bincount(y, weights=sim**2, minlength=500)
    low_cos += np.bincount(y[sim < .45], minlength=500); low_gap += np.bincount(y[gap < .02], minlength=500)
    for key, target in [('title_only', title_only), ('retracted', retracted), ('template_record', template)]:
        target += np.bincount(lab[good & np.array(d[key])], minlength=500)
    np.add.at(boundary_flow, (y[gap < .02], np.asarray(secondary[ix])[gap < .02]), 1)
    group = y * 3 + sc[good]
    order = np.argsort(group, kind='stable')
    boundaries = np.r_[0, np.flatnonzero(np.diff(group[order])) + 1, len(order)]
    # SplitMix64 gives a reproducible label-independent random priority.
    random = ix.astype(np.uint64) + np.uint64(500)
    random = (random ^ (random >> np.uint64(30))) * np.uint64(0xbf58476d1ce4e5b9)
    random = (random ^ (random >> np.uint64(27))) * np.uint64(0x94d049bb133111eb)
    random = random ^ (random >> np.uint64(31))
    for start, stop in zip(boundaries[:-1], boundaries[1:]):
        loc = order[start:stop]
        if not len(loc): continue
        cluster, s = divmod(int(group[loc[0]]), 3)
        for role, score, n in [('center', sim[loc], 5), ('random', random[loc].astype(np.float64), 3), ('boundary', -gap[loc], 3), ('far', -sim[loc], 3)]:
            chosen = np.argsort(score)[-n:]
            for j in chosen: keep((cluster, s, role), score[j], ix[loc[j]], n)
    for y0, date0, s0 in zip(lab, d['date'], d['source']):
        if y0 >= 0: years[(int(y0), s0, date0[:4] if date0 else 'unknown')] += 1
    assignment = pa.table({'row_id': ids, 'doc_id': d['doc_id'], 'source': d['source'], 'date': d['date'], 'raw_cluster': lab, 'raw_topic_id': [f'B{x:03d}' if x >= 0 else 'UNUSABLE' for x in lab], 'secondary_candidate': np.asarray(secondary[ids]), 'distance_margin': np.asarray(margin[ids]), 'cosine_to_centroid': cosine, 'title_only': d['title_only'], 'retracted': d['retracted'], 'template_record': d['template_record'], 'quality_note': d['quality_note']})
    pq.write_table(assignment, out / part.name, compression='zstd')
    if p % 20 == 0: print('ASSIGNMENTS_AND_EVIDENCE', p+1, len(parts), flush=True)

selection = collections.defaultdict(list)
for (cluster, s, role), heap in heaps.items():
    for rank, (score, rid) in enumerate(sorted(heap, reverse=True), 1):
        selection[rid].append({'cluster': cluster, 'source': s, 'role': role, 'rank': rank})
evidence = []
for part in parts:
    table = pq.read_table(part)
    ids = table.column('row_id').to_numpy()
    positions = [i for i, rid in enumerate(ids) if int(rid) in selection]
    if not positions: continue
    for row in table.take(pa.array(positions)).to_pylist():
        rid = row['row_id']; row['cluster'] = int(labels[rid]); row['raw_topic_id'] = f'B{labels[rid]:03d}'
        row['selection_roles'] = '|'.join(f"{x['role']}:{x['rank']}" for x in selection[rid])
        row['secondary_candidate'] = int(secondary[rid]); row['distance_margin'] = float(margin[rid])
        evidence.append(row)
pq.write_table(pa.Table.from_pylist(evidence), BASE / 'evidence/review_documents.parquet', compression='zstd')
with (BASE / 'evidence/review_documents.jsonl').open('w') as f:
    for row in evidence: f.write(json.dumps(row, ensure_ascii=False) + '\n')

while not (BASE / 'results/raw_500_topics.csv').exists(): time.sleep(3)
raw = pd.read_csv(BASE / 'results/raw_500_topics.csv')
totals = counts.sum(1)
raw['mean_cosine'] = cos_sum / totals
raw['std_cosine'] = np.sqrt(np.maximum(0, cos_sq/totals - (cos_sum/totals)**2))
raw['cosine_below_045'] = low_cos
raw['margin_below_002'] = low_gap
raw['title_only_documents'] = title_only
raw['retracted_documents'] = retracted
raw['template_documents'] = template
raw.to_csv(BASE / 'results/raw_500_topics.csv', index=False)
pd.DataFrame([dict(cluster=k[0], source=k[1], year=k[2], documents=v) for k,v in years.items()]).to_csv(BASE / 'results/raw_topic_year_counts.csv', index=False)

wordvec = normalize(sparse.load_npz(BASE / 'models/ctfidf.npz'))
lexsim = (wordvec @ wordvec.T).toarray()
semantic = centers @ centers.T
pairs = []
for i in range(500):
    top = set(np.argsort(semantic[i])[-9:]) | set(np.argsort(lexsim[i])[-5:])
    for j in top:
        if j <= i: continue
        pairs.append({'a': f'B{i:03d}', 'b': f'B{j:03d}', 'semantic_cosine': float(semantic[i,j]), 'ctfidf_cosine': float(lexsim[i,j]), 'boundary_flow': int(boundary_flow[i,j]+boundary_flow[j,i]), 'keywords_a': raw.iloc[i].keywords, 'keywords_b': raw.iloc[j].keywords})
pd.DataFrame(pairs).sort_values('semantic_cosine', ascending=False).to_csv(BASE / 'evidence/merge_candidates.csv', index=False)

by_cluster = collections.defaultdict(list)
for e in evidence: by_cluster[e['cluster']].append(e)
compact = []
for r in raw.to_dict('records'):
    es = by_cluster[r['cluster']]
    keep_rows = []
    for s in ['paper', 'patent', 'policy']:
        for role in ['center:1', 'random:1']:
            matches = [e for e in es if e['source'] == s and role in e['selection_roles'].split('|')]
            for e in matches: keep_rows.append({'row_id': e['row_id'], 'source': s, 'role': role, 'title': e['title'], 'body_preview': e['body'][:500]})
    compact.append({**r, 'examples': keep_rows})
dump(BASE / 'evidence/cluster_review_cards.json', compact)
dump(BASE / 'evidence/EVIDENCE_AUDIT.json', {'created_utc': now(), 'raw_clusters': 500, 'documents_with_saved_assignments': len(labels), 'unique_evidence_documents': len(evidence), 'sampling_per_cluster_per_source': {'center': 5, 'random': 3, 'boundary': 3, 'far': 3}, 'geometry_is_not_calibrated_accuracy': True, 'candidate_pairs_are_not_merge_decisions': True})
print('REVIEW_EVIDENCE_READY', len(evidence), now(), flush=True)
