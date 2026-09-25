"""Check packaged files and catalog accounting, not classification accuracy."""
import ast
import csv
import hashlib
import json
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]


def check(condition, message):
    if not condition:
        raise ValueError(message)


def read_csv(name):
    with (ROOT / 'results' / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def main():
    rows = read_csv('category_dictionary.csv')
    summary = json.loads((ROOT / 'results/SUMMARY.json').read_text())
    check([r['category_id'] for r in rows] == [f'C{i:04d}' for i in range(1, 751)], '750 IDs')
    check([int(r['category_index']) for r in rows] == list(range(750)), 'category indices')
    for r in rows:
        check(bool(r['category_name']), 'empty name')
        check(all(int(v) >= 0 for k, v in r.items() if k not in ('category_name', 'category_id')), 'negative count')
        total = int(r['documents'])
        check(total > 0, 'unused category')
        check(total == sum(int(r[s + '_documents']) for s in ('paper', 'patent', 'policy')), 'source sum')
        check(total == int(r['countable_documents']) + int(r['retracted_documents']), 'retraction accounting')
        check(int(r['supported_documents']) <= int(r['countable_documents']), 'supported subset')
        check(int(r['needs_review_documents']) <= total, 'review subset')
    expected = {'documents': summary['category_records'],
                'countable_documents': summary['totals']['eligible_for_counts'],
                'supported_documents': summary['totals']['eligible_for_supported_analysis'],
                'needs_review_documents': summary['category_records_needing_review'],
                'semantic_label_changes': summary['totals']['semantic_label_changed']}
    for field, value in expected.items():
        check(sum(int(r[field]) for r in rows) == value, field)
    quarantine = read_csv('quarantine_dictionary.csv')
    check(sum(int(r['documents']) for r in quarantine) == summary['totals']['quarantined'], 'quarantine')
    check(summary['category_records'] + summary['totals']['quarantined'] == summary['totals']['documents'], 'all records')
    check(summary['category_records_needing_review'] + sum(int(r['needs_review_documents']) for r in quarantine)
          == summary['totals']['needs_review'], 'all pending reviews')
    for source in read_csv('source_counts.csv'):
        field = source['source'] + '_documents'
        check(sum(int(r[field]) for r in rows + quarantine) == int(source['documents']), 'source totals')
    workbook = ROOT / 'results/750类平级目录与文献标签.xlsx'
    wb = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    actual = list(wb['类别目录'].values)[1:]
    fields = ['category_id', 'category_name', 'documents', 'countable_documents',
              'supported_documents', 'needs_review_documents', 'retracted_documents',
              'text_cleaned_documents', 'semantic_label_changes', 'paper_documents',
              'patent_documents', 'policy_documents']
    expected_rows = [tuple(r[k] if k in ('category_id', 'category_name') else int(r[k])
                           for k in fields) for r in rows]
    check(actual == expected_rows, 'Excel/CSV mismatch')
    wb.close()
    original = json.loads((ROOT / 'provenance/SOURCE_FILES.json').read_text())
    for item in original:
        check(hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() == item['sha256'], item['path'])
    release = ROOT / 'provenance/SHA256SUMS.json'
    check(release.exists(), 'missing release manifest')
    for path, digest in json.loads(release.read_text()).items():
        check(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path)
    sources = list(ROOT.rglob('*.py'))
    for path in sources:
        if not any(p.startswith('.venv') for p in path.parts):
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    print(json.dumps({'passed': True, 'categories': len(rows), 'category_records': summary['category_records'],
                      'quarantined': summary['totals']['quarantined'], 'excel_csv_equal': True,
                      'source_files_verified': len(original), 'classification_accuracy_evaluated': False}, indent=2))


if __name__ == '__main__':
    main()
