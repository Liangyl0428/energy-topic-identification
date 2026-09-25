"""Independent K=1000 experiment; SOURCE is read-only input."""
from pathlib import Path
import os, sys, json, hashlib, re, unicodedata, datetime

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
SOURCE = ROOT / 'jjjj/bertopic500_all_sources_20260925'
sys.path[:0] = [str(ROOT / 'aaaa/bge_m3/_runtime'), str(ROOT / 'aaaa/bge_m3/_core'), str(ROOT / 'cccc/_deps'), str(ROOT / 'bbbb/_deps')]
sys.path.append(str(SOURCE / 'src'))
os.environ.setdefault('OMP_NUM_THREADS', '4')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '4')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
K = 1000
SEED = 500

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False, default=str) + '\n', encoding='utf-8')
    tmp.replace(path)

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(chunk)
    return h.hexdigest()

def clean(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', str(value or ''))).strip()

def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def progress(stage, **values):
    payload = {'stage':stage, 'updated_utc':now(), **values}
    dump(BASE/'PROGRESS.json', payload)
    print(json.dumps(payload, ensure_ascii=False), flush=True)
