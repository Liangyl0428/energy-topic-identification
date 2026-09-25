from common import *
import time, numpy as np, duckdb
from tokenizers import Tokenizer
import onnxruntime as ort

M = BASE / 'models/multilingual_minilm'
tok = Tokenizer.from_file(str(M / 'tokenizer.json'))
opt = ort.SessionOptions(); opt.intra_op_num_threads = 4; opt.inter_op_num_threads = 1
opt.enable_mem_pattern = False
sess = ort.InferenceSession(str(M / 'onnx/model_O4.onnx'), sess_options=opt, providers=[('CUDAExecutionProvider', {'gpu_mem_limit': 18000 * 1024**2, 'arena_extend_strategy': 'kSameAsRequested'}), 'CPUExecutionProvider'])
assert sess.get_providers()[0] == 'CUDAExecutionProvider', sess.get_providers()
print('providers', sess.get_providers(), flush=True)
c = duckdb.connect(str(ROOT / 'analyze/data/independent_corpus.duckdb'), read_only=True)
rows = c.execute('SELECT clean_text FROM works USING SAMPLE 4096 ROWS (reservoir, 500)').fetchall()
c.close(); texts = [r[0] for r in rows]
results = []
for length in [128, 256]:
    tok.enable_truncation(max_length=length); tok.enable_padding(pad_id=1, pad_token='<pad>', length=length)
    enc = tok.encode_batch(texts)
    feed = {'input_ids': np.array([e.ids for e in enc], dtype=np.int64), 'attention_mask': np.array([e.attention_mask for e in enc], dtype=np.int64), 'token_type_ids': np.array([e.type_ids for e in enc], dtype=np.int64)}
    for bs in [64, 128, 256]:
        sess.run(None, {k: v[:bs] for k, v in feed.items()})
        t = time.perf_counter()
        for i in range(0, len(texts), bs):
            f = {k: v[i:i+bs] for k, v in feed.items()}
            h = sess.run(None, f)[0]
            mask = f['attention_mask'][..., None]
            emb = (h * mask).sum(1) / mask.sum(1)
            assert np.isfinite(emb).all()
        sec = time.perf_counter() - t
        row = {'tokens': length, 'batch': bs, 'documents': len(texts), 'seconds': sec, 'docs_per_second': len(texts) / sec}
        results.append(row); print(row, flush=True)
dump(BASE / 'models/ENCODER_BENCHMARK.json', results)
