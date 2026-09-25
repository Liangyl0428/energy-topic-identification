"""Validate all exported rows, identifiers, assignments, subsets and arrays."""
from flat_common import *


def main():
    manifest = read(FLAT / 'results/ASSIGNMENT_MANIFEST.json')
    previous = read(PREVIOUS / 'results/ASSIGNMENT_MANIFEST.json')
    originals = read(CORPUS / 'data/INPUT_MANIFEST.json')['parts']
    summary = read(FLAT / 'results/SUMMARY.json')
    refs = read(FLAT / 'audit/INPUT_REFERENCES.json')
    assert sha(PREVIOUS / 'results/ASSIGNMENT_MANIFEST.json') == refs['source_assignment_manifest_sha256']
    assert sha(PREVIOUS / 'results/topic_dictionary.csv') == refs['source_dictionary_sha256']
    assert sha(PREVIOUS / 'results/SUMMARY.json') == refs['source_summary_sha256']
    assert sha(PREVIOUS / 'VALIDATION.json') == refs['source_validation_sha256']
    assert sha(CORPUS / 'data/INPUT_MANIFEST.json') == refs['original_corpus_manifest_sha256']
    catalog = pd.read_csv(FLAT / 'results/category_dictionary.csv')
    quality = pd.read_csv(FLAT / 'results/quarantine_dictionary.csv')
    crosswalk = pd.read_csv(FLAT / 'audit/label_crosswalk.csv').fillna('')
    active = crosswalk[crosswalk.mapping_status.eq('active')].set_index('source_topic_id')
    assert len(catalog) == summary['category_count'] == manifest['category_count'] == 750
    assert catalog.category_id.is_unique and catalog.category_name.is_unique
    assert catalog.documents.gt(0).all()
    assert np.array_equal(catalog.category_index, np.arange(len(catalog)))
    assert catalog.category_id.tolist() == [f'C{i + 1:04d}' for i in range(len(catalog))]
    assert not any(term in column for column in catalog for term in ['parent', 'child', 'leaf'])
    arrays = {}
    for key, metadata in manifest['arrays'].items():
        assert sha(FLAT / metadata['file']) == metadata['sha256']
        arrays[key] = np.load(FLAT / metadata['file'], mmap_mode='r')
        assert arrays[key].shape == (manifest['documents'],)
    source_labels = np.load(PREVIOUS / 'results/final_labels.npy', mmap_mode='r')
    source_review = np.load(PREVIOUS / 'results/needs_review.npy', mmap_mode='r')
    columns = [c for c in catalog if c not in ['category_id', 'category_index', 'category_name']]
    statistics = {c: Counter() for c in columns}
    qstatistics = {c: Counter() for c in quality if c not in ['quarantine_code', 'quarantine_reason']}
    totals, statuses, qualities, sources, origins, reasons, transitions = [Counter() for _ in range(7)]
    assert len(manifest['parts']) == len(previous['parts']) == len(originals) == 259
    end = 0
    for i, (part, prior_part, original_part) in enumerate(zip(manifest['parts'], previous['parts'], originals)):
        path = FLAT / part['file']
        assert sha(path) == part['sha256']
        assert sha(PREVIOUS / prior_part['file']) == prior_part['sha256']
        table = pq.read_table(path)
        assert table.schema.equals(SCHEMA, check_metadata=False)
        current = table.to_pandas()
        prior = pq.read_table(PREVIOUS / prior_part['file']).to_pandas()
        start = part['first_row']
        assert start == end == prior_part['first_row'] == original_part['first_row']
        assert len(current) == part['n'] == prior_part['n'] == original_part['n']
        end = start + part['n']
        assert np.array_equal(current.row_id, np.arange(start, end))
        original = pq.read_table(CORPUS / original_part['file'],
                                columns=['row_id', 'doc_id', 'source', 'date', 'retracted']).to_pandas()
        for column in original:
            pd.testing.assert_series_equal(current[column], original[column], check_dtype=False)
        for column in ['title', 'needs_review', 'quality_status', 'initial_quality_status', 'quality_flags',
                       'text_cleaned', 'retracted', 'rule_id', 'text_evidence_level', 'semantic_support_cosine',
                       'semantic_support_cluster1000', 'raw_cluster1000', 'routing_body_characters',
                       'clean_text_nearest1000', 'review_priority']:
            pd.testing.assert_series_equal(current[column], prior[column], check_dtype=False)
        expected_indices = prior.final_topic_id.map(active.category_index).fillna(-1).to_numpy(dtype=np.int16)
        assert np.array_equal(current.category_index, expected_indices)
        assert np.array_equal(prior.final_topic_index, source_labels[start:end])
        assert np.array_equal(current.category_index, arrays['final_labels'][start:end])
        assert np.array_equal(current.needs_review, arrays['needs_review'][start:end])
        assert np.array_equal(current.needs_review, source_review[start:end])
        assert np.array_equal(current.quarantined, arrays['quarantined'][start:end])
        q = current.quarantined
        assert np.array_equal(q, prior.final_topic_id.str.startswith('Q.'))
        assert current.loc[q, 'category_index'].eq(-1).all()
        assert current.loc[q, ['category_id', 'category_name']].isna().all().all()
        assert current.loc[~q, ['quarantine_code', 'quarantine_reason']].isna().all().all()
        assert (current.loc[q, 'quarantine_code'].to_numpy() == prior.loc[q, 'final_topic_id'].to_numpy()).all()
        assert current.loc[~q, 'category_id'].isin(catalog.category_id).all()
        expected_names = catalog.set_index('category_id').category_name
        pd.testing.assert_series_equal(current.loc[~q, 'category_name'].reset_index(drop=True),
            prior.loc[~q, 'final_topic_label'].reset_index(drop=True), check_names=False)
        assert (current.loc[~q, 'category_id'].map(expected_names).to_numpy() ==
                current.loc[~q, 'category_name'].to_numpy()).all()
        assert np.array_equal(current.eligible_for_counts, ~q & ~current.retracted)
        assert np.array_equal(current.eligible_for_supported_analysis, prior.eligible_for_accepted_topic_analysis)
        assert not (current.eligible_for_supported_analysis & (q | current.needs_review | current.retracted)).any()
        assert np.array_equal(arrays['analysis_count_labels'][start:end],
                              np.where(current.eligible_for_counts, current.category_index, -1))
        assert np.array_equal(arrays['analysis_supported_labels'][start:end],
                              np.where(current.eligible_for_supported_analysis, current.category_index, -1))
        assert np.array_equal(current.label_changed, prior.topic_changed)
        assert np.array_equal(current.semantic_label_changed, prior.topic_changed & ~q)
        assert np.array_equal(current.priority_cleanup, prior.priority_parent)
        assert np.array_equal(current.assignment_status, prior.assignment_status.map(STATUS))
        assert np.array_equal(current.label_origin, prior.label_origin.map(ORIGIN))
        assert np.array_equal(current.decision_action, prior.finalization_action.map(ACTION))
        assert np.array_equal(current.review_reason, prior.review_reason.map(flat_reason))
        assert not current.review_reason.str.contains('主类|父类|子类', regex=True).any()
        expected_baseline = prior.old_parent_id.map(active.category_id)
        pd.testing.assert_series_equal(current.baseline_category_id.fillna(''), expected_baseline.fillna(''), check_names=False)
        assert np.array_equal(current.baseline_category_name, prior.old_parent_name)
        assert np.array_equal(current.baseline_review_status, prior.old_parent_status)
        masks = {'documents': ~q, 'countable_documents': current.eligible_for_counts,
            'supported_documents': current.eligible_for_supported_analysis, 'needs_review_documents': current.needs_review & ~q,
            'retracted_documents': current.retracted & ~q, 'text_cleaned_documents': current.text_cleaned & ~q,
            'semantic_label_changes': current.semantic_label_changed,
            **{f'{s}_documents': current.source.eq(s) & ~q for s in SOURCE_CN}}
        for key, mask in masks.items():
            statistics[key].update(current.loc[mask, 'category_id'].value_counts().to_dict())
        qmasks = {'documents': q, 'needs_review_documents': q & current.needs_review,
                  'retracted_documents': q & current.retracted,
                  **{f'{s}_documents': q & current.source.eq(s) for s in SOURCE_CN}}
        for key, mask in qmasks.items():
            qstatistics[key].update(current.loc[mask, 'quarantine_code'].value_counts().to_dict())
        for folder, mask in [('pending_review', current.needs_review),
                             ('label_changes', current.label_changed), ('quality_quarantine', q)]:
            metadata = part[folder]
            assert sha(FLAT / metadata['file']) == metadata['sha256']
            subset = pq.read_table(FLAT / metadata['file'])
            assert subset.num_rows == metadata['n'] == int(mask.sum())
            pd.testing.assert_frame_equal(subset.to_pandas(), current.loc[mask].reset_index(drop=True))
        totals['documents'] += len(current)
        for key in summary['totals']:
            if key != 'documents': totals[key] += int(current[key].sum())
        statuses.update(current.assignment_status.value_counts().to_dict())
        qualities.update(current.quality_status.value_counts().to_dict())
        sources.update(current.source.value_counts().to_dict())
        origins.update(current.label_origin.value_counts().to_dict())
        reasons.update(current.loc[current.needs_review, 'review_reason'].value_counts().to_dict())
        changed = current[current.label_changed].copy()
        changed['baseline_category_id'] = changed.baseline_category_id.fillna('')
        changed['destination'] = changed.category_id.fillna(changed.quarantine_code)
        transitions.update(changed.groupby(['baseline_category_id', 'destination']).size().to_dict())
        if i % 25 == 0 or i == len(manifest['parts']) - 1:
            print('VALIDATED_PARTS', i + 1, len(manifest['parts']), flush=True)
    assert end == manifest['documents'] == 5119004
    assert dict(totals) == summary['totals']
    for column, counter in statistics.items():
        assert catalog.set_index('category_id')[column].to_dict() == {key: counter[key] for key in catalog.category_id}
    for column, counter in qstatistics.items():
        assert quality.set_index('quarantine_code')[column].to_dict() == {key: counter[key] for key in quality.quarantine_code}
    assert int(catalog.documents.sum()) == summary['category_records'] == 5111081
    assert int(catalog.documents.sum()) + int(quality.documents.sum()) == end
    assert np.array_equal(catalog.documents, catalog[['paper_documents', 'patent_documents', 'policy_documents']].sum(axis=1))
    assert np.array_equal(catalog.documents - catalog.retracted_documents, catalog.countable_documents)
    for key, counter in [('status', statuses), ('quality', qualities), ('source', sources), ('origin', origins), ('review_reason', reasons)]:
        assert dict(counter) == summary['counts'][key]
        saved = pd.read_csv(FLAT / f'results/{key}_counts.csv').fillna('')
        assert saved.set_index(key).documents.to_dict() == dict(counter)
    saved_transitions = pd.read_csv(FLAT / 'results/label_transitions.csv').fillna('')
    saved_transitions['destination'] = np.where(saved_transitions.category_id.ne(''), saved_transitions.category_id, saved_transitions.quarantine_code)
    assert saved_transitions.set_index(['baseline_category_id', 'destination']).documents.to_dict() == dict(transitions)
    assert int(saved_transitions.documents.sum()) == totals['label_changed']
    correction_rows = 0
    for metadata in manifest['text_corrections']:
        local_path = FLAT / metadata['file']
        assert sha(local_path) == metadata['sha256'] == sha(PREVIOUS / metadata['file'])
        assert pq.ParquetFile(local_path).metadata.num_rows == metadata['n']
        correction_rows += metadata['n']
    assert correction_rows == totals['text_cleaned']
    result = dict(passed=True, created_utc=now(), documents=end, parts=len(manifest['parts']), categories=len(catalog),
        category_records=int(catalog.documents.sum()), quality_quarantine_records=int(quality.documents.sum()),
        one_current_category_per_classified_record=True, no_empty_categories=True, no_duplicate_category_names=True,
        continuous_unique_complete_row_ids=True, identifiers_sources_dates_retraction_flags_unchanged=True,
        category_meaning_and_document_assignments_preserved=True, flat_conversion_semantic_changes=0,
        review_and_evidence_flags_preserved=True, arrays_match_all_parquet_rows=True,
        subsets_match_assignments=True, all_counts_reconciled=True,
        source_final_assignments_hashes_verified=True, previous_catalog_summary_validation_hashes_unchanged=True,
        copied_text_correction_records_verified=correction_rows, totals=dict(totals),
        limitation='This is an integrity validation, not a semantic accuracy or non-overlap certification.')
    dump(FLAT / 'VALIDATION.json', result)
    print('FLAT_VALIDATION_PASSED', len(catalog), end, flush=True)


if __name__ == '__main__':
    main()
