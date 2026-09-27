"""Paths and atomic audit output for the full-corpus release."""
from pathlib import Path
import hashlib
import json
import os

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO.parent
RUN = Path(os.environ.get('FULL_NMF_RUN', REPO / 'work/full_nmf500_20260926'))
CORPUS = ROOT / 'jjjj/bertopic500_all_sources_20260925/data/corpus'
K = 500


def dump(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(chunk)
    return h.hexdigest()


def parts():
    return sorted(CORPUS.glob('part-*.parquet'))
