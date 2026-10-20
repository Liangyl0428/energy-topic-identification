"""Independent full-pass release; existing R2 data is always read only."""
from pathlib import Path
import hashlib
import json
import duckdb
import pandas as pd

import sys
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from runtime_config import load_runtime
RUNTIME = load_runtime()
ROOT = RUNTIME.path('data_root')
WORK = ROOT / 'work/keyword_dictionary_continuous_review_20261020'
BASELINE = ROOT / 'work/keyword_dictionary_semantic_review_20261019_r2'
ASSETS = ROOT / 'final/assets/keyword_dictionary_full_review'
CORPUS = RUNTIME.path('corpus_dir')
FROZEN = RUNTIME.path('classification_run')


def read(path):
    return json.loads(Path(path).read_text())


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def connect():
    c = duckdb.connect(str(WORK / 'dictionary.duckdb'))
    c.execute('SET threads=4')
    c.execute("SET memory_limit='6GB'")
    c.execute('SET preserve_insertion_order=false')
    (WORK / 'tmp').mkdir(exist_ok=True)
    c.execute('SET temp_directory=?', [str(WORK / 'tmp')])
    baseline_path = str(BASELINE / 'dictionary.duckdb').replace("'", "''")
    c.execute(f"ATTACH '{baseline_path}' AS baseline (READ_ONLY)")
    return c
