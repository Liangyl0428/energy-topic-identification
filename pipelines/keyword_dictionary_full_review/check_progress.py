"""Audit persisted reading history without assigning semantic decisions."""
from common import *


def main():
    progress = read(WORK / 'CONTEXT_PROGRESS.json')
    queue = pd.read_parquet(WORK / 'frozen_context_queue.parquet')
    prepared = read(WORK / 'CONTEXT_PREPARED.json')
    assert sha(WORK / 'frozen_context_queue.parquet') == prepared['context_queue_sha256']
    contexts = pd.read_parquet(WORK / 'context_review_ledger.parquet')
    assert contexts.context_index.tolist() == list(range(1, progress['reviewed'] + 1))
    assert contexts.evidence_id.is_unique
    assert len(contexts) == progress['reviewed']
    recorded = []
    for b in progress['batch_manifest']:
        path = WORK / b['review_file']
        review = read(path)
        assert sha(path) == b['review_sha256']
        input_path = path.with_name(path.name.replace('_review', '_input'))
        assert sha(input_path) == b['input_sha256'] == review['input_sha256']
        assert len(review['decisions']) == b['cases']
        expanded = set()
        for e in review.get('expansion_files', []):
            assert sha(WORK / e['path']) == e['sha256']
            expanded.update(r['context_index'] for r in read(WORK / e['path'])['contexts'])
        for case in review['decisions']:
            assert case['expanded_body_read'] == (case['context_index'] in expanded)
        recorded.extend(review['decisions'])
    assert [r['context_index'] for r in recorded] == contexts.context_index.tolist()
    for col in ['evidence_id', 'keyword_code', 'outcome', 'review_reason']:
        assert [r[col] for r in recorded] == contexts[col].tolist()
    decisions, corrections = {}, 0
    for path in sorted((WORK / 'term_resolutions').glob('resolution_*.json')):
        for record in read(path)['decisions']:
            code = record['keyword_code']
            for remap in record.get('explicit_remapped_support', []):
                source = contexts[contexts.evidence_id.eq(remap['evidence_id'])]
                assert len(source) == 1
                source = source.iloc[0]
                assert source.keyword_code == code and source.outcome == 'wrong_topic'
                assert bool(source.expanded_body_read) and remap['reason'].strip()
                assert remap['original_topic'] == record['proposal_topic_code']
                assert remap['accepted_topic'] == record['topic_code'] != remap['original_topic']
                assert remap['evidence_id'] in record['evidence_ids']
            if code in decisions:
                previous = hashlib.sha256(json.dumps(decisions[code], ensure_ascii=False,
                    sort_keys=True).encode()).hexdigest()
                assert record['supersedes_decision_sha256'] == previous
                corrections += 1
            decisions[code] = record
    ledger = pd.read_parquet(WORK / 'term_resolution_ledger.parquet')
    assert ledger.keyword_code.is_unique and set(ledger.keyword_code) == set(decisions)
    for record in ledger.to_dict('records'):
        for col in ['decision', 'topic_code', 'resolution_status', 'resolution_reason']:
            assert record[col] == decisions[record['keyword_code']][col]
    completed = queue.groupby('keyword_code').context_index.max()
    ready = set(completed[completed.le(progress['reviewed'])].index)
    assert ready == set(decisions), ('Unresolved fully read words', ready - set(decisions))
    observations = pd.read_csv(WORK / 'document_keyword_review.csv', keep_default_na=False)
    assert not observations.duplicated(['row_id', 'keyword_code']).any()
    for path in sorted(WORK.glob('document_override_review_*.json')):
        log = read(path)
        if log.get('source_sha256'):
            assert sha(WORK / log['source']) == log['source_sha256']
        for r in log['rows']:
            old = observations[observations.row_id.eq(r['row_id']) &
                observations.keyword_code.eq(r['keyword_code'])]
            assert len(old) == 1 and old.iloc[0].action == r['action']
    constraints = read(WORK / 'word_specific_anchor_constraints.json')['constraints']
    assert len({r['display_name'] for r in constraints}) == len(constraints)
    checkpoint = dict(contexts_reviewed=len(contexts), total_contexts=len(queue),
        terms_resolved=len(ledger), target_terms=int(queue.keyword_code.nunique()),
        supplemental_contexts_reviewed=6, next_context_index=len(contexts)+1,
        next_batch=len(progress['batch_manifest'])+1,
        withholdings=int(observations.action.eq('withhold_trigger').sum()),
        needs_context=int(observations.action.eq('needs_context').sum()),
        word_specific_constraints=len(constraints), prior_term_amendments=corrections,
        all_fully_read_terms_resolved=True, all_batch_hashes_valid=True,
        dictionary_build_started=False)
    write(WORK / 'REVIEW_CHECKPOINT.json', checkpoint)
    print(json.dumps(checkpoint, ensure_ascii=False))


if __name__ == '__main__':
    main()
