from common import *
import requests, time
REPO = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
REV = 'e8f8c211226b894fcb81acc59f3b34ba3efd5f42'
M = BASE / 'models/multilingual_minilm'
files = ['onnx/model_O4.onnx', 'tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json', 'sentence_bert_config.json', '1_Pooling/config.json', 'config.json']
manifest = {'repository': REPO, 'revision': REV, 'inference': 'local only; no document upload or model API', 'files': {}, 'created_utc': now()}
for name in files:
    path = M / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        for attempt in range(4):
            try:
                with requests.get(f'https://huggingface.co/{REPO}/resolve/{REV}/{name}', stream=True, timeout=(30, 90)) as response:
                    response.raise_for_status()
                    with path.with_suffix(path.suffix + '.part').open('wb') as out:
                        for chunk in response.iter_content(1024**2):
                            out.write(chunk)
                path.with_suffix(path.suffix + '.part').replace(path)
                break
            except Exception:
                if attempt == 3: raise
                time.sleep(2)
    manifest['files'][name] = {'sha256': sha(path), 'bytes': path.stat().st_size}
    print('READY', name, path.stat().st_size, flush=True)
dump(BASE / 'models/DOWNLOAD_MANIFEST.json', manifest)
