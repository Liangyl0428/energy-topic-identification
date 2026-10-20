"""Versioned keyword dictionary classification; no NMF or semantic transfer."""
from pathlib import Path
import json, hashlib, re, unicodedata
import pandas as pd
import duckdb

import sys
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from runtime_config import load_runtime
RUNTIME = load_runtime()
ROOT = RUNTIME.path('data_root')
WORK=ROOT/'work/keyword_dictionary_semantic_review_20261019_r2'
ASSETS=ROOT/'final/assets/keyword_dictionary_semantic_review_r2'
FROZEN = RUNTIME.path('classification_run')
CORPUS = RUNTIME.path('corpus_dir')
HERE=Path(__file__).resolve().parent
WORK.mkdir(parents=True,exist_ok=True)

def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def normalize(text):
    value=unicodedata.normalize('NFKC',str(text or '')).casefold().strip()
    value=re.sub(r'[-‐‑‒–—−]', ' ',value)
    return re.sub(r'\s+',' ',value).strip()

def connect():
    c=duckdb.connect(str(WORK/'dictionary.duckdb'))
    c.execute('SET threads=4');c.execute('SET preserve_insertion_order=false');c.execute("SET memory_limit='6GB'")
    (WORK/'tmp').mkdir(exist_ok=True)
    c.execute('SET temp_directory=?',[str(WORK/'tmp')])
    return c
