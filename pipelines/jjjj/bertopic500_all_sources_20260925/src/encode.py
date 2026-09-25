"""Encode every usable document locally; all body tokens participate via chunks."""
from common import *
import time, numpy as np, pyarrow as pa, pyarrow.parquet as pq
from tokenizers import Tokenizer
import onnxruntime as ort

M = BASE / 'models/multilingual_minilm'
OUT = BASE / 'models/embeddings'
OUT.mkdir(exist_ok=True)
tok = Tokenizer.from_file(str(M / 'tokenizer.json'))
tok.no_padding(); tok.no_truncation()
opt = ort.SessionOptions(); opt.intra_op_num_threads = 1; opt.inter_op_num_threads = 1
opt.add_session_config_entry('session.intra_op.allow_spinning', '0')
opt.add_session_config_entry('session.inter_op.allow_spinning', '0')
opt.enable_mem_pattern = False; opt.log_severity_level = 3
sess = ort.InferenceSession(str(M / 'onnx/model_O4_pooled.onnx'), sess_options=opt, providers=[('CUDAExecutionProvider', {'gpu_mem_limit': 16000 * 1024**2, 'arena_extend_strategy': 'kSameAsRequested'}), 'CPUExecutionProvider'])
assert sess.get_providers()[0] == 'CUDAExecutionProvider', sess.get_providers()

def run_sequences(sequences):
    lengths = np.array([len(x) for x in sequences])
    order = np.argsort(lengths, kind='stable')
    output = np.empty((len(sequences), 384), dtype=np.float32)
    for i in range(0, len(order), 16):
        ix = order[i:i+16]
        length = int((lengths[ix].max() + 15) // 16 * 16)
        ids = np.ones((len(ix), length), dtype=np.int64)
        mask = np.zeros_like(ids)
        for j, k in enumerate(ix):
            ids[j, :lengths[k]] = sequences[k]; mask[j, :lengths[k]] = 1
        feed = {'input_ids': ids, 'attention_mask': mask, 'token_type_ids': np.zeros_like(ids)}
        v = sess.run(['sentence_embedding'], feed)[0]
        assert np.isfinite(v).all()
        output[ix] = v
    return output

# Verify appended GPU pooling against the official output on different languages.
example_texts = ['Lithium-ion battery state-of-health estimation using impedance spectroscopy.', '关于新型储能参与电力现货市场的通知', '风电机组齿轮箱故障诊断与状态监测', 'Electricity price forecasting and day-ahead bidding.']
examples = [e.ids for e in tok.encode_batch(example_texts)]
pooled = run_sequences(examples)
raw_sess = ort.InferenceSession(str(M / 'onnx/model_O4.onnx'), sess_options=opt, providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
length = max(map(len, examples)); ids = np.ones((4, length), dtype=np.int64); mask = np.zeros_like(ids)
for i, e in enumerate(examples): ids[i, :len(e)] = e; mask[i, :len(e)] = 1
h = raw_sess.run(None, {'input_ids': ids, 'attention_mask': mask, 'token_type_ids': np.zeros_like(ids)})[0]
reference = (h * mask[..., None]).sum(1) / mask.sum(1)[:, None]
reference /= np.linalg.norm(reference, axis=1, keepdims=True)
pool_error = float(np.max(np.abs(reference - pooled)))
assert pool_error < .003, pool_error
del raw_sess
dump(BASE / 'models/POOL_VALIDATION.json', {'maximum_absolute_difference': pool_error, 'threshold': .003, 'pass': True, 'languages': ['en', 'zh']})

def iter_parts():
    index = 0
    while True:
        path = BASE / 'data/corpus' / f'part-{index:05d}.parquet'
        if path.exists():
            yield path; index += 1
        elif (BASE / 'data/INPUT_MANIFEST.json').exists():
            expected = json.loads((BASE / 'data/INPUT_MANIFEST.json').read_text())
            assert index == len(expected['parts'])
            break
        else:
            time.sleep(2)

def prepare_part(part):
    prep_start=time.time()
    rows = pq.read_table(part).to_pylist()
    # Encode with no truncation; no text is sent outside this process.
    texts = [x for r in rows for x in (r['title'], r['body'])]
    encoded = tok.encode_batch(texts, add_special_tokens=False)
    seq = []; owners = []; weights = []; chunk_counts = []; token_counts = []
    for i, r in enumerate(rows):
        title = encoded[i*2].ids; body = encoded[i*2+1].ids
        token_counts.append(len(title) + len(body))
        if not r['usable']:
            chunk_counts.append(0); continue
        if len(title) + len(body) <= 125:
            seq.append([0] + title + ([2] if body else []) + body + [2]); owners.append(i); weights.append(max(1, len(title) + len(body))); chunk_counts.append(1)
        else:
            prefix = title[:24]
            remaining = title[24:] + body
            width = 125 - len(prefix)
            n = 0
            covered = 0
            for j in range(0, len(remaining), width):
                piece = remaining[j:j+width]
                newly = len(piece) + (len(prefix) if j == 0 else 0)
                weight = newly
                if r['source'] == 'policy':
                    total_tokens = len(title) + len(body)
                    main_tokens = min(total_tokens, 4096)
                    main_new = min(newly, max(0, main_tokens-covered))
                    weight = .4*newly/total_tokens + .6*main_new/main_tokens
                seq.append([0] + prefix + [2] + piece + [2]); owners.append(i); weights.append(weight); n += 1; covered += newly
            if n == 0:
                seq.append([0] + prefix + [2]); owners.append(i); weights.append(len(prefix)); n = 1
            chunk_counts.append(n)
    return rows, seq, owners, weights, chunk_counts, token_counts, time.time()-prep_start

from concurrent.futures import ThreadPoolExecutor
start = time.time(); completed = []; totals = {'documents': 0, 'chunks': 0, 'content_tokens': 0, 'unusable_documents': 0}
pending=[]
for part in iter_parts():
    out=OUT/(part.stem+'.npy');meta_path=OUT/(part.stem+'.json')
    if out.exists() and meta_path.exists():
        meta=json.loads(meta_path.read_text());assert meta['corpus_sha256']==sha(part)
        for k in totals:totals[k]+=meta[k]
        completed.append(part.stem)
    else:pending.append(part)
with ThreadPoolExecutor(max_workers=1) as executor:
    future=executor.submit(prepare_part,pending[0]) if pending else None
    for index,part in enumerate(pending):
        t=time.time();out=OUT/(part.stem+'.npy');meta_path=OUT/(part.stem+'.json')
        rows,seq,owners,weights,chunk_counts,token_counts,preparation_seconds=future.result()
        if index+1<len(pending):future=executor.submit(prepare_part,pending[index+1])
        inference_start=time.time()
        vec = run_sequences(seq)
        inference_seconds=time.time()-inference_start
        emb = np.zeros((len(rows), 384), dtype=np.float32)
        np.add.at(emb, np.array(owners), vec * np.array(weights, dtype=np.float32)[:, None])
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        usable = np.array([r['usable'] for r in rows])
        assert (norms[usable] > 0).all()
        emb /= np.maximum(norms, 1e-12)
        tmp = out.with_suffix('.partial.npy'); np.save(tmp, emb.astype(np.float16)); tmp.replace(out)
        chunk_file = OUT / (part.stem + '_lengths.parquet')
        pq.write_table(pa.table({'row_id': [r['row_id'] for r in rows], 'content_tokens': token_counts, 'chunks': chunk_counts}), chunk_file, compression='zstd')
        meta = {'documents': len(rows), 'chunks': len(seq), 'content_tokens': int(sum(token_counts)), 'unusable_documents': int(sum(not r['usable'] for r in rows)), 'seconds': time.time()-t, 'preparation_seconds': preparation_seconds, 'inference_seconds': inference_seconds, 'corpus_sha256': sha(part), 'embedding_sha256': sha(out), 'created_utc': now()}
        dump(meta_path, meta)
        for k in totals: totals[k] += meta[k]
        completed.append(part.stem)
        dump(BASE / 'PROGRESS.json', {'stage': 'encoding', 'last_part': part.stem, **totals, 'seconds_current_run': time.time()-start, 'updated_utc': now()})
        print(part.stem, meta['documents'], 'chunks', meta['chunks'], 'sec', round(meta['seconds'], 1), 'prep', round(preparation_seconds,1), 'infer', round(inference_seconds,1), 'total_docs', totals['documents'], flush=True)
manifest = json.loads((BASE / 'data/INPUT_MANIFEST.json').read_text())
assert totals['documents'] == manifest['documents'], (totals, manifest['documents'])
dump(BASE / 'models/EMBEDDING_AUDIT.json', {'model': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', 'revision': 'e8f8c211226b894fcb81acc59f3b34ba3efd5f42', 'dimensions': 384, 'saved_dtype': 'float16', 'model_precision': 'official O4 FP16 encoder', 'max_tokens_per_chunk': 128, 'text_view': 'all title and body tokens; title prefix up to24 repeated per chunk; non-overlapping body chunks; normalized masked-mean chunk vectors weighted by newly covered token count, then normalized document vector; policy vectors mix60% first4096-token narrative and40% full text so massive numeric annexes do not erase policy intent', 'body_tokens_discarded': 0, 'input_sha256': sha(BASE / 'data/INPUT_MANIFEST.json'), 'providers': sess.get_providers(), 'pool_validation_max_abs_error': pool_error, 'parts': completed, **totals, 'completed_utc': now(), 'seconds_current_run': time.time()-start})
print('ENCODING_COMPLETE', totals, flush=True)
