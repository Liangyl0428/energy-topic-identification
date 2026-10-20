"""Regression checks for misleading conclusions, source drift and typed APIs."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import pandas as pd
import pytest

FINAL = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(FINAL), str(FINAL / 'energy-technology-trl-crl')]
from p1_common import read, sha, WINDOWS
from trl_crl.insights import joint_interpretation
from trl_crl.pipeline import assess

ID = 'energy-topic-identification'
HOT = 'energy-topic-hotspots'
MAT = 'energy-technology-trl-crl'


def artifact(module, name):
    return read(FINAL / module / 'assets/full_nmf500/p1' / (name + '.json'))


def load_builder():
    path = FINAL / ID / 'pipelines/business/build.py'
    spec = importlib.util.spec_from_file_location('p1_review_test', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_build_input_and_code_fingerprints():
    build = read(FINAL / 'assets/p1/BUILD.json')
    for kind in ['inputs', 'code']:
        for path, digest in build[kind].items():
            assert sha(FINAL / path) == digest, path


def test_no_scope_approval_from_sample_or_keyword_names():
    cards = artifact(ID, 'topic_business_cards')
    assert len(cards) == 500
    assert sum(c['reviewed_count'] > 0 for c in cards) == 3
    assert sum(c['reviewed_count'] for c in cards) == 24
    assert all(not c['scope_approved'] and not c['rank_eligible'] for c in cards)
    f22 = next(c for c in cards if c['category_id'] == 'F0022')
    assert '混合' in f22['display_name_zh'] and len(f22['business_topic_ids']) > 1
    for m in artifact(ID, 'topic_business_mappings'):
        assert not m['whole_cluster_relabel'] and m['requires_recompute']


def test_review_quotes_and_reclassification_of_known_errors():
    docs = {r['doc_id']: r for r in artifact(ID, 'scope_evidence')}
    reviews = {r['doc_id']: r for r in artifact(ID, 'scope_reviews')}
    for r in reviews.values():
        assert r['quote'] in docs[r['doc_id']][r['quote_field']]
        assert r['reviewer_type'] == 'assistant' and not r['independent_expert_approved']
    assert reviews['paper:W7134113234']['decision'] == 'outside_current_energy_scope'
    assert reviews['paper:W2348415734']['business_topic_ids'] == ['B-GRID-PROTECTION']
    assert reviews['paper:W2354627511']['business_topic_ids'] == ['B-POWER-MARKET']
    assert reviews['paper:W7160693920']['decision'] == 'insufficient_evidence'
    included = {r['doc_id'] for r in reviews.values() if r['decision'] == 'include'}
    assert {r['doc_id'] for r in artifact(ID, 'reviewed_memberships')} == included
    assert len(included) == 11


@pytest.mark.parametrize('mutation', ['quote', 'duplicate', 'topic', 'unresolved_membership'])
def test_reject_invalid_review_inputs(mutation):
    builder = load_builder()
    docs = artifact(ID, 'scope_evidence'); reviews = artifact(ID, 'scope_reviews')
    if mutation == 'quote': reviews[0]['quote'] = 'not present in source'
    elif mutation == 'duplicate': reviews.append(copy.deepcopy(reviews[0]))
    elif mutation == 'topic': reviews[0]['category_id'] = 'F0999'
    else:
        r = next(r for r in reviews if r['decision'] != 'include')
        r['business_topic_ids'] = ['B-GRID-PROTECTION']
    bids = {r['business_topic_id'] for r in read(FINAL / ID / 'assets/full_nmf500/p1/business_taxonomy.json')['business_topics']}
    with pytest.raises(ValueError):
        builder.validate_reviews(docs, reviews, {c['category_id'] for c in artifact(ID, 'topic_business_cards')}, bids)


def test_signal_numbers_are_source_values_and_decline_is_not_emergence():
    facts = pd.read_csv(FINAL / HOT / 'assets/full_nmf500/hotspot_metrics.csv').set_index('category_id')
    contexts = pd.read_csv(FINAL / HOT / 'assets/full_nmf500/institution_citation_context.csv').set_index('category_id')
    cards = {c['category_id']: c for c in artifact(HOT, 'topic_insights')}
    for cid, card in cards.items():
        for field in ['recent_papers', 'previous_papers', 'share_growth_ratio', 'growing_quarters']:
            assert card['key_numbers'][field] == facts.loc[cid, field]
        assert card['key_numbers']['previous_institutions'] == contexts.loc[cid, 'year1_institutions']
        assert card['key_numbers']['recent_institutions'] == contexts.loc[cid, 'year0_institutions']
        assert card['population_scope'] == 'original_algorithm_cluster'
        assert card['future_potential_score'] is None and not card['rank_eligible']
        assert card['windows'] == WINDOWS
    assert '下降' in cards['F0022']['judgment']
    assert cards['F0110']['key_numbers']['recent_papers'] == 1612
    assert cards['F0110']['key_numbers']['previous_papers'] == 470
    assert cards['F0110']['key_numbers']['previous_institutions'] == 573


def test_all_insight_references_resolve_to_actual_rows():
    cache = {}
    for card in artifact(HOT, 'topic_insights') + artifact(HOT, 'reviewed_scope_metrics'):
        for ref in card['evidence_refs']:
            path = FINAL / ref['artifact']
            if path not in cache:
                cache[path] = pd.read_csv(path) if path.suffix == '.csv' else pd.DataFrame(read(path))
            rows = cache[path]
            for key, value in ref['record_key'].items(): rows = rows[rows[key].eq(value)]
            assert len(rows), ref
            assert set(ref['fields']) <= set(rows.columns)


def test_reviewed_subset_recounts_do_not_inherit_old_ranks():
    rows = {r['business_topic_id']: r for r in artifact(HOT, 'reviewed_scope_metrics')}
    assert rows['B-WIND-FORECAST']['recent_papers'] == 1
    assert rows['B-WIND-FORECAST']['previous_papers'] == 0
    assert rows['B-WIND-FORECAST']['recent_institutions'] == 2
    assert rows['B-BATTERY-INTERFACE']['recent_institutions'] == 4
    assert rows['B-POWER-MARKET']['recent_papers'] == 0  # source is from 2006
    for row in rows.values():
        for field in ['share_growth_ratio', 'core_score', 'emerging_score', 'core_rank', 'emerging_rank']:
            assert row[field] is None
        assert row['membership_scope'] == 'diagnostic_reviewed_subset' and not row['rank_eligible']
        assert row['sampling_denominator'] == 24
    quarters = artifact(HOT, 'reviewed_quarter_counts')
    assert len(quarters) == 20 * len(rows)
    for bid, row in rows.items():
        recent = [q for q in quarters if q['business_topic_id'] == bid and '2025Q3' <= q['period'] <= '2026Q2']
        assert sum(q['papers'] for q in recent) == row['recent_papers']
        assert all(len(q['doc_ids']) == q['papers'] for q in recent)


def test_maturity_matches_unchanged_engine_and_unknown_contract():
    _, result = assess(FINAL / MAT / 'data')
    truth = {r['case_id']: r for r in result['assessment_units']}
    rows = artifact(MAT, 'case_insights')
    assert len(rows) == 122 and sum(r['paired_axes_usable'] for r in rows) == 13
    for r in rows:
        for a in ['trl', 'crl']:
            stage = r[a + '_public_evidence_stage']
            assert stage == truth[r['case_id']][a + '_public_evidence_stage']
            assert stage is None or type(stage) is int
            if stage is None:
                assert r[a + '_next_stage_to_investigate'] is None
                assert r[a + '_evidence_gap_requirements']
            assert r[a + '_next_actions']
        assert r['formal_trl'] is None and r['formal_crl'] is None
    assert '同一配置' in joint_interpretation(3, 4)
    assert '未知' in joint_interpretation(4, None)
    assert '实际履约' in joint_interpretation(9, 2)


def test_gate_evidence_is_same_object_and_exact_source_quote():
    evidence = {r['evidence_id']: r for r in artifact(MAT, 'evidence_index')}
    obs = {r['observation_id']: r for r in artifact(MAT, 'observation_index')}
    gates = {r['gate_id']: r for r in artifact(MAT, 'gate_evidence')}
    for gate in gates.values():
        for oid in gate['observation_ids']:
            observation = obs[oid]; e = evidence[observation['evidence_id']]
            assert e['case_id'] == observation['case_id'] == gate['case_id']
            assert observation['quote'] in e['quote']
            assert e['evidence_id'] in gate['evidence_ids']
    for row in artifact(MAT, 'case_insights'):
        for axis in ['trl', 'crl']:
            for gid in row[axis + '_supported_gate_ids']:
                assert gates[gid]['effective_status'] == 'met'
                assert gates[gid]['evidence_ids']
            for gap in row[axis + '_evidence_gap_requirements']:
                assert gates[gap['gate_id']]['effective_status'] != 'met'


def test_distributions_do_not_grade_topics_or_double_count():
    rows = artifact(MAT, 'topic_case_distributions')
    assert len(rows) == 500 and sum(r['case_count'] for r in rows) == 122
    assert sum(len(r['paired_case_ids']) for r in rows) == 13
    for r in rows:
        assert r['theme_trl'] is None and r['theme_crl'] is None
        assert sum(r['trl_distribution'].values()) == r['case_count']
        assert sum(r['crl_distribution'].values()) == r['case_count']
    examples = read(FINAL / 'assets/p1/platform_examples.json')
    assert len(examples) == 6
    for example in examples:
        assert all(r['category_id'] == example['category_id'] for r in example['case_insights'])


def test_p0_original_artifacts_unchanged():
    # Frozen initial P1 backup contains the already fixed P0 exports.
    baseline = read(FINAL / 'provenance/P1_BASELINE.json')['files']
    for path, digest in baseline.items():
        if '/assets/full_nmf500/' in path and not path.endswith(('MANIFEST.json', 'POSTPROCESS_DELIVERY.json')):
            assert sha(FINAL / path) == digest, path
