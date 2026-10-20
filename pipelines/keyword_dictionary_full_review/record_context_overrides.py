"""Persist explicitly reviewed source-observation overrides; never infer semantics."""
from common import *
import argparse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', required=True)
    args = ap.parse_args()
    spec_path = Path(args.spec)
    spec = read(spec_path)
    source_path = WORK / spec['source']
    review = read(source_path)
    assert sha(source_path) == spec['source_sha256']
    cases = {r['context_index']: r for r in review['decisions']}
    metadata = pd.read_parquet(WORK / 'context_metadata.parquet').set_index('row_id')
    sources = pd.read_parquet(WORK / 'context_source_keywords.parquet')
    existing = pd.read_csv(WORK / 'document_keyword_review.csv', keep_default_na=False)
    fresh = pd.read_csv(WORK / 'new_document_keyword_review.csv', keep_default_na=False)
    keys = set(zip(existing.row_id, existing.keyword_code))
    rows, reconfirmed, seen = [], [], set()
    for item in spec['items']:
        case = cases[item['context_index']]
        assert case['expanded_body_read'], 'Override needs an expanded context reading'
        assert item['action'] in {'withhold_trigger', 'needs_context'}
        assert item['reason'].strip()
        names = item.get('terms', [case['display_name']])
        src = sources[sources.evidence_id.eq(case['evidence_id'])]
        for name in names:
            match = src[src.raw_name.eq(name)]
            assert len(match) == 1, (case['context_index'], name, 'not a source observation')
            code = match.iloc[0].keyword_code
            key = (int(case['row_id']), code)
            assert key not in seen, ('duplicate in specification', key)
            seen.add(key)
            record = dict(row_id=key[0], doc_id=case['doc_id'],
                source_evidence_id=case['evidence_id'], keyword_code=code,
                source_keyword=name, action=item['action'], reason=item['reason'],
                title=case['title'], body_excerpt=str(metadata.loc[key[0], 'body'])[:1400],
                reviewer='assistant', expert_approved=False)
            if key in keys:
                old = existing[existing.row_id.eq(key[0]) & existing.keyword_code.eq(key[1])]
                assert old.iloc[0].action == item['action'], 'Action change requires explicit amendment'
                reconfirmed.append(record)
            else:
                rows.append(record)
    logs = sorted(WORK.glob('document_override_review_*.json'))
    target = WORK / f'document_override_review_{len(logs)+1:03d}.json'
    assert not target.exists() and rows
    updated = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
    new = pd.concat([fresh, pd.DataFrame(rows)], ignore_index=True)
    assert not updated.duplicated(['row_id', 'keyword_code']).any()
    write(target, dict(source=spec['source'], source_sha256=spec['source_sha256'],
        input_spec_sha256=sha(spec_path), paper_full_text_read=False,
        rows=rows, reconfirmed_existing_overrides=reconfirmed))
    updated.to_csv(WORK / 'document_keyword_review.csv', index=False, encoding='utf-8-sig')
    new.to_csv(WORK / 'new_document_keyword_review.csv', index=False, encoding='utf-8-sig')
    print(json.dumps(dict(file=target.name, added=len(rows), reconfirmed=len(reconfirmed),
        totals=updated.action.value_counts().to_dict())))


if __name__ == '__main__':
    main()
