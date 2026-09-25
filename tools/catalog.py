"""Search the frozen topic directory; no model or external data required."""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--id', help='Exact category ID, e.g. C0001')
    parser.add_argument('--search', default='', help='Substring of category ID or name')
    parser.add_argument('--output', type=Path, help='Export matching rows as UTF-8 CSV')
    args = parser.parse_args()
    with (ROOT / 'results/category_dictionary.csv').open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = [r for r in reader if
                (args.id is None or r['category_id'] == args.id.upper()) and
                args.search.casefold() in (r['category_id'] + ' ' + r['category_name']).casefold()]
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        print(f'{len(rows)} topics exported to {args.output}')
    else:
        print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
