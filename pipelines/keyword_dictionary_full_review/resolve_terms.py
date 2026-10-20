"""Persist explicit term conclusions only after all frozen samples were read."""
from common import *
import argparse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', required=True)
    args = ap.parse_args()
    spec = read(Path(args.spec))
    assert spec['summary'].strip()
    ledger = pd.read_csv(WORK / 'term_review_ledger.csv', keep_default_na=False)
    queue = pd.read_parquet(WORK / 'frozen_context_queue.parquet')
    checked = pd.read_parquet(WORK / 'context_review_ledger.parquet')
    assert checked.evidence_id.nunique() == len(checked)
    supplemental = pd.DataFrame()
    if spec.get('use_supplementary_evidence'):
        supplement = read(WORK / 'supplementary_context_review.json')
        sq = pd.read_parquet(WORK / 'supplementary_context_queue.parquet')
        assert supplement['queue_sha256'] == sha(WORK / 'supplementary_context_queue.parquet')
        assert supplement['all_displayed_contexts_read'] is True
        supplemental = pd.DataFrame(supplement['decisions'])
        assert supplemental.evidence_id.is_unique
        assert set(supplemental.evidence_id) == set(sq.evidence_id)
        assert set(zip(supplemental.evidence_id,supplemental.keyword_code)) == set(zip(sq.evidence_id,sq.keyword_code))
    secondary = []
    if spec.get('additional_evidence'):
        sources = pd.read_parquet(WORK / 'context_source_keywords.parquet')
        metadata = pd.read_parquet(WORK / 'context_metadata.parquet').set_index('row_id')
        for item in spec['additional_evidence']:
            assert item['reason'].strip() and item['outcome'] == 'energy_supported'
            case = checked[checked.context_index.eq(item['context_index'])]
            assert len(case) == 1 and bool(case.iloc[0]['expanded_body_read'])
            case = case.iloc[0]
            for name in item['terms']:
                candidate = ledger[ledger.display_name.eq(name)]
                assert len(candidate) == 1
                code = candidate.iloc[0]['keyword_code']
                tagged = bool(len(sources[sources.evidence_id.eq(case['evidence_id']) & sources.keyword_code.eq(code)]))
                literals = item.get('text_evidence_literals',[])
                if not tagged:
                    assert literals and all(isinstance(t,str) and t.strip() for t in literals)
                    original_text = str(case['title']) + ' ' + str(metadata.loc[case['row_id'],'body'])
                    assert all(t.casefold() in original_text.casefold() for t in literals), (name,'literal missing')
                secondary.append(dict(evidence_id=case['evidence_id'],keyword_code=code,
                    outcome=item['outcome'],review_reason=item['reason'],source='explicit_cross_term_reading',
                    original_keyword_observation_present=tagged,text_evidence_literals=literals,
                    creates_keyword_observation=False))
    folder = WORK / 'term_resolutions'
    folder.mkdir(exist_ok=True)
    existing = sorted(folder.glob('resolution_*.json'))
    prior = [r for p in existing for r in read(p)['decisions']]
    seen = {r['keyword_code'] for r in prior}
    records = []
    current_codes = set()
    statuses = {'active_confirmed','inactive_contextual','inactive_outside','inactive_unresolved','scope_boundary'}
    for group in spec['groups']:
        assert group['reason'].strip() and group['resolution_status'] in statuses
        for name in group['terms']:
            matches = ledger[ledger.display_name.eq(name)]
            assert len(matches) == 1, (name,len(matches))
            term = matches.iloc[0].to_dict()
            code = term['keyword_code']
            assert code not in current_codes, (name,'duplicate within this specification')
            current_codes.add(code)
            supersedes = ''
            if code in seen:
                previous = [r for r in prior if r['keyword_code'] == code][-1]
                supersedes = hashlib.sha256(json.dumps(previous,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
                assert spec.get('allow_corrections') is True and group.get('correction_reason','').strip()
                assert group.get('supersedes_decision_sha256') == supersedes, (name,'wrong previous decision hash')
            seen.add(code)
            all_ids = set(queue.loc[queue.keyword_code.eq(code),'evidence_id'])
            evidence = checked[checked.keyword_code.eq(code)]
            assert all_ids and set(evidence.evidence_id) == all_ids, (name,'read all frozen samples first')
            if len(supplemental):
                extra = supplemental[supplemental.keyword_code.eq(code)]
                evidence = pd.concat([evidence, extra], ignore_index=True)
                all_ids.update(extra.evidence_id)
            cross = pd.DataFrame([r for r in secondary if r['keyword_code'] == code])
            if len(cross):
                assert not set(cross.evidence_id).intersection(all_ids)
                evidence = pd.concat([evidence,cross],ignore_index=True)
                all_ids.update(cross.evidence_id)
            mode = group['decision']
            decision = term['decision'] if mode == 'keep_proposal' else mode
            assert decision in {'direct','conditional','general_auxiliary','broad_auxiliary','excluded'}
            topic = group.get('topic_code',term['topic_code']) if decision in {'direct','conditional'} else ''
            remapped_support = []
            for remap in group.get('remapped_support', []):
                # An explicit topic correction can reuse a reading whose original
                # proposed topic was rejected. Preserve the original outcome.
                assert decision in {'direct','conditional'} and topic != term['topic_code']
                assert remap['topic_code'] == topic and remap['reason'].strip()
                source_case = checked[checked.context_index.eq(remap['context_index'])]
                assert len(source_case) == 1
                source_case = source_case.iloc[0]
                assert source_case['keyword_code'] == code
                assert source_case['outcome'] == 'wrong_topic' and bool(source_case['expanded_body_read'])
                remapped_support.append(dict(evidence_id=source_case['evidence_id'],
                    original_outcome='wrong_topic', original_topic=term['topic_code'],
                    accepted_topic=topic, reason=remap['reason']))
            assert len({r['evidence_id'] for r in remapped_support}) == len(remapped_support)
            if decision in {'direct','conditional'}:
                assert topic.startswith('KWD-T') and group['resolution_status'] == 'active_confirmed'
                assert evidence.outcome.eq('energy_supported').any() or remapped_support, (name,'no sampled energy support')
            else:
                assert group['resolution_status'] != 'active_confirmed'
            records.append({
                'keyword_code':code, 'review_index':int(term['review_index']), 'display_name':name,
                'canonical_name':term['canonical_name'], 'decision':decision,'topic_code':topic,
                'proposal_decision':term['decision'],'proposal_topic_code':term['topic_code'],
                'baseline_decision':term['prior_decision'],'baseline_topic_code':term['prior_topic_code'],
                'resolution_status':group['resolution_status'],'resolution_reason':group['reason'],
                'supersedes_decision_sha256':supersedes,'correction_reason':group.get('correction_reason',''),
                'evidence_ids':sorted(all_ids),'evidence_outcomes':evidence.outcome.value_counts().to_dict(),
                'explicit_remapped_support':remapped_support,
                'reviewer':'assistant','expert_approved':False,'all_article_contexts_validated':False,
                'sampling_limit':'Judgment based on the explicitly read titles/excerpts and requested expansions; diagnostic evidence, not a blind accuracy test.',
            })
    assert records
    output = folder / f'resolution_{len(existing)+1:03d}.json'
    assert not output.exists()
    write(output, {'summary':spec['summary'],'input_spec_sha256':sha(Path(args.spec)),
                   'context_review_ledger_sha256':sha(WORK/'context_review_ledger.parquet'),
                   'supplementary_review_sha256':sha(WORK/'supplementary_context_review.json') if spec.get('use_supplementary_evidence') else None,
                   'additional_evidence':spec.get('additional_evidence',[]),'additional_evidence_validated':secondary,
                   'decisions':records})
    frame = pd.DataFrame(prior+records).drop_duplicates('keyword_code',keep='last').reset_index(drop=True)
    frame['explicit_remapped_support'] = frame.explicit_remapped_support.map(lambda v: v if isinstance(v,list) else [])
    frame.to_parquet(WORK / 'term_resolution_ledger.parquet',index=False)
    for col in ['evidence_ids','evidence_outcomes','explicit_remapped_support']:
        frame[col] = frame[col].map(lambda v: json.dumps(v,ensure_ascii=False))
    frame.to_csv(WORK / 'term_resolution_ledger.csv',index=False,encoding='utf-8-sig')
    print(json.dumps({'terms_resolved_now':len(records),'terms_resolved':len(frame),
        'context_target_terms':int(queue.keyword_code.nunique()),
        'file':str(output.relative_to(WORK))},ensure_ascii=False))


if __name__ == '__main__':
    main()
