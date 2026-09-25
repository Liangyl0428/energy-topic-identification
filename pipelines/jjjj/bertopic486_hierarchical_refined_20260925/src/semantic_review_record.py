"""Assemble traceable review coverage; refuse to mark unseen samples reviewed."""
from refine_common import *
from decision_guards import guard,quality_veto,ACCEPTED

def main():
    final=read(BASE/'evidence/final_review_samples.json');seen=set();bodies={};logs=[]
    for f in sorted((BASE/'evidence').glob('read_log*.json')):
        x=read(f);logs.append(str(f.relative_to(BASE)))
        for r in x['records']:
            seen.add(int(r['row_id']));bodies[r['row_id']]=max(bodies.get(r['row_id'],0),r.get('body_characters_shown',0))
    missing=[r['row_id'] for r in final['records'] if r['row_id'] not in seen]
    assert not missing,f'Unseen final samples: {missing}'
    accepted=[r for r in final['records'] if r['assignment_status'] in ACCEPTED]
    assert all(guard(r) is None and quality_veto(r) is None for r in accepted)
    all_reviewed=[]
    for filename in ['partial_review_samples.json','round2_review_samples.json','round3_review_samples.json','final_review_samples.json']:
        p=BASE/'evidence'/filename
        if p.exists():all_reviewed.extend(read(p)['records'])
    selected={r['row_id'] for r in all_reviewed};outcomes={}
    parts=read(BASE/'results/ASSIGNMENT_MANIFEST.json')['parts']
    for p in parts:
        ids=sorted(i for i in selected if p['first_row']<=i<p['first_row']+p['n'])
        if not ids:continue
        tab=pq.read_table(BASE/p['file'],columns=['row_id','final_topic_id','final_topic_label','assignment_status','needs_review','review_reason','finalization_action','rule_id'])
        for r in tab.take(pa.array([i-p['first_row'] for i in ids])).to_pylist():outcomes[r['row_id']]=r
    unique={r['row_id']:r for r in all_reviewed};rows=[]
    for rid in sorted(unique):
        r=unique[rid];o=outcomes[rid]
        rows.append(dict(row_id=rid,title=r['title'],**{k:v for k,v in o.items() if k!='row_id'},
            title_reviewed=rid in seen,body_characters_reviewed=bodies.get(rid,0),
            assessment='题名与操作性标签相容；仍非全文人工验收' if o['assignment_status'] in ACCEPTED else '撤回自动主题决定或保留质量隔离/复核，见原因'))
    pd.DataFrame(rows).to_csv(BASE/'review/SEMANTIC_REVIEW_OUTCOMES.csv',index=False,encoding='utf-8-sig')
    rules=read(BASE/'review/final_taxonomy_rules.json')['rules'];summary=read(BASE/'results/SUMMARY.json')
    descriptor_active={r['rule_id'] for r in rules if r['seed_status']=='descriptor_retrieval_only_not_sample_approved' and summary['accepted_rule_counts'].get(r['rule_id'],0)>0}
    read_rules={r['rule_id'] for r in all_reviewed if r['row_id'] in seen}
    audit=dict(created_utc=now(),completed=True,reviewer='assistant semantic diagnostic review',
        unique_titles_reviewed=len(seen & selected),unique_records_with_body_excerpt_reviewed=sum(bodies.get(i,0)>0 for i in selected),
        final_sample_records=len(final['records']),final_sample_topics=final['topics'],final_sample_all_titles_read=True,
        final_sample_accepted=len(accepted),final_sample_deferred_or_quarantined=len(final['records'])-len(accepted),
        known_veto_cases_still_accepted=0,
        active_descriptor_only_rules=len(descriptor_active),active_descriptor_only_rules_with_reviewed_title_evidence=len(descriptor_active & read_rules),
        logs=logs,sample_sha256=sha(BASE/'evidence/final_review_samples.json'),
        methodology='Adaptive topic-stratified diagnosis, precision-guard correction and regression checks. Title review for each final sample, selective excerpts for ambiguity. Saved excerpts not displayed are not counted as read.',
        limitations=['Not a random population accuracy estimate','Not expert reading of every full text','No claim that all 486 baseline parent labels or accepted labels are semantically pure','Undetected errors may remain; pending review and provenance are retained'])
    dump(BASE/'review/FINAL_SEMANTIC_REVIEW.json',audit);print(json.dumps(audit,ensure_ascii=False))

if __name__=='__main__':main()
