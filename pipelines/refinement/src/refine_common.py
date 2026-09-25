from pathlib import Path
import sys, os, json, hashlib, datetime, re, unicodedata
BASE=Path(__file__).resolve().parents[1]
ROOT=BASE.parents[1]
# Frozen upstream inputs; the historical training pipelines are not required here.
OLD=ROOT/'inputs/baseline'
NEW=ROOT/'inputs/candidates'
os.environ.setdefault('OMP_NUM_THREADS','4')
os.environ.setdefault('OPENBLAS_NUM_THREADS','4')
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text())
def dump(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n');tmp.replace(p)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()
def clean(s):return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(s or ''))).strip()
def progress(stage,**kw):
    d=dict(stage=stage,updated_utc=now(),**kw);dump(BASE/'PROGRESS.json',d);print(json.dumps(d,ensure_ascii=False),flush=True)
for sub in ['results','results/assignments','results/text_corrections','review','evidence','models','logs']:
    (BASE/sub).mkdir(parents=True,exist_ok=True)
