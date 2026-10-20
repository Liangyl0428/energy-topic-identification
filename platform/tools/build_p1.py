"""Build the three current modules' P1 business exports entirely offline."""
import importlib.util
import sys
from pathlib import Path
import pandas as pd

FINAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FINAL))
from p1_common import VERSION, TAXONOMY, read, write, sha


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    identification = FINAL / 'energy-topic-identification'
    hotspots = FINAL / 'energy-topic-hotspots'
    maturity = FINAL / 'energy-technology-trl-crl'
    classification_sha = sha(identification / 'assets/full_nmf500/SUMMARY.json')
    for repo in [hotspots, maturity]:
        if read(repo / 'assets/full_nmf500/SUMMARY.json')['classification_summary_sha256'] != classification_sha:
            raise ValueError('Cross-module classification snapshot mismatch')
    identify = load('p1_identification', identification / 'pipelines/business/build.py')
    signals = load('p1_hotspots', hotspots / 'src/energy_hotspots/insights.py')
    sys.path.insert(0, str(maturity))
    from trl_crl.insights import build as build_maturity
    cards, reviews, members, documents, taxonomy = identify.build(identification)
    insights, recomputed = signals.build(hotspots, cards, members, documents, taxonomy)
    cases, distributions = build_maturity(maturity, cards)
    dest = FINAL / 'assets/p1'
    cards_by_id = {r['category_id']: r for r in cards}
    insights_by_id = {r['category_id']: r for r in insights}
    dist_by_id = {r['category_id']: r for r in distributions}
    cases_by_id = {r['case_id']: r for r in cases}
    examples = []
    # The paired-axis cases keep their actual candidate topic association.
    # They are never forced into the three mixed-topic examples.
    example_ids = list(dict.fromkeys(['F0001', 'F0022', 'F0110'] +
                     [cases_by_id[c]['category_id'] for c in ['C0540-N01', 'W001', 'W014']]))
    for cid in example_ids:
        distribution = dist_by_id[cid]
        examples.append({'category_id': cid, 'topic_description': cards_by_id[cid],
                         'trend_insight': insights_by_id[cid],
                         'scope_reviews': [r for r in reviews if r['category_id'] == cid],
                         'reviewed_business_counts': [r for r in recomputed if r['business_topic_id'] in cards_by_id[cid]['business_topic_ids']],
                         'case_distribution': distribution,
                         'case_insights': [cases_by_id[i] for i in distribution['case_ids']],
                         'scope_warning': '算法趋势与已审样本统计属于不同人群；不得互换。对象关联仍需核查。'})
    write(dest / 'platform_examples.json', examples)
    summary = {
        'business_version': VERSION, 'taxonomy_version': TAXONOMY,
        'topic_cards': len(cards), 'detailed_topic_cards': sum(r['reviewed_count'] > 0 for r in cards),
        'numeric_insight_cards': len(insights), 'reviewed_documents': len(reviews),
        'included_documents': len({m['doc_id'] for m in members}),
        'outside_scope_documents': sum(r['decision'] == 'outside_current_energy_scope' for r in reviews),
        'insufficient_evidence_documents': sum(r['decision'] == 'insufficient_evidence' for r in reviews),
        'business_subtopics_with_reviewed_members': sum(r['reviewed_members'] > 0 for r in recomputed),
        'object_insights': len(cases), 'paired_axis_objects': sum(r['paired_axes_usable'] for r in cases),
        'topic_case_distributions': len(distributions), 'joined_examples': len(examples),
        'full_cluster_scope_approved': 0, 'formally_graded_objects': 0,
        'external_network_used': False,
        'full_business_ranking_recomputed': False,
        'reviewed_subset_counts_recomputed': True,
        'remaining_work': [
            '其余 497 个主题需要文献审阅与具体中文业务定义；当前仅有待审字段占位。',
            '三个重点主题尚需跨年份、分类差距和来源的分层复审，再筛选全量成员。',
            '全量业务成员确定后，重新计算领域份额、机构和排名；24 条诊断样本不支持该推断。',
            '对象关联、专属细则与独立专家正式评定仍待完成。',
        ],
    }
    write(dest / 'SUMMARY.json', summary)
    with pd.ExcelWriter(dest / 'P1_review.xlsx', engine='openpyxl') as writer:
        for name, rows in [('主题说明', cards), ('范围审核', reviews), ('新业务范围统计', recomputed),
                           ('趋势洞察', insights), ('对象成熟度', cases), ('主题案例分布', distributions)]:
            import json
            flat = [{k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in rows]
            pd.DataFrame(flat).to_excel(writer, sheet_name=name, index=False)
            sheet = writer.sheets[name]; sheet.freeze_panes = 'A2'; sheet.auto_filter.ref = sheet.dimensions
            for column in sheet.columns:
                sheet.column_dimensions[column[0].column_letter].width = min(55, max(18, len(str(column[0].value)) + 2))
    inputs = [*[repo / 'assets/full_nmf500/SUMMARY.json' for repo in [identification, hotspots, maturity]], identification / 'assets/full_nmf500/topic_catalog.csv',
              *sorted((identification / 'data/business_review').glob('*.json')),
              *[hotspots / 'assets/full_nmf500' / n for n in ['hotspot_metrics.csv', 'quarter_counts.csv', 'institution_citation_context.csv', 'cross_source_signals.csv', 'experiments/rank_intervals.csv']],
              maturity / 'assets/full_nmf500/case_hotspot_links.json',
              *sorted((maturity / 'data').glob('*.json'))]
    code = [Path(__file__), FINAL / 'p1_common.py', identification / 'pipelines/business/build.py',
            hotspots / 'src/energy_hotspots/insights.py', maturity / 'trl_crl/insights.py',
            maturity / 'trl_crl/rules.py', maturity / 'trl_crl/engine.py', maturity / 'trl_crl/pipeline.py', maturity / 'trl_crl/delivery.py']
    write(dest / 'BUILD.json', {'version': VERSION,
                              'inputs': {str(p.relative_to(FINAL)): sha(p) for p in inputs},
                              'code': {str(p.relative_to(FINAL)): sha(p) for p in code},
                              'command': 'python final/tools/build_p1.py', 'network_used': False,
                              'review_sampling': 'top8_nmf_score_per_target_cluster_purposive_not_representative'})
    print(summary)


if __name__ == '__main__':
    main()
