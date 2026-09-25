"""Read literature records, cleaned text and the current flat category."""
from flat_common import *
import argparse


def flat_part(part, include_body=True):
    columns = None if include_body else ['row_id', 'doc_id', 'source', 'date', 'title', 'url', 'retracted', 'usable']
    original = pq.read_table(CORPUS / part['file'], columns=columns).to_pandas()
    labels = pq.read_table(FLAT / 'results/assignments' / Path(part['file']).name).to_pandas()
    assert np.array_equal(original.row_id, labels.row_id)
    original = original.rename(columns={'title': 'original_title', 'body': 'original_body'})
    original = original.drop(columns=[c for c in original if c in labels and c != 'row_id'])
    result = original.merge(labels, on='row_id', validate='one_to_one')
    if include_body:
        result['body'] = result.original_body
        correction_path = FLAT / 'results/text_corrections' / Path(part['file']).name
        if correction_path.exists():
            corrections = pq.read_table(correction_path).to_pandas().set_index('row_id')
            mask = result.row_id.isin(corrections.index)
            result.loc[mask, 'body'] = result.loc[mask, 'row_id'].map(corrections.clean_body)
    return result


def iter_flat_parts(include_body=True):
    for part in read(CORPUS / 'data/INPUT_MANIFEST.json')['parts']:
        yield flat_part(part, include_body=include_body)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--row-id', type=int, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    part = next((p for p in read(CORPUS / 'data/INPUT_MANIFEST.json')['parts']
                 if p['first_row'] <= args.row_id < p['first_row'] + p['n']), None)
    if part is None:
        raise ValueError('row_id outside corpus')
    result = flat_part(part)
    record = result.loc[result.row_id.eq(args.row_id)].iloc[0].to_dict()
    for key, value in record.items():
        if isinstance(value, float) and np.isnan(value): record[key] = None
    dump(Path(args.output), record)
    print(args.output)


if __name__ == '__main__':
    main()
