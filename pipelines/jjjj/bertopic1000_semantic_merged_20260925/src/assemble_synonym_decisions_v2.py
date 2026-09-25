"""Assemble the explicit semantic decisions and an honest record of inspected evidence."""
from merge_common import *
from itertools import combinations
from semantic_mapping import make_mapping

BACKUP=BASE/'history/v1_998_before_synonym_merge'
SUPPORT={
    'SYN001':[3236413,4268823,233064,3002279,531542,2415843],
    'SYN002':[2695199,2068449,3203481,831748,1101570,3313464,4589521],
    'SYN003':[3111065,4166646,1712341,4579998,480233,690044,1572690,4829655],
    'SYN004':[4027015,2974257,1991049,3202124,2133091,3750751],
    'SYN005':[4951339,4981724,4980979,4964059,4837181,4872993,4992694,4840102,5075052,5107700],
    'SYN006':[3843605,4737406,4205675,4365697,497024,1275517,4490372],
    'SYN007':[3577257,3627034,4934932,4999512,2704749,1703616,4998949,4698102],
    'SYN008':[3916990,4099311,4934275,4992719,1507582,3911502,4884719,5017256],
}

def main():
    prior=read(BACKUP/'review/decisions.json')
    prior_inspected=read(BACKUP/'review/ACTUALLY_INSPECTED.json')
    review=read(BASE/'review/synonym_review_v2.json')
    files=sorted((BASE/'evidence').glob('synonyms_v2_*.json'))
    records={}
    body_chars={}
    for f in files:
        for r in read(f)['records']:
            records[r['row_id']]=r
            body_chars[r['row_id']]=max(body_chars.get(r['row_id'],0),len(r['body_excerpt']))
    fresh=read(BASE/'evidence/fresh_synonym_audit_v2.json')
    for r in fresh['records']:
        records[r['row_id']]={**r,'topic':r['cluster']}
        body_chars[r['row_id']]=min(320,len(r['body_excerpt'])) if r['cluster'] in [381,876,616,948] else 0
    new_topics=sorted({r['topic'] for r in records.values()})
    detail=sorted(set(prior_inspected['detailed_topics'])|set(new_topics))
    old_ids=set()
    for f in prior_inspected['detail_packets']+[prior_inspected['fresh_random_file']]:
        old_ids.update(r['row_id'] for r in read(BACKUP/f)['records'])
    groups=prior['merge_groups']+review['new_merge_groups']
    for g in groups:
        if g['decision_id'].startswith('SYN'):
            g.update(decision='merge',scope='whole_cluster_only',
                supporting_row_ids=SUPPORT[g['decision_id']],
                evidence_row_ids=sorted(rid for rid,r in records.items() if r['topic'] in g['members']),
                review_method='模型语义判断；20个主题词、中心/随机/边界完整题名、明确展示的正文片段及每类8条新增随机题名')
            assert set(g['supporting_row_ids'])<=set(g['evidence_row_ids'])
    anchor,lookup,anchors=make_mapping(groups)
    keep={}
    for g in prior['keep_or_defer']:
        for pair in combinations(sorted(g['members']),2):
            keep[pair]={**g,'members':list(pair)}
    for n,r in enumerate(review['candidate_reviews']):
        assert set(r['members'])<=set(new_topics)
        for a,b in combinations(sorted(r['members']),2):
            if anchor[a]==anchor[b]:
                continue
            keep[(a,b)]=dict(members=[a,b],decision='keep_separate',decision_id=f'V2K{n+1:03d}_{a:04d}_{b:04d}',
                reason=r['reason'],evidence_row_ids=sorted(rid for rid,x in records.items() if x['topic'] in [a,b]),
                review_method='主题词及所列题名/正文抽样复核；语义不足或范围不同则保留')
    for pair in list(keep):
        if anchor[pair[0]]==anchor[pair[1]]:
            del keep[pair]
    actual=dict(created_utc=now(),reviewer=review['reviewer'],
        inventory_screen=dict(topics=1000,scope='全部类别前5主题词和前三相邻类编号；候选进一步阅读20词及文献',
            source='review/topic_cards.json',read_ranges=[[0,349],[350,699],[700,999]]),
        title_review_topics=new_topics,unique_documents=len(records),
        existing_sample_documents=len(records)-len(fresh['records']),
        additional_random_documents=len(fresh['records']),
        nonempty_body_excerpts_read=sum(n>0 for n in body_chars.values()),
        actual_body_characters_by_row={str(k):v for k,v in sorted(body_chars.items()) if v>0},
        title_row_ids=sorted(records),candidate_groups=len(review['candidate_reviews']),
        evidence_files=[str(f.relative_to(BASE)) for f in files]+['evidence/fresh_synonym_audit_v2.json'],
        full_corpus_manual_review=False,independent_expert_review=False,semantic_accuracy=None)
    dump(BASE/'review/ACTUALLY_INSPECTED_v2.json',actual)
    combined={**prior_inspected,'created_utc':now(),'detailed_topics':detail,
        'unique_documents':len(set(records)|old_ids),'current_review_unique_documents':len(records),
        'prior_review_unique_documents':len(old_ids),
        'additional_random_documents':len(fresh['records'])+len(read(BACKUP/prior_inspected['fresh_random_file'])['records']),
        'current_additional_random_documents':len(fresh['records']),
        'current_review_file':'review/ACTUALLY_INSPECTED_v2.json',
        'current_evidence_files':actual['evidence_files'],
        'shown_excerpt_records':None,
        'count_note':'unique_documents为当前题名审阅与历史已记录审阅的去重并集，不表示每条都有全文；正文实际展示量见v2记录。'}
    dump(BASE/'review/ACTUALLY_INSPECTED.json',combined)
    dump(BASE/'review/decisions.json',dict(version='semantic-1000-20260925-v2-synonyms',created_utc=now(),
        reviewer=review['reviewer'],criteria=prior['criteria'],policy=review['policy'],merge_groups=groups,
        keep_or_defer=list(keep.values()),previous_version=prior['version'],new_merge_groups=len(review['new_merge_groups']),
        review_limit='1000类主题词清单全覆盖；候选抽样语义复核及新增随机审阅。未逐篇重分类，不把相似阈值当作同义判据；不宣称穷尽所有同义关系。'))
    print(json.dumps(dict(final_topics=len(anchors),total_merge_groups=len(groups),new_merge_groups=len(review['new_merge_groups']),
        current_review_topics=len(new_topics),current_documents=len(records),cumulative_review_topics=len(detail),
        cumulative_documents=combined['unique_documents'],explicit_kept_pairs=len(keep)),ensure_ascii=False))

if __name__=='__main__':
    main()
