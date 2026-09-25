"""Deterministic second pass, immutable initial decisions, usable indices and audit tables."""
from refine_common import *
from decision_guards import *
from classify import SPECIAL
from collections import Counter

REASONS={
 'parent_retained_needs_review':'原宽泛/混杂主类，未找到足够明确的单一子类证据',
 'multiple_tasks_pending':'多种对象或任务同时命中，尚未确定主任务',
 'abstract_task_pending':'任务仅在摘要/正文出现，不能排除背景提及',
 'broader_parent_suggestion_only':'迁移到宽泛主类可能损失原研究方向',
 'cross_parent_margin_pending':'跨主类向量支持未达到启发式门槛',
 'cleaned_pending_reclassification':'模板已清理，真实主题仍须复核',
 'peripheral_parent_retained':'原外围或非研究类，未有充分证据恢复研究主题',
 'quality_quarantine':'文本质量隔离；见quality_status及quality_flags',
}

def main():
    parts=read(OLD/'data/INPUT_MANIFEST.json')['parts'];n=sum(p['n'] for p in parts)
    assert len(list((BASE/'logs').glob('part-*.json')))==len(parts),'Initial classification incomplete'
    initial=BASE/'results/initial_assignments';final=BASE/'results/assignments'
    if not initial.exists():final.rename(initial)
    final.mkdir(exist_ok=True)
    for sub in ['pending_review','label_changes','decision_reversions']:(BASE/'results'/sub).mkdir(exist_ok=True)
    old=pd.read_csv(OLD/'results/merged_topics.csv').fillna('')
    oldstatus=old.set_index('merged_topic_id').status.to_dict()
    names=old.set_index('merged_topic_id').name.to_dict()
    parents={k:k for k in names};kind={k:'parent' for k in names}
    spec=read(BASE/'review/taxonomy_rules.json')['rules']
    children={}
    for s in spec:
        tid=canonical_topic(s['topic_id'])
        if s['is_child'] and tid not in names:
            children[tid]=dict(s,topic_id=tid,name=NAME_OVERRIDES.get(tid,s['name']))
            if tid=='M128.food_sludge':children[tid]['definition']='明确餐厨垃圾、厨余或污泥厌氧消化；与粪便/农业残余共同消化时保留主类并复核。'
    for tid,s in children.items():names[tid]=s['name'];parents[tid]=s['parent_id'];kind[tid]='child'
    for tid,name in SPECIAL.items():names[tid]=name;parents[tid]='';kind[tid]='quality'
    ids=list(old.merged_topic_id)+sorted(children)+sorted(SPECIAL)
    lut={tid:i for i,tid in enumerate(ids)};plut={tid:i for i,tid in enumerate(old.merged_topic_id)}
    arr=np.lib.format.open_memmap(BASE/'results/final_labels.npy',mode='w+',dtype=np.int32,shape=(n,))
    parr=np.lib.format.open_memmap(BASE/'results/final_parent_labels.npy',mode='w+',dtype=np.int32,shape=(n,))
    leafarr=np.lib.format.open_memmap(BASE/'results/analysis_leaf_labels.npy',mode='w+',dtype=np.int32,shape=(n,))
    needs=np.lib.format.open_memmap(BASE/'results/needs_review.npy',mode='w+',dtype=np.bool_,shape=(n,))
    counts={k:Counter() for k in ['status','quality','source','topic','parent','eligible_parent','eligible_leaf','accepted_topic','reason','flags','old_changed','old_parent_changed','old_review','old_quarantine','old_child','old_accepted','old_retained','source_changed','old_cleaned','reversion_rule']}
    flows=Counter();rulecounts=Counter();manifest=[];reversions=Counter();totals=Counter();review_manifest=[]
    for pi,p in enumerate(parts):
        f=initial/Path(p['file']).name;df=pq.read_table(f).to_pandas();rows=df.to_dict('records');reverted=[]
        for r in rows:
            r['old_parent_status']=oldstatus.get(r['old_parent_id'],'')
            r['initial_topic_id']=r['final_topic_id'];r['initial_assignment_status']=r['assignment_status']
            r['initial_quality_status']=r['quality_status']
            r['finalization_action']='unchanged_initial_decision';r['review_reason']=''
            quality_reason=quality_veto(r)
            if quality_reason and r['quality_status']!='unusable_original':
                r.update(final_topic_id='Q.EDITORIAL',final_parent_id='',assignment_status='quality_quarantine',
                         quality_status='nonresearch_editorial',needs_review=False,finalization_action='editorial_quality_override',
                         review_reason=quality_reason,quality_flags='|'.join(filter(None,[r['quality_flags'],'second_pass_editorial_title'])))
            r,rev=apply(r,oldstatus)
            if rev:
                r['finalization_action']='guard_reverted';r['review_reason']=rev['reason'];reverted.append(rev)
                reversions[rev['reason']]+=1;counts['reversion_rule'][r['rule_id']]+=1
            if r['final_topic_id'] in ALIASES:
                r['final_topic_id']=canonical_topic(r['final_topic_id'])
                r['finalization_action']='canonical_owner_normalized'
            if r['candidate_topic_ids']:
                r['candidate_topic_ids']='|'.join(sorted({canonical_topic(t) for t in r['candidate_topic_ids'].split('|') if t}))
            tid=r['final_topic_id'];assert tid in names,(r['row_id'],tid)
            r['final_topic_label']=names[tid];r['final_parent_id']=parents[tid]
            r['parent_changed']=r['final_parent_id']!=r['old_parent_id']
            r['topic_changed']=tid!=r['old_parent_id']
            r['final_topic_index']=lut[tid];r['final_parent_index']=plut.get(r['final_parent_id'],-1)
            r['priority_parent']=r['old_parent_status'] in {'宽泛待细分','混杂待重分'}
            accepted=r['assignment_status'] in ACCEPTED
            if accepted:
                r['assignment_status']='reclassified_after_cleaning' if r['text_cleaned'] else 'cross_parent_reclassified' if r['parent_changed'] else 'refined_child' if kind[tid]=='child' else 'parent_supported'
            r['eligible_for_leaf_analysis']=bool(accepted and kind[tid]=='child' and not r['retracted'])
            r['eligible_for_accepted_topic_analysis']=bool(accepted and kind[tid]!='quality' and not r['retracted'])
            r['eligible_for_parent_counts']=bool(r['final_parent_id'] and not r['retracted'])
            # Backward-compatible field is explicitly the coarse parent-count flag.
            r['eligible_for_topic_counts']=r['eligible_for_parent_counts']
            r['label_origin']='quality_quarantine' if kind[tid]=='quality' else 'automatic_title_rule_and_semantic_support' if accepted else 'retained_baseline_parent_not_newly_verified'
            if r['needs_review'] and not r['review_reason']:r['review_reason']=REASONS.get(r['assignment_status'],'参见候选标签及证据字段')
            r['review_priority']=0 if not r['needs_review'] else 1 if r['text_cleaned'] or r['assignment_status'] in {'precision_guard_pending','quality_quarantine'} else 2 if r['assignment_status']=='multiple_tasks_pending' else 3 if r['candidate_topic_ids'] else 4
        out=pd.DataFrame(rows)
        first=p['first_row'];stop=first+p['n']
        assert np.array_equal(out.row_id.to_numpy(),np.arange(first,stop))
        arr[first:stop]=out.final_topic_index;parr[first:stop]=out.final_parent_index
        leafarr[first:stop]=np.where(out.eligible_for_leaf_analysis,out.final_topic_index,-1)
        needs[first:stop]=out.needs_review
        outfile=final/f.name;pq.write_table(pa.Table.from_pandas(out,preserve_index=False),outfile,compression='zstd')
        pending=out[out.needs_review]
        reviewcols=['row_id','doc_id','source','title','old_parent_id','old_parent_name','final_topic_id','final_topic_label','assignment_status','candidate_topic_ids','review_reason','review_priority','rule_id','text_evidence_level','semantic_support_cosine','quality_status','quality_flags','text_cleaned','retracted','priority_parent']
        rp=BASE/'results/pending_review'/f.name
        pq.write_table(pa.Table.from_pandas(pending[reviewcols],preserve_index=False),rp,compression='zstd')
        review_manifest.append(dict(file=str(rp.relative_to(BASE)),documents=len(pending),sha256=sha(rp)))
        changed=out[out.topic_changed]
        pq.write_table(pa.Table.from_pandas(changed,preserve_index=False),BASE/'results/label_changes'/f.name,compression='zstd')
        revfile=BASE/'results/decision_reversions'/f.name
        if reverted:pq.write_table(pa.Table.from_pylist(reverted),revfile,compression='zstd')
        elif revfile.exists():revfile.unlink()
        for k,col in [('status','assignment_status'),('quality','quality_status'),('source','source'),('topic','final_topic_id'),('parent','final_parent_id'),('reason','review_reason')]:counts[k].update(out[col].value_counts().to_dict())
        for k,mask,col in [
            ('eligible_parent',out.eligible_for_parent_counts,'final_parent_id'),('eligible_leaf',out.eligible_for_leaf_analysis,'final_topic_id'),
            ('accepted_topic',out.eligible_for_accepted_topic_analysis,'final_topic_id'),('old_changed',out.topic_changed,'old_parent_id'),
            ('old_parent_changed',out.parent_changed,'old_parent_id'),('old_review',out.needs_review,'old_parent_id'),
            ('old_quarantine',out.final_parent_id.eq(''),'old_parent_id'),('old_child',out.final_topic_id.str.contains('.',regex=False),'old_parent_id'),
            ('old_accepted',out.assignment_status.isin(ACCEPTED),'old_parent_id'),('old_retained',out.final_topic_id.eq(out.old_parent_id),'old_parent_id'),
            ('source_changed',out.topic_changed,'source'),('old_cleaned',out.text_cleaned,'old_parent_id')]:
            # Q.* quality bins are never counted as child labels.
            if k=='old_child':mask=mask & ~out.final_topic_id.str.startswith('Q.')
            counts[k].update(out.loc[mask,col].value_counts().to_dict())
        for x in out.loc[out.quality_flags.ne(''),'quality_flags']:
            counts['flags'].update(x.split('|'))
        for key,v in out.groupby(['old_parent_id','final_parent_id','final_topic_id']).size().items():flows[key]+=int(v)
        rulecounts.update(out.loc[out.assignment_status.isin(ACCEPTED),'rule_id'].value_counts().to_dict())
        for col in ['topic_changed','parent_changed','needs_review','text_cleaned','retracted','eligible_for_leaf_analysis','eligible_for_accepted_topic_analysis','eligible_for_parent_counts','priority_parent']:
            totals[col]+=int(out[col].sum())
        totals['documents']+=len(out);totals['reverted_decisions']+=len(reverted)
        totals['accepted_changed_labels']+=int((out.topic_changed&out.assignment_status.isin(ACCEPTED)).sum())
        totals['accepted_cross_parent']+=int((out.parent_changed&out.assignment_status.isin(ACCEPTED)).sum())
        totals['priority_accepted_changed']+=int((out.priority_parent&out.topic_changed&out.assignment_status.isin(ACCEPTED)).sum())
        totals['priority_needs_review']+=int((out.priority_parent&out.needs_review).sum())
        totals['cleaned_reclassified']+=int((out.text_cleaned&out.assignment_status.isin(ACCEPTED)).sum())
        totals['canonicalized_decisions']+=int(out.finalization_action.eq('canonical_owner_normalized').sum())
        manifest.append(dict(file=str(outfile.relative_to(BASE)),n=len(out),first_row=first,sha256=sha(outfile)))
        if pi%10==0 or pi==len(parts)-1:progress('finalizing',completed_parts=pi+1,total_parts=len(parts),documents=totals['documents'])
    for a in [arr,parr,leafarr,needs]:a.flush()
    catalog=[]
    for tid in ids:
        catalog.append(dict(topic_index=lut[tid],topic_id=tid,name=names[tid],parent_id=parents[tid],kind=kind[tid],
            assigned_documents=counts['topic'][tid],inclusive_parent_documents=counts['parent'][tid] if kind[tid]=='parent' else 0,
            eligible_leaf_documents=counts['eligible_leaf'][tid],accepted_topic_documents=counts['accepted_topic'][tid],enabled=counts['topic'][tid]>0 or kind[tid]=='parent'))
    pd.DataFrame(catalog).to_csv(BASE/'results/topic_dictionary.csv',index=False,encoding='utf-8-sig')
    parentrows=[]
    plan=pd.read_csv(BASE/'results/parent_processing_plan.csv').set_index('parent_id').to_dict('index')
    for r in old.to_dict('records'):
        tid=r['merged_topic_id'];r.update(parent_id=tid,original_documents=r['documents'],final_inclusive_documents=counts['parent'][tid],
            final_direct_parent_documents=counts['topic'][tid],accepted_child_documents=sum(counts['topic'][c] for c in children if parents[c]==tid),
            enabled_children=sum(counts['topic'][c]>0 for c in children if parents[c]==tid),original_rows_label_changed=counts['old_changed'][tid],
            original_rows_parent_changed=counts['old_parent_changed'][tid],original_rows_needs_review=counts['old_review'][tid],
            original_rows_quality_quarantine=counts['old_quarantine'][tid],original_rows_to_children=counts['old_child'][tid],
            original_rows_accepted=counts['old_accepted'][tid],original_rows_still_at_parent=counts['old_retained'][tid],
            original_rows_text_cleaned=counts['old_cleaned'][tid],priority=r['status'] in {'宽泛待细分','混杂待重分'},
            local_child_rules=plan[tid]['local_child_rules'],candidate_rules=plan[tid]['local_or_cross_parent_candidate_rules'])
        parentrows.append(r)
    pd.DataFrame(parentrows).to_csv(BASE/'results/main_directory_486_refined.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame([r for r in parentrows if r['priority']]).to_csv(BASE/'results/priority_280_outcomes.csv',index=False,encoding='utf-8-sig')
    childrows=[]
    for tid,s in sorted(children.items()):
        req=TITLE_GUARDS.get(s['rule_id']);exc=EXCLUDE_GUARDS.get(s['rule_id'])
        childrows.append(dict(topic_id=tid,parent_id=parents[tid],parent_name=names[parents[tid]],name=names[tid],documents=counts['topic'][tid],
            enabled=counts['topic'][tid]>0,eligible_leaf_documents=counts['eligible_leaf'][tid],rule_id=s['rule_id'],definition=s['definition'],
            candidate_clusters1000='|'.join(f'T{x:04d}' for x in s['candidate_seed_clusters1000']),seed_status=s['seed_status'],
            object_pattern=s['object_pattern'],task_pattern=s['task_pattern'],exclude_title_pattern=s['exclude_title_pattern'],
            precision_required_title=req[0].pattern if req else '',precision_excluded_title=exc[0].pattern if exc else '',
            precision_note='；'.join(x[1] for x in [req,exc] if x),review_status='自动规则接受；抽样诊断；非专家全量验收'))
    pd.DataFrame(childrows).to_csv(BASE/'results/child_directory.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame([dict(old_parent_id=a,final_parent_id=b,final_topic_id=c,documents=v) for (a,b,c),v in sorted(flows.items())]).to_csv(BASE/'results/label_flows.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame([dict(reason=k,decisions=v) for k,v in reversions.most_common()]).to_csv(BASE/'results/guard_reversions_summary.csv',index=False,encoding='utf-8-sig')
    for k in ['status','quality','flags','source']:
        pd.DataFrame([dict(value=x,documents=v) for x,v in counts[k].most_common()]).to_csv(BASE/f'results/{k}_counts.csv',index=False,encoding='utf-8-sig')
    dump(BASE/'results/ASSIGNMENT_MANIFEST.json',dict(created_utc=now(),documents=n,parts=manifest,index='row_id',topic_dictionary='results/topic_dictionary.csv',input_manifest_sha256=sha(OLD/'data/INPUT_MANIFEST.json')))
    dump(BASE/'results/REVIEW_MANIFEST.json',dict(documents=totals['needs_review'],parts=review_manifest))
    dump(BASE/'results/SUMMARY.json',dict(created_utc=now(),totals=totals,counts=counts,accepted_rule_counts=rulecounts,
        parent_count=len(old),proposed_child_count=len(children),enabled_child_count=sum(counts['topic'][c]>0 for c in children),
        canonical_aliases=ALIASES,name_overrides=NAME_OVERRIDES,guard_reasons=reversions))
    finalrules=[]
    for s in spec:
        t=dict(s);t['initial_topic_id']=s['topic_id'];t['topic_id']=canonical_topic(s['topic_id']);t['parent_id']=parents[t['topic_id']]
        t['name']=names[t['topic_id']];t['is_child']=kind[t['topic_id']]=='child';t['accepted_documents']=rulecounts[s['rule_id']]
        if t['topic_id'] in children:t['definition']=children[t['topic_id']]['definition']
        finalrules.append(t)
    dump(BASE/'review/final_taxonomy_rules.json',dict(rules=finalrules,additional_guards='src/decision_guards.py',canonical_aliases=ALIASES))
    progress('finalization_complete',**dict(totals),enabled_children=sum(counts['topic'][c]>0 for c in children))

if __name__=='__main__':main()
