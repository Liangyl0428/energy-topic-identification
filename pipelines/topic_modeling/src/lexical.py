"""Streaming, reproducible lexical features for BERTopic c-TF-IDF."""
from topic_common import *
import time, numpy as np, joblib, jieba, collections, multiprocessing as mp
import pyarrow.parquet as pq
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS
jieba.setLogLevel(40)
STOP = set(ENGLISH_STOP_WORDS) | set('研究 方法 进行 通过 提供 包括 所述 其中 一种 本发明 本实用新型 本文 以及 关于 有关 通知 印发 规定 工作 要求 应当 可以 实施 根据 进一步 推进 加强 做好 有效 相关 主要 具有 实现 提高 采用 结果 表明 分析 技术 公开 申请 涉及 用于 设置 设置有 分别 第一 第二 第三 至少 连接 说明 附图 实施例 上述 本申请 其特征 其特征在于 study studies paper proposed result results using based present presents approach method methods respectively fig figure shown also new used use obtained however et al author copyright rights reserved'.split())
TOKEN = re.compile(r'[\u4e00-\u9fff]+|[^\W\d_][\w]*(?:[-/][\w]+)*', re.UNICODE)
ZH = re.compile(r'[\u4e00-\u9fff]')

def analyzer(text):
    # Segment only Chinese; preserve scientific Latin abbreviations and numbers
    # inside terms. Sentence boundaries prevent cross-document bigrams.
    for sentence in re.split(r'[.!?。！？;；\n]+', str(text).lower()):
        words = []
        for token in TOKEN.findall(sentence):
            words.extend(jieba.lcut(token, HMM=False) if ZH.search(token) else token.replace('-', ' ').split())
        for i, word in enumerate(words):
            if word in STOP or len(word) < 2: continue
            yield word
            if i + 1 < len(words) and words[i+1] not in STOP and len(words[i+1]) >= 2:
                yield word + ' ' + words[i+1]

def texts_for(part):
    d = pq.read_table(part, columns=['title', 'body']).to_pydict()
    return [a + '. ' + b for a, b in zip(d['title'], d['body'])]

def vocabulary_view(title, body):
    # Vocabulary selection only: a multi-million-character project annex must
    # not outweigh thousands of ordinary documents when selecting features.
    # Full text counts are still computed by process_part/texts_for.
    if len(body)>4000:
        middle=len(body)//2
        body=body[:2000]+' . '+body[middle-500:middle+500]+' . '+body[-1000:]
    return title+'. '+body

def process_part(path):
    part = Path(path); dest = BASE / 'models/bow' / (part.stem + '.npz')
    meta_path = dest.with_suffix('.json')
    if dest.exists() and meta_path.exists():
        meta=json.loads(meta_path.read_text())
        assert meta['input_sha256']==sha(part), 'Input changed; rebuild lexical counts'
        return meta
    vectorizer = joblib.load(BASE / 'models/vectorizer.joblib')
    start = time.time(); texts = texts_for(part)
    x = vectorizer.transform(texts).astype(np.int32)
    sparse.save_npz(dest.with_suffix('.partial.npz'), x, compressed=True)
    dest.with_suffix('.partial.npz').replace(dest)
    meta = {'part': part.stem, 'documents': len(texts), 'nnz': x.nnz, 'vocabulary_features': x.shape[1], 'seconds': time.time()-start, 'input_sha256': sha(part)}
    dump(meta_path, meta)
    return meta

if __name__ == '__main__':
    from lexical import analyzer as stable_analyzer
    require(BASE / 'data/INPUT_MANIFEST.json')
    manifest = json.loads((BASE / 'data/INPUT_MANIFEST.json').read_text())
    parts = [BASE / p['file'] for p in manifest['parts']]
    (BASE / 'models/bow').mkdir(parents=True, exist_ok=True)
    vector_file = BASE / 'models/vectorizer.joblib'
    if not vector_file.exists():
        sample = []; by_source = collections.Counter(); rng = np.random.default_rng(500)
        quota = {'paper': 100000, 'patent': 40000, 'policy': 8000}
        for part in parts:
            d = pq.read_table(part, columns=['source', 'title', 'body']).to_pydict()
            source = d['source'][0]
            take = min(len(d['title']), int(np.ceil(len(d['title']) * quota[source] / manifest['source_counts'][source])))
            ix = rng.choice(len(d['title']), take, replace=False)
            sample.extend(vocabulary_view(d['title'][i],d['body'][i]) for i in ix); by_source[source] += len(ix)
        cv = CountVectorizer(analyzer=stable_analyzer, min_df=3, max_features=120000, dtype=np.int32)
        cv.fit(sample); joblib.dump(cv, vector_file)
        dump(BASE / 'models/VOCABULARY_AUDIT.json', {'sample_documents_by_source': dict(by_source), 'features': len(cv.vocabulary_), 'min_document_frequency': 3, 'all_corpus_counts_later': True, 'vocabulary_selection_view': 'title+body; bodies over4000 characters use head2000/middle1000/tail1000, vocabulary selection only to prevent huge numeric annex dominance; final class counts use complete texts', 'stopwords': sorted(STOP), 'analyzer': 'Chinese jieba HMM=False + Unicode technical words; unigram/bigram within sentence', 'vectorizer_sha256': sha(vector_file), 'created_utc': now()})
        print('VOCABULARY_READY', len(cv.vocabulary_), dict(by_source), flush=True)
        del cv, sample
    with mp.get_context('spawn').Pool(4) as pool:
        for meta in pool.imap_unordered(process_part, map(str, parts), chunksize=1):
            print('BOW', meta['part'], meta['nnz'], round(meta['seconds'], 1), flush=True)
    dump(BASE / 'models/BOW_AUDIT.json', {'parts': len(parts), 'documents': manifest['documents'], 'completed_utc': now(), 'count_basis': 'all full title and body text, fixed vocabulary selected before cluster labels'})
