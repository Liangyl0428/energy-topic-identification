"""Export the existing final decisions as a single flat classification."""
from flat_common import *
import shutil


def main():
    manifest_path = PREVIOUS / 'results/ASSIGNMENT_MANIFEST.json'
    dictionary_path = PREVIOUS / 'results/topic_dictionary.csv'
    manifest = read(manifest_path)
    previous_summary = read(PREVIOUS / 'results/SUMMARY.json')
    assert read(PREVIOUS / 'VALIDATION.json')['passed']
    dictionary = pd.read_csv(dictionary_path).fillna('')
    active = dictionary.loc[(dictionary.kind != 'quality') &
                            (dictionary.assigned_documents > 0)].sort_values('topic_index').copy()
    assert active.topic_id.is_unique and active.name.is_unique
    active['category_index'] = np.arange(len(active), dtype=np.int16)
    active['category_id'] = [f'C{i + 1:04d}' for i in range(len(active))]
    active['category_name'] = active['name']
    lookup = active.set_index('topic_id')
    quality = dictionary.loc[dictionary.kind.eq('quality')].set_index('topic_id')
    n = manifest['documents']
    for folder in ['results/assignments', 'results/pending_review', 'results/label_changes',
                   'results/quality_quarantine', 'results/text_corrections', 'audit', 'logs']:
        (FLAT / folder).mkdir(parents=True, exist_ok=True)

    crosswalk = dictionary[['topic_index', 'topic_id', 'name', 'assigned_documents']].rename(
        columns={'topic_index': 'source_topic_index', 'topic_id': 'source_topic_id',
                 'name': 'source_label'})
    crosswalk['category_index'] = crosswalk.source_topic_id.map(lookup.category_index).fillna(-1).astype(int)
    crosswalk['category_id'] = crosswalk.source_topic_id.map(lookup.category_id).fillna('')
    crosswalk['category_name'] = crosswalk.source_topic_id.map(lookup.category_name).fillna('')
    crosswalk['mapping_status'] = np.where(dictionary.kind.eq('quality'), 'quality_quarantine',
                                         np.where(dictionary.assigned_documents.gt(0), 'active', 'unused_candidate'))
    crosswalk['quarantine_code'] = np.where(dictionary.kind.eq('quality'), dictionary.topic_id, '')
    csv(crosswalk, FLAT / 'audit/label_crosswalk.csv')
    csv(pd.DataFrame([dict(source_status=k, assignment_status=v, description=STATUS_CN[v])
                      for k, v in STATUS.items()]), FLAT / 'audit/status_crosswalk.csv')
    refs = dict(created_utc=now(), previous_export_directory=str(PREVIOUS.relative_to(ROOT)),
                original_corpus=str(CORPUS.relative_to(ROOT)),
                source_assignment_manifest_sha256=sha(manifest_path),
                source_dictionary_sha256=sha(dictionary_path),
                source_summary_sha256=sha(PREVIOUS / 'results/SUMMARY.json'),
                source_validation_sha256=sha(PREVIOUS / 'VALIDATION.json'),
                original_corpus_manifest_sha256=sha(CORPUS / 'data/INPUT_MANIFEST.json'),
                source_decisions='results/assignments/',
                note='All current decisions are preserved. Historical candidates and rule evidence remain in the previous export, joined by row_id.')
    dump(FLAT / 'audit/INPUT_REFERENCES.json', refs)

    arrays = {name: np.lib.format.open_memmap(FLAT / 'results' / f'{name}.npy',
              mode='w+', dtype=(np.bool_ if name in ['needs_review', 'quarantined'] else np.int16), shape=(n,))
              for name in ['final_labels', 'analysis_count_labels', 'analysis_supported_labels', 'needs_review', 'quarantined']}
    stats = {name: Counter() for name in ['documents', 'countable_documents', 'supported_documents',
        'needs_review_documents', 'retracted_documents', 'text_cleaned_documents',
        'semantic_label_changes', 'paper_documents', 'patent_documents', 'policy_documents']}
    totals = Counter()
    counts = {name: Counter() for name in ['status', 'quality', 'source', 'review_reason', 'origin']}
    qstats = {name: Counter() for name in ['documents', 'needs_review_documents', 'retracted_documents',
                                        'paper_documents', 'patent_documents', 'policy_documents']}
    transitions = Counter()
    parts, corrections = [], []
    expected_row = 0
    for number, part in enumerate(manifest['parts']):
        input_path = PREVIOUS / part['file']
        assert sha(input_path) == part['sha256'], input_path
        frame = pq.read_table(input_path).to_pandas()
        start, end = part['first_row'], part['first_row'] + part['n']
        assert start == expected_row and np.array_equal(frame.row_id, np.arange(start, end))
        expected_row = end
        q = frame.final_topic_id.isin(quality.index)
        assert frame.final_topic_id.isin(set(lookup.index) | set(quality.index)).all()
        output = frame[['row_id', 'doc_id', 'source', 'date', 'title']].copy()
        output['category_index'] = frame.final_topic_id.map(lookup.category_index).fillna(-1).astype(np.int16)
        output['category_id'] = frame.final_topic_id.map(lookup.category_id).where(~q, None)
        output['category_name'] = frame.final_topic_id.map(lookup.category_name).where(~q, None)
        output['baseline_category_id'] = frame.old_parent_id.map(lookup.category_id)
        output['baseline_category_name'] = frame.old_parent_name
        output['baseline_review_status'] = frame.old_parent_status
        assert frame.loc[output.baseline_category_id.isna(), 'old_parent_id'].fillna('').eq('').all()
        output['assignment_status'] = frame.assignment_status.map(STATUS)
        output['label_origin'] = frame.label_origin.map(ORIGIN)
        output['label_changed'] = frame.topic_changed
        output['semantic_label_changed'] = frame.topic_changed & ~q
        output['quarantined'] = q
        output['quarantine_code'] = frame.final_topic_id.where(q, None)
        output['quarantine_reason'] = frame.final_topic_id.map(quality['name']).where(q, None)
        for column in ['quality_status', 'initial_quality_status', 'quality_flags', 'text_cleaned',
                       'retracted', 'needs_review', 'review_priority', 'rule_id', 'text_evidence_level',
                       'semantic_support_cosine', 'semantic_support_cluster1000', 'raw_cluster1000',
                       'routing_body_characters', 'clean_text_nearest1000']:
            output[column] = frame[column]
        output['review_reason'] = frame.review_reason.map({v: flat_reason(v) for v in frame.review_reason.unique()})
        output['priority_cleanup'] = frame.priority_parent
        output['eligible_for_counts'] = ~q & ~frame.retracted
        output['eligible_for_supported_analysis'] = frame.eligible_for_accepted_topic_analysis
        output['decision_action'] = frame.finalization_action.map(ACTION)
        assert output[['assignment_status', 'label_origin', 'decision_action']].notna().all().all()
        assert (output.eligible_for_counts == frame.eligible_for_parent_counts).all()
        assert not (output.eligible_for_supported_analysis & (q | frame.retracted | frame.needs_review)).any()
        assert (output.loc[~q, 'category_name'].to_numpy() == frame.loc[~q, 'final_topic_label'].to_numpy()).all()
        assert not output.review_reason.str.contains('主类|父类|子类', regex=True).any()
        table = pa.Table.from_pandas(output, schema=SCHEMA, preserve_index=False).replace_schema_metadata(None)
        filename = input_path.name
        path = FLAT / 'results/assignments' / filename
        pq.write_table(table, path, compression='zstd')
        part_info = dict(file=str(path.relative_to(FLAT)), n=len(output), first_row=start, sha256=sha(path))
        for folder, selector in [('pending_review', output.needs_review),
                                 ('label_changes', output.label_changed), ('quality_quarantine', q)]:
            subset_path = FLAT / 'results' / folder / filename
            pq.write_table(table.filter(pa.array(selector)), subset_path, compression='zstd')
            part_info[folder] = dict(file=str(subset_path.relative_to(FLAT)), n=int(selector.sum()), sha256=sha(subset_path))
        parts.append(part_info)
        correction_source = PREVIOUS / 'results/text_corrections' / filename
        if correction_source.exists():
            correction_target = FLAT / 'results/text_corrections' / filename
            shutil.copyfile(correction_source, correction_target)
            assert sha(correction_target) == sha(correction_source)
            ct = pq.read_table(correction_target, columns=['row_id']).column('row_id').to_numpy()
            assert np.array_equal(np.sort(ct), np.sort(output.loc[output.text_cleaned, 'row_id'].to_numpy()))
            corrections.append(dict(file=str(correction_target.relative_to(FLAT)), n=len(ct), sha256=sha(correction_target)))
        else:
            assert not output.text_cleaned.any()
        indices = output.category_index.to_numpy()
        arrays['final_labels'][start:end] = indices
        arrays['analysis_count_labels'][start:end] = np.where(output.eligible_for_counts, indices, -1)
        arrays['analysis_supported_labels'][start:end] = np.where(output.eligible_for_supported_analysis, indices, -1)
        arrays['needs_review'][start:end] = output.needs_review
        arrays['quarantined'][start:end] = q
        masks = {'documents': ~q, 'countable_documents': output.eligible_for_counts,
            'supported_documents': output.eligible_for_supported_analysis, 'needs_review_documents': output.needs_review & ~q,
            'retracted_documents': output.retracted & ~q, 'text_cleaned_documents': output.text_cleaned & ~q,
            'semantic_label_changes': output.semantic_label_changed,
            **{f'{s}_documents': output.source.eq(s) & ~q for s in SOURCE_CN}}
        for key, mask in masks.items():
            stats[key].update(output.loc[mask, 'category_id'].value_counts().to_dict())
        qmasks = {'documents': q, 'needs_review_documents': q & output.needs_review,
                  'retracted_documents': q & output.retracted,
                  **{f'{s}_documents': q & output.source.eq(s) for s in SOURCE_CN}}
        for key, mask in qmasks.items():
            qstats[key].update(output.loc[mask, 'quarantine_code'].value_counts().to_dict())
        for key, column in [('status', 'assignment_status'), ('quality', 'quality_status'),
                            ('source', 'source'), ('origin', 'label_origin')]:
            counts[key].update(output[column].value_counts().to_dict())
        counts['review_reason'].update(output.loc[output.needs_review, 'review_reason'].value_counts().to_dict())
        changed = output.loc[output.label_changed].copy()
        changed['baseline_category_id'] = changed.baseline_category_id.fillna('')
        changed['destination'] = changed.category_id.fillna(changed.quarantine_code)
        transitions.update(changed.groupby(['baseline_category_id', 'destination']).size().to_dict())
        totals['documents'] += len(output)
        for key in ['quarantined', 'label_changed', 'semantic_label_changed', 'needs_review', 'text_cleaned',
                    'retracted', 'eligible_for_counts', 'eligible_for_supported_analysis']:
            totals[key] += int(output[key].sum())
        if number % 25 == 0 or number == len(manifest['parts']) - 1:
            progress = dict(stage='export_flat_labels', completed_parts=number + 1, parts=len(manifest['parts']),
                            processed_records=end, updated_utc=now())
            dump(FLAT / 'PROGRESS.json', progress)
            print(json.dumps(progress, ensure_ascii=False), flush=True)
    assert expected_row == n
    for array in arrays.values():
        array.flush()
    catalog = active[['category_index', 'category_id', 'category_name']].copy()
    for key, counter in stats.items():
        catalog[key] = catalog.category_id.map(counter).fillna(0).astype(np.int64)
    assert np.array_equal(catalog.documents.to_numpy(), active.assigned_documents.to_numpy())
    assert np.array_equal(catalog.supported_documents.to_numpy(), active.accepted_topic_documents.to_numpy())
    csv(catalog, FLAT / 'results/category_dictionary.csv')
    qcatalog = quality.reset_index()[['topic_id', 'name']].rename(columns={'topic_id': 'quarantine_code', 'name': 'quarantine_reason'})
    for key, counter in qstats.items():
        qcatalog[key] = qcatalog.quarantine_code.map(counter).fillna(0).astype(np.int64)
    csv(qcatalog, FLAT / 'results/quarantine_dictionary.csv')
    for key, counter in counts.items():
        data = pd.DataFrame(counter.most_common(), columns=[key, 'documents'])
        if key == 'status': data.insert(1, 'description', data[key].map(STATUS_CN))
        if key == 'quality': data.insert(1, 'description', data[key].map(QUALITY_CN))
        if key == 'source': data.insert(1, 'description', data[key].map(SOURCE_CN))
        csv(data, FLAT / f'results/{key}_counts.csv')
    names = catalog.set_index('category_id').category_name.to_dict()
    names[''] = '原无研究类别'
    names.update(qcatalog.set_index('quarantine_code').quarantine_reason.to_dict())
    tr = pd.DataFrame([dict(baseline_category_id=a, baseline_category_name=names[a],
          category_id='' if b.startswith('Q.') else b, category_name='' if b.startswith('Q.') else names[b],
          quarantine_code=b if b.startswith('Q.') else '', quarantine_reason=names[b] if b.startswith('Q.') else '',
          documents=v) for (a, b), v in sorted(transitions.items())])
    csv(tr, FLAT / 'results/label_transitions.csv')
    t = previous_summary['totals']
    assert totals['documents'] == n == 5119004
    assert totals['semantic_label_changed'] == t['accepted_changed_labels'] == 374161
    assert totals['label_changed'] == t['topic_changed'] == 382084
    assert totals['needs_review'] == t['needs_review'] == 2758621
    assert totals['quarantined'] == int(quality.assigned_documents.sum()) == 7923
    assert totals['text_cleaned'] == sum(p['n'] for p in corrections) == 14156
    assert totals['eligible_for_supported_analysis'] == t['eligible_for_accepted_topic_analysis']
    assert int(catalog.documents.sum()) + totals['quarantined'] == n
    summary = dict(created_utc=now(), category_count=len(catalog), numbering=f'C0001-C{len(catalog):04d}',
        category_records=int(catalog.documents.sum()), totals=dict(totals),
        category_records_needing_review=int(catalog.needs_review_documents.sum()),
        quarantined_records_needing_review=int(qcatalog.needs_review_documents.sum()),
        unused_candidates_excluded=int(crosswalk.mapping_status.eq('unused_candidate').sum()),
        flat_conversion_semantic_changes=0, counts={k: dict(v) for k, v in counts.items()},
        note='Counts use direct document assignments only. Flat numbering does not certify semantic disjointness or manual review.')
    dump(FLAT / 'results/SUMMARY.json', summary)
    dump(FLAT / 'results/ASSIGNMENT_MANIFEST.json', dict(created_utc=now(), documents=n, category_count=len(catalog),
        row_key='row_id', category_dictionary='results/category_dictionary.csv', quality_index=-1,
        source_assignment_manifest_sha256=sha(manifest_path), parts=parts, text_corrections=corrections,
        arrays={name: dict(file=f'results/{name}.npy', sha256=sha(FLAT / f'results/{name}.npy')) for name in arrays}))
    print('FLAT_EXPORT_COMPLETE', len(catalog), dict(totals), flush=True)


if __name__ == '__main__':
    main()
