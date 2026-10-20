"""Meaningful guards against false scope, duplicate denominators and grade inflation."""
import importlib.util
import json
import sys
from pathlib import Path
import pytest
import pandas as pd

FINAL=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(FINAL/'tools'))
from p2_taxonomy import taxonomy
from build_p2 import match_title,describe_trend
TOPICS={t['business_topic_id']:t for t in taxonomy()}
def read(p):return json.loads((FINAL/p).read_text())

@pytest.mark.parametrize('bid,title,expected',[
 ('D01','Analysis of Neutral Point Over-Volatge Protection for 110kV Transformer',True),
 ('D01','CNN-Transformer for photovoltaic power forecasting',False),
 ('D01','Transformer Insulation Health Assessment using a Neural Network',True),
 ('D02','Transmission line model for porous electrode impedance',False),
 ('D02','Fault location in 500 kV transmission lines',True),
 ('E03','Hydroelectric cell based on lithium-substituted hematite',False),
 ('S07','Biochar reduces soil volumetric heat storage',False),
 ('S11','Recyclable Solid Electrolyte for Lithium-Based Batteries',False),
 ('S12','Membranes for electrochemical energy storage',False),
 ('U01','Vehicle speed control for distributed drive electric vehicles',False),
 ('U01','Electric vehicle charging load forecasting',True),
 ('G01','Probabilistic Archaeological Record Analysis',False),
 ('G01','Hybrid Prophet–TCN Probabilistic Wind-Power Forecasting',True),
 ('S02','Lithium-metal batteries with porous interfaces',True),
 ('S02','Porous MXene for osteosarcoma therapy',False),
])
def test_task_boundary_regressions(bid,title,expected):
    assert bool(match_title(title,TOPICS[bid])) is expected


def test_growth_uses_population_share_not_raw_count_or_overlap_sum():
    r=describe_trend(200,100,4000,1000,4,100)
    assert r['share_growth_ratio']==.5 and r['signal']=='份额下降'
    assert describe_trend(100,0,1000,1000,4,50)['share_growth_ratio'] is None
    assert describe_trend(200,10,1000,1000,4,50)['attention']=='观察'
    assert describe_trend(200,100,1000,1000,4,50)['attention']=='优先研读'


def test_actual_quarters_and_denominators_reconcile():
    rows=read('energy-topic-hotspots/assets/full_nmf500/p2/business_insights.json')
    q=pd.read_csv(FINAL/'energy-topic-hotspots/assets/full_nmf500/p2/business_quarter_counts.csv')
    d=pd.read_csv(FINAL/'energy-topic-hotspots/assets/full_nmf500/p2/population_quarter_counts.csv').set_index('period').papers
    assert len(rows)==len(TOPICS) and len(q)==20*len(rows)
    assert not q.duplicated(['business_topic_id','period']).any()
    assert all(q.denominator_papers==q.period.map(d))
    for r in rows:
        own=q[q.business_topic_id==r['business_topic_id']]
        for name,low,high in [('recent','2025Q3','2026Q2'),('previous','2024Q3','2025Q2')]:
            selected=own[own.period.between(low,high)]
            assert r[name+'_papers']==int(selected.papers.sum())
            assert r[name+'_denominator']==int(selected.denominator_papers.sum())
        ratio=r['recent_share']/r['previous_share'] if r['previous_share'] else None
        assert r['share_growth_ratio']==pytest.approx(ratio)
        assert not r['scope_approved'] and not r['rank_eligible']
        assert r['potential_assessment']['future_potential_score'] is None


def test_evidence_quotes_and_no_claimed_expert_reviews():
    rows=read('energy-topic-identification/assets/full_nmf500/p2/evidence_samples.json')
    for r in rows:
        assert r['matched_quotes'] and all(q in r['title'] for q in r['matched_quotes'])
        assert r['matched_quotes']==match_title(r['title'],TOPICS[r['business_topic_id']])
    reviews=read('energy-topic-identification/data/business_v2/development_title_review.json')
    assert len(reviews)==102
    for r in reviews:
        assert r['reviewer_type']=='assistant' and not r['independent_expert_review']
        if r['decision']=='remove_from_this_title_scope':
            assert not match_title(r['title'],TOPICS[r['business_topic_id']]),r


def test_all_500_f_bridges_preserve_counts_and_identity():
    rows=read('energy-topic-identification/assets/full_nmf500/p2/f_topic_bridge.json')
    assert len(rows)==500 and len({r['category_id'] for r in rows})==500
    for r in rows:
        assert r['matched_unique_papers']+r['unresolved_papers']==r['paper_documents']
        assert not r['whole_cluster_relabel'] and not r['scope_approved']
        assert r['unresolved_papers']>=0
        assert sum(b['documents'] for b in r['business_composition'])>=r['matched_unique_papers']


def test_case_grades_unchanged_and_candidate_links_have_exact_object_quotes():
    original={r['case_id']:r for r in read('energy-technology-trl-crl/assets/full_nmf500/p1/case_insights.json')}
    rows=read('energy-technology-trl-crl/assets/full_nmf500/p2/case_decision_cards.json')
    assert len(rows)==122
    for r in rows:
        old=original[r['case_id']]
        for axis in ['trl','crl']:
            assert r[axis+'_public_evidence_stage']==old[axis+'_public_evidence_stage']
        assert r['formal_trl'] is None and r['formal_crl'] is None
        assert r['canonical_name'] in r['decision_brief']
        assert r['specific_questions']
        for link in r['business_links']:
            assert all(q in r[link['quote_field']] for q in link['quotes'])


def test_full_membership_recounts_and_unresolved_examples():
    import duckdb
    workspace=FINAL.parent/'work/business_p2_20261019/business.duckdb'
    if not workspace.exists():pytest.skip('Full memberships stay in workspace; compact integration tests remain portable')
    con=duckdb.connect(str(workspace),read_only=True)
    assert con.execute('SELECT count(*) FROM population').fetchone()[0]==5119004
    assert con.execute('SELECT count(*)-count(DISTINCT doc_id) FROM population').fetchone()[0]==0
    assert con.execute('SELECT count(*) FROM (SELECT doc_id,business_topic_id,count(*) n FROM members GROUP BY ALL HAVING n>1)').fetchone()[0]==0
    for did in ['paper:W7134113234','paper:W7106791247','paper:W234978226']:
        assert con.execute('SELECT count(*) FROM members WHERE doc_id=?',[did]).fetchone()[0]==0
    assert con.execute("SELECT count(*) FROM members WHERE doc_id='paper:W2348415734' AND business_topic_id='D01'").fetchone()[0]==1
    for r in read('energy-topic-hotspots/assets/full_nmf500/p2/business_insights.json'):
        n=con.execute("SELECT count(*) FROM members m JOIN population p USING(doc_id) WHERE business_topic_id=? AND source='paper' AND eligible AND date BETWEEN '2025-07-01' AND '2026-06-30'",[r['business_topic_id']]).fetchone()[0]
        assert n==r['recent_papers']
    con.close()
