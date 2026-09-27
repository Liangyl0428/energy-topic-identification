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


def current_report_text(text):
    """Normalize cached report prose without changing computed data."""
    replacements={
        '新主题编号F0001–F0500，不继承旧主题语义审核与成熟度等级。':'主题编号F0001–F0500，范围和语义需审核，主题不自动获得成熟度等级。',
        '不复用样本版实验结果或人工审核。':'主题范围和语义需独立审核。',
        'v0.2.1补充时间、对象和判据绑定校验，并修正W011证据解释；':'当前引擎执行时间、对象和判据绑定校验；',
        '证据实验全部重新执行；复用的是评估引擎，不是旧实验结果。':'证据实验通过共用评估引擎执行。',
    }
    for old,new in replacements.items():text=text.replace(old,new)
    return text
