"""Versioned business descriptions and bounded document scope decisions.

The original F500 assignments remain immutable. A review of a diagnostic
sample never approves an entire cluster or creates a ranked business topic.
"""
from collections import Counter
from p1_common import TAXONOMY, VERSION, REVIEWER, read, sha, text_sha, table, write
import pandas as pd


def validate_reviews(documents, reviews, topic_ids, business_topics):
    docs = {d['doc_id']: d for d in documents}
    if len(docs) != len(documents) or len({r['doc_id'] for r in reviews}) != len(reviews):
        raise ValueError('Duplicate review/document identity')
    if set(docs) != {r['doc_id'] for r in reviews}:
        raise ValueError('Every bounded review document requires exactly one decision')
    for r in reviews:
        d = docs[r['doc_id']]
        if r['category_id'] != d['category_id'] or r['category_id'] not in topic_ids:
            raise ValueError('Review topic differs from frozen membership')
        if r['decision'] not in {'include', 'outside_current_energy_scope', 'insufficient_evidence'}:
            raise ValueError('Invalid decision')
        if r['decision'] == 'include':
            if not r['business_topic_ids'] or not set(r['business_topic_ids']) <= business_topics:
                raise ValueError('Included document needs valid business topic references')
        elif r['business_topic_ids']:
            raise ValueError('Unresolved/excluded document cannot enter business membership')
        if not r['quote'] or r['quote'] not in d[r['quote_field']]:
            raise ValueError('Scope decision must cite an exact source excerpt')
        for field in ['title', 'body']:
            if d[field + '_sha256'] != text_sha(d[field]):
                raise ValueError('Review source text changed')


def build(repo):
    base = repo / 'assets/full_nmf500'
    cfg = repo / 'data/business_review'
    taxonomy = read(cfg / 'taxonomy.json')
    defs = read(cfg / 'topic_definitions.json')
    snapshot = read(cfg / 'SOURCE_SNAPSHOT.json')
    if sha(base / 'topic_catalog.csv') != snapshot['topic_catalog_sha256']:
        raise ValueError('Review snapshot belongs to a different topic catalog')
    documents = read(cfg / 'documents.json')
    reviews = read(cfg / 'scope_decisions.json')
    catalog = pd.read_csv(base / 'topic_catalog.csv').to_dict('records')
    business = {x['business_topic_id']: x for x in taxonomy['business_topics']}
    validate_reviews(documents, reviews, {c['category_id'] for c in catalog}, set(business))
    enriched = []
    for r in reviews:
        enriched.append({**r, 'review_id': 'SR-' + r['doc_id'].split(':')[-1],
                         'reviewer_id': REVIEWER, 'reviewer_type': 'assistant',
                         'review_status': 'assistant_reviewed_pending_domain_review',
                         'independent_expert_approved': False,
                         'membership_scope': 'diagnostic_reviewed_subset',
                         'taxonomy_version': TAXONOMY, 'business_version': VERSION})
    cards, mappings, queue = [], [], []
    for c in catalog:
        cid = c['category_id']; own = [r for r in enriched if r['category_id'] == cid]
        definition = defs.get(cid, {})
        bids = sorted({t for r in own for t in r['business_topic_ids']})
        cards.append({
            'category_id': cid, 'algorithm_name': c['name'],
            'display_name_zh': definition.get('display_name_zh', f'{cid}｜业务名称待审核'),
            'definition': definition.get('definition', '当前为关键词形成的算法文献集合；尚未完成业务定义与范围审核。'),
            'business_categories': sorted({b for t in bids for b in business[t]['business_categories']}),
            'business_categories_basis': 'included_diagnostic_documents_only' if bids else 'unreviewed',
            'content_types': definition.get('content_types', []),
            'energy_relevance': definition.get('energy_relevance', '待核查代表文献及具体能源任务。'),
            'application_scenarios': definition.get('application_scenarios', []),
            'included_scope': definition.get('included_scope', []),
            'excluded_scope': definition.get('excluded_scope', []),
            'representative_doc_ids': [r['doc_id'] for r in own if r['decision'] == 'include'],
            'counterexample_doc_ids': [r['doc_id'] for r in own if r['decision'] == 'outside_current_energy_scope'],
            'reviewed_document_ids': [r['doc_id'] for r in own],
            'reviewed_count': len(own), 'paper_documents': c['paper_documents'],
            'review_sampling': 'purposive_diagnostic_not_representative' if own else 'not_sampled',
            'review_status': 'partial_assistant_review_pending_domain_review' if own else 'unreviewed',
            'scope_approved': False, 'rank_eligible': False,
            'business_topic_ids': bids, 'scope_decision_counts': dict(Counter(r['decision'] for r in own)),
            'taxonomy_version': TAXONOMY, 'business_version': VERSION,
            'reviewer_id': REVIEWER if own else None,
        })
        queue.append({'category_id': cid, 'priority': 1 if own else 2,
                      'reviewed_documents': len(own),
                      'remaining_paper_documents': c['paper_documents'] - len(own),
                      'next_action': '按年份、分类差距及来源分层补审；确认业务范围后对全量成员执行筛选与重算。',
                      'status': 'partial_review' if own else 'pending'})
        for bid in bids:
            ids = [r['doc_id'] for r in own if bid in r['business_topic_ids']]
            mappings.append({'from_category_id': cid, 'from_taxonomy_version': TAXONOMY,
                             'to_business_topic_id': bid, 'to_business_version': VERSION,
                             'relation': 'reviewed_subset_of_mixed_cluster', 'doc_ids': ids,
                             'whole_cluster_relabel': False, 'requires_recompute': True,
                             'review_status': 'assistant_reviewed_pending_domain_review'})
    members = []
    for r in enriched:
        for bid in r['business_topic_ids']:
            d = next(d for d in documents if d['doc_id'] == r['doc_id'])
            members.append({'doc_id': r['doc_id'], 'category_id': r['category_id'],
                            'business_topic_id': bid, 'date': d['date'], 'source': d['source'],
                            'review_id': r['review_id'], 'scope': 'diagnostic_reviewed_subset',
                            'business_version': VERSION, 'rank_eligible': False})
    for name, rows in [('topic_business_cards', cards), ('scope_reviews', enriched),
                       ('topic_business_mappings', mappings), ('reviewed_memberships', members),
                       ('scope_review_queue', queue), ('scope_evidence', documents)]:
        table(base / 'p1' / name, rows)
    write(base / 'p1/business_taxonomy.json', taxonomy)
    write(base / 'p1/INPUTS.json', {'version': VERSION, 'files': {
        str(p.relative_to(repo)): sha(p) for p in [base / 'topic_catalog.csv', *sorted(cfg.glob('*.json'))]}})
    return cards, enriched, members, documents, taxonomy
