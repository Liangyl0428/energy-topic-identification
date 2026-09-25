from refine_common import *
from taxonomy import RULES
from rule_engine import compiled
from text_quality import process
from local_encoder import LocalEncoder
from threadpoolctl import threadpool_limits

def main():
    threadpool_limits(4)
    encoder=LocalEncoder()
    descriptors=encoder.encode([dict(title=r['name']) for r in RULES])
    np.save(BASE/'models/rule_name_vectors.npy',descriptors)
    centers=np.load(NEW/'models/topic_centroids.npy').astype(np.float32)
    similarity=descriptors@centers.T
    cards=read(MERGED/'review/topic_cards.json')
    docs=pq.read_table(NEW/'evidence/review_documents.parquet').to_pandas()
    records={i:[] for i in range(1000)}
    for row in docs.itertuples():
        if not any(role.startswith(('center:','random:')) for role in row.selection_roles.split('|')):continue
        q=process(row.title,row.body)
        if q['quality'] in ['insufficient_metadata','nonresearch_editorial','unresolved_template'] or q['text_changed']:continue
        records[row.cluster].append(dict(row_id=int(row.row_id),title=q['title'],text=q['title']+' . '+q['body'][:1000]))
    rules=compiled();spec=[];source_read=[]
    old=pd.read_csv(OLD/'results/merged_topics.csv')
    parent_set=set(old.merged_topic_id)
    by_raw=[set() for _ in range(1000)]
    by_parent={p:set() for p in parent_set}
    for ri,r in enumerate(rules):
        d=r.data.copy();seed_candidates=[];support=[]
        for c in range(1000):
            kw=cards[c]['keywords'];km=r.match(kw,kw)
            matching=[x for x in records[c] if r.match(x['title'],x['text'])>=2]
            if (matching and (km>=1 or similarity[ri,c]>=.30)) or (km==3 and similarity[ri,c]>=.30):
                seed_candidates.append(c)
                support.extend(dict(cluster=c,row_id=x['row_id'],title=x['title']) for x in matching)
        seed_candidates.sort(key=lambda c:similarity[ri,c],reverse=True)
        seeds=seed_candidates[:10]
        d['candidate_seed_clusters1000']=seeds
        d['seed_evidence']=[x for x in support if x['cluster'] in seeds][:30]
        d['seed_status']=('sample_object_task_supported' if d['seed_evidence'] else 'keyword_candidate_only') if seeds else 'no_seed_abstain'
        if d['is_child']:
            assert d['parent_id'] in parent_set
        spec.append(d)
        for c in seeds:by_raw[c].add(ri)
        by_parent[d['parent_id']].add(ri)
        original_parent=d['rule_id'].split('.')[0]
        if original_parent in by_parent:by_parent[original_parent].add(ri)
    # Retrieval may use a name-neighbor; it never grants a topic label by itself.
    for c in range(1000):
        for ri in np.argsort(similarity[:,c])[-8:]:
            if similarity[ri,c]>=.30 and spec[ri]['candidate_seed_clusters1000']:by_raw[c].add(int(ri))
    dump(BASE/'models/rule_retrieval.json',dict(by_raw1000=[sorted(s) for s in by_raw],by_parent={k:sorted(v) for k,v in by_parent.items()}))
    dump(BASE/'review/taxonomy_rules.json',dict(created_utc=now(),rules=spec,
        semantics='Operational object/task definitions. Cluster/example retrieval is machine-generated; it is not a claim that every proposed seed class was read or approved as a whole.'))
    pd.DataFrame([dict(rule_id=r['rule_id'],topic_id=r['topic_id'],parent_id=r['parent_id'],name=r['name'],is_child=r['is_child'],
        candidate_seed_clusters1000='|'.join(f'T{x:04d}' for x in r['candidate_seed_clusters1000']),
        seed_status=r['seed_status'],definition=r['definition'],object_pattern=r['object_pattern'],task_pattern=r['task_pattern'],
        exclude_title_pattern=r['exclude_title_pattern'],required_text_pattern=r.get('required_text_pattern','')) for r in spec]).to_csv(BASE/'results/taxonomy_rules.csv',index=False,encoding='utf-8-sig')
    priority=set(old.loc[old.status.isin(['宽泛待细分','混杂待重分']),'merged_topic_id'])
    coverage=[]
    packets=read(BASE/'review/parent_candidate_packets.json')
    for p in packets:
        options=set(by_parent[p['parent_id']])
        for c in p['candidates']:options.update(by_raw[int(c['raw1000'][1:])])
        coverage.append(dict(parent_id=p['parent_id'],name=p['name'],priority=p['priority'],documents=p['documents'],
            local_child_rules=sum(spec[i]['is_child'] and spec[i]['parent_id']==p['parent_id'] for i in options),
            local_or_cross_parent_candidate_rules=len(options),
            approach='逐条质量检查、对象/任务判别及向量佐证；符合者细分/重分，冲突和无充分证据者保留父类待复核' if p['priority'] else
                '逐条质量检查；可明确细分或恢复者处理，其他保留原目录'))
    pd.DataFrame(coverage).to_csv(BASE/'results/parent_processing_plan.csv',index=False,encoding='utf-8-sig')
    progress('retrieval_and_rule_taxonomy_ready',rules=len(spec),rules_with_sample_supported_seeds=sum(bool(r['candidate_seed_clusters1000']) for r in spec),
        priority_parents=len(priority),priority_with_local_children=sum(x['priority'] and x['local_child_rules']>0 for x in coverage),
        priority_with_candidates=sum(x['priority'] and x['local_or_cross_parent_candidate_rules']>0 for x in coverage))

if __name__=='__main__':main()
