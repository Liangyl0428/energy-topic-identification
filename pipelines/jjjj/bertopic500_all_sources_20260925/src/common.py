from pathlib import Path
import os, sys, json, hashlib, re, unicodedata, datetime

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
sys.path[:0] = [str(ROOT / 'aaaa/bge_m3/_runtime'), str(ROOT / 'aaaa/bge_m3/_core'), str(ROOT / 'cccc/_deps'), str(ROOT / 'bbbb/_deps')]
os.environ.setdefault('OMP_NUM_THREADS', '4')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '4')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'true')
os.environ.setdefault('RAYON_NUM_THREADS', '2')

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def dump(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')
    tmp.replace(path)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(b)
    return h.hexdigest()

def clean(value):
    if not value:
        return ''
    text = unicodedata.normalize('NFKC', str(value))
    return re.sub(r'\s+', ' ', text).strip()

def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def normalize_date(value):
    text=clean(value)
    if re.fullmatch(r'\d{8}',text):text=text[:4]+'-'+text[4:6]+'-'+text[6:8]
    return text[:10]
