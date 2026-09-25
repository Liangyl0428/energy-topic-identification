from pathlib import Path
import sys, os, json, hashlib, datetime
BASE=Path(__file__).resolve().parents[1]
ROOT=BASE.parents[1]
RAW=ROOT/'jjjj/bertopic1000_all_sources_20260925'
CORPUS=ROOT/'jjjj/bertopic500_all_sources_20260925'
sys.path[:0]=[str(ROOT/'aaaa/bge_m3/_runtime'),str(ROOT/'aaaa/bge_m3/_core'),str(ROOT/'cccc/_deps'),str(ROOT/'bbbb/_deps')]
os.environ.setdefault('OMP_NUM_THREADS','4')
os.environ.setdefault('OPENBLAS_NUM_THREADS','4')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text())
def dump(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n');tmp.replace(p)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
