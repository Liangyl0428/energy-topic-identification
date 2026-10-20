"""Small, deterministic contracts shared by the P1 delivery exporters."""
import hashlib
import json
from pathlib import Path
import pandas as pd

TAXONOMY = 'full_nmf500_20260926'
VERSION = 'energy_business_p1_20261018'
REVIEWER = 'assistant_source_review_20261018'
WINDOWS = {
    'history': ['2021-07-01', '2026-06-30'],
    'core': ['2023-07-01', '2026-06-30'],
    'recent': ['2025-07-01', '2026-06-30'],
    'previous': ['2024-07-01', '2025-06-30'],
    'baseline': ['2022-07-01', '2025-06-30'],
    'cross_source': ['2026-01-01', '2026-06-30'],
}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def table(path, rows):
    """JSON is the typed API; CSV encodes nested structures as JSON cells."""
    path = Path(path)
    write(path.with_suffix('.json'), rows)
    flat = [{k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
             for k, v in row.items()} for row in rows]
    pd.DataFrame(flat).to_csv(path.with_suffix('.csv'), index=False, encoding='utf-8-sig')


def evidence_ref(module, filename, key, fields=None):
    return {'artifact': f'{module}/assets/full_nmf500/{filename}',
            'record_key': key, 'fields': fields or []}
