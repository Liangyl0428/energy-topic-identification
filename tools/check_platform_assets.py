"""Verify compact snapshots and explicitly inventoried external Parquet exports."""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1] / 'platform'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            value.update(block)
    return value.hexdigest()


def validate(external_root=None):
    external = {row['path']: row for row in json.loads((ROOT / 'EXTERNAL_FILES.json').read_text())['files']}
    checked, deferred = 0, set()
    for manifest in (ROOT / 'assets').glob('*/RELEASE.json'):
        data = json.loads(manifest.read_text())
        for relative, expected in data['files'].items():
            path = manifest.parent / relative
            if not path.resolve().is_relative_to(manifest.parent.resolve()):
                raise ValueError(f'Unsafe manifest path: {relative}')
            key = path.relative_to(ROOT).as_posix()
            if key in external:
                if external[key]['sha256'] != expected:
                    raise ValueError(f'External checksum disagreement: {key}')
                deferred.add(key)
                if external_root is None:
                    continue
                path = Path(external_root) / key
                if path.stat().st_size != external[key]['bytes']:
                    raise ValueError(f'External size mismatch: {key}')
            if not path.is_file() or digest(path) != expected:
                raise ValueError(f'Missing or changed snapshot: {path}')
            checked += 1
    if deferred != set(external):
        raise ValueError('External inventory contains unbound files')
    data = json.loads((ROOT / 'assets/keyword_dictionary_semantic_review_r2/platform_data.json').read_text())
    if len(data['topics']) != 72 or data['semantic_accuracy_validated']:
        raise ValueError('Unexpected R2 scope or acceptance claim')
    return {'passed': True, 'snapshot_files_checked': checked, 'external_files': len(external),
            'external_content_verified': external_root is not None,
            'semantic_accuracy_validated': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--external-root', type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.external_root), ensure_ascii=False, indent=2))
