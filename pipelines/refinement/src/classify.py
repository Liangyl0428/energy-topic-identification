"""Per-document refinement with explicit abstention; no original files are written."""
from refine_common import *
from taxonomy import RULES
from rule_engine import compiled,routing_view
from text_quality import process
from local_encoder import LocalEncoder
from threadpoolctl import threadpool_limits
from collections import Counter
import argparse,time

SPECIAL={'Q.UNUSABLE':'原始文本不可用','Q.INSUFFICIENT':'题名摘要不足，待补全','Q.EDITORIAL':'封面、索引、勘误等非研究正文','Q.TEMPLATE':'仍有模板干扰，待复核'}
THRESHOLDS={3:.60,2:.66,1:.72}

class Refiner:
    def __init__(self):
        threadpool_limits(1)
        self.old=pd.read_csv(OLD/'results/merged_topics.csv').fillna('').set_index('merged_topic_id')
        self.mapping=pd.read_csv(OLD/'results/raw_to_merged.csv').sort_values('cluster')
        self.oldparent_lut=self.mapping.merged_topic_id.to_numpy()
        self.oldstatus=self.old.status.to_dict()
        self.oldraw=np.load(OLD/'results/raw_labels.npy',mmap_mode='r')
        self.newraw=np.load(NEW/'results/raw_labels.npy',mmap_mode='r')
        self.secondary=np.load(NEW/'results/secondary_labels.npy',mmap_mode='r')
        self.centroids=np.load(NEW/'models/topic_centroids.npy').astype(np.float32)
        self.names=np.load(BASE/'models/rule_name_vectors.npy')
        self.retrieval=read(BASE/'models/rule_retrieval.json')
        self.spec=read(BASE/'review/taxonomy_rules.json')['rules'];self.rules=compiled()
        assert len(self.rules)==len(self.spec)
        self.seeds=[s['candidate_seed_clusters1000'] for s in self.spec]
        self.seedmat=[self.centroids[ids] for ids in self.seeds]
        self.topic_names={p:r['name'] for p,r in self.old.iterrows()}
        self.topic_parents={p:p for p in self.old.index}
        for s in self.spec:
            if s['is_child']:
                self.topic_names[s['topic_id']]=s['name'];self.topic_parents[s['topic_id']]=s['parent_id']
        self.topic_names.update(SPECIAL);self.topic_parents.update({k:'' for k in SPECIAL})
        self.priority=set(self.old[self.old.status.isin(['宽泛待细分','混杂待重分'])].index)
        self.encoder=None
        self.global_candidates=[i for i,s in enumerate(self.spec) if s['candidate_seed_clusters1000']]

    def encode_changed(self,rows,cleaned,vectors):
        ids=[i for i,q in enumerate(cleaned) if q['text_changed'] and q['quality'] in ['cleaned_title_only','cleaned_text']]
        if not ids:return ids
        if self.encoder is None:self.encoder=LocalEncoder()
        for start in range(0,len(ids),1024):
            batch=ids[start:start+1024]
            vectors[batch]=self.encoder.encode([dict(title=cleaned[i]['title'],body=cleaned[i]['body'],source=rows[i]['source']) for i in batch])
        return ids

    def one(self,row,q,vector,clean_nearest=None):
        rid=row['row_id'];old_raw=int(self.oldraw[rid]);new_raw=int(self.newraw[rid]);sec=int(self.secondary[rid])
        old_parent=self.oldparent_lut[old_raw] if old_raw>=0 else ''
        base=dict(row_id=rid,doc_id=row['doc_id'],source=row['source'],date=row['date'],title=q['title'],
            old_cluster500=old_raw,old_parent_id=old_parent,old_parent_name=self.topic_names.get(old_parent,''),
            raw_cluster1000=new_raw,quality_status=q['quality'],quality_flags='|'.join(q['flags']),
            text_cleaned=q['text_changed'],retracted=bool(row['retracted']),
            final_parent_id=old_parent,final_topic_id=old_parent,final_topic_label=self.topic_names.get(old_parent,''),
            assignment_status='parent_retained_needs_review' if old_parent in self.priority else 'parent_retained',
            rule_id='',text_evidence_level=0,semantic_support_cosine=None,semantic_support_cluster1000=None,
            candidate_topic_ids='',routing_body_characters=0,parent_changed=False,topic_changed=False,
            needs_review=old_parent in self.priority,eligible_for_topic_counts=bool(old_parent) and not row['retracted'],
            clean_text_nearest1000=clean_nearest)
        quality_map={'unusable_original':'Q.UNUSABLE','insufficient_metadata':'Q.INSUFFICIENT','nonresearch_editorial':'Q.EDITORIAL','unresolved_template':'Q.TEMPLATE'}
        if q['quality'] in quality_map:
            tid=quality_map[q['quality']]
            base.update(final_parent_id='',final_topic_id=tid,final_topic_label=SPECIAL[tid],assignment_status='quality_quarantine',
                needs_review=tid in ['Q.INSUFFICIENT','Q.TEMPLATE'],eligible_for_topic_counts=False,
                parent_changed=bool(old_parent),topic_changed=True)
            return base
        text,used=routing_view(q['title'],q['body'],row['source']);base['routing_body_characters']=used
        candidates=set(self.retrieval['by_parent'].get(old_parent,[]))
        for c in [new_raw,sec,clean_nearest]:
            if c is not None and c>=0:candidates.update(self.retrieval['by_raw1000'][c])
        # A template-cleaned title must be allowed to escape its original template cluster.
        if q['text_changed']:
            candidates.update(self.global_candidates)
        matches={};all_hits=[]
        for i in candidates:
            if not self.seeds[i]:continue
            s=self.spec[i];mode=self.rules[i].match(q['title'],text)
            if not mode:continue
            simvals=self.seedmat[i]@vector;best=int(np.argmax(simvals));sim=float(simvals[best])
            if sim<THRESHOLDS[mode]:continue
            # Body-only matches may reflect background rather than the paper's purpose.
            if mode==1:continue
            target=s['topic_id']
            value=(mode,sim,i,self.seeds[i][best])
            if target not in matches or value[:2]>matches[target][:2]:matches[target]=value
        if not matches:
            if q['text_changed'] or self.oldstatus.get(old_parent)=='外围或非研究文本':
                base.update(assignment_status='cleaned_pending_reclassification' if q['text_changed'] else 'peripheral_parent_retained',needs_review=True,eligible_for_topic_counts=False)
            return base
        maxmode=max(m[0] for m in matches.values())
        best={tid:m for tid,m in matches.items() if m[0]==maxmode}
        # A specific child supersedes a same-parent fallback, not another independent task.
        for tid in list(best):
            if tid in self.old.index and any(x!=tid and self.topic_parents[x]==tid for x in best):best.pop(tid,None)
        # Canonical reaction rules already collapse material specializations to one target.
        if len(best)>1:
            base.update(assignment_status='multiple_tasks_pending',needs_review=True,
                candidate_topic_ids='|'.join(sorted(best)),text_evidence_level=maxmode)
            if q['text_changed']:base['eligible_for_topic_counts']=False
            return base
        tid=next(iter(best));mode,sim,ri,seed=best[tid];parent=self.topic_parents[tid]
        parent_changed=old_parent!=parent
        if mode<3:
            base.update(assignment_status='abstract_task_pending',needs_review=True,candidate_topic_ids=tid,
                semantic_support_cosine=sim,text_evidence_level=mode,rule_id=self.spec[ri]['rule_id'])
            if q['text_changed']:base['eligible_for_topic_counts']=False
            return base
        if parent_changed and tid==parent and old_parent and self.oldstatus.get(old_parent) not in ['宽泛待细分','混杂待重分','外围或非研究文本']:
            base.update(assignment_status='broader_parent_suggestion_only',needs_review=True,candidate_topic_ids=tid,
                semantic_support_cosine=sim,text_evidence_level=mode,rule_id=self.spec[ri]['rule_id'])
            return base
        # Cross-parent movement requires an explicit object AND task in the title, or
        # a cleaned template title plus two independent model similarities.
        if parent_changed and mode<3:
            base.update(assignment_status='cross_parent_body_evidence_pending',needs_review=True,candidate_topic_ids=tid,
                semantic_support_cosine=sim,text_evidence_level=mode,rule_id=self.spec[ri]['rule_id'])
            return base
        # Avoid preserving known peripheral buckets as accepted technical labels.
        if parent_changed and sim<.64:
            base.update(assignment_status='cross_parent_margin_pending',needs_review=True,candidate_topic_ids=tid,
                semantic_support_cosine=sim,text_evidence_level=mode,rule_id=self.spec[ri]['rule_id'])
            return base
        base.update(final_parent_id=parent,final_topic_id=tid,final_topic_label=self.topic_names[tid],
            assignment_status='reclassified_after_cleaning' if q['text_changed'] else 'cross_parent_reclassified' if parent_changed else 'refined_child' if tid!=parent else 'parent_supported',
            rule_id=self.spec[ri]['rule_id'],text_evidence_level=mode,semantic_support_cosine=sim,semantic_support_cluster1000=seed,
            parent_changed=parent_changed,topic_changed=tid!=old_parent,needs_review=False,
            eligible_for_topic_counts=not row['retracted'])
        return base

    def part(self,p,save=True):
        start=time.time();rows=pq.read_table(OLD/p['file']).to_pylist()
        vectors=np.load(OLD/'models/embeddings'/f'{Path(p["file"]).stem}.npy').astype(np.float32)
        vectors/=np.maximum(np.linalg.norm(vectors,axis=1,keepdims=True),1e-12)
        cleaned=[process(r['title'],r['body'],r['usable']) for r in rows]
        changed=self.encode_changed(rows,cleaned,vectors)
        nearest={}
        if changed:
            scores=vectors[changed]@self.centroids.T
            nearest={i:int(j) for i,j in zip(changed,np.argmax(scores,axis=1))}
        labels=[self.one(r,q,v,nearest.get(i)) for i,(r,q,v) in enumerate(zip(rows,cleaned,vectors))]
        if save:
            out=BASE/'results/assignments'/Path(p['file']).name
            # Stable schema even when a shard has no successful refinements.
            schema=assignment_schema()
            table=pa.Table.from_pylist(labels,schema=schema)
            pq.write_table(table,out,compression='zstd')
            corrections=[]
            for i,(r,q) in enumerate(zip(rows,cleaned)):
                if q['text_changed']:
                    corrections.append(dict(row_id=r['row_id'],doc_id=r['doc_id'],clean_title=q['title'],clean_body=q['body'],
                        flags='|'.join(q['flags']),original_title_sha256=hashlib.sha256((r['title'] or '').encode()).hexdigest(),
                        original_body_sha256=hashlib.sha256((r['body'] or '').encode()).hexdigest(),
                        clean_body_sha256=hashlib.sha256(q['body'].encode()).hexdigest()))
            if corrections:pq.write_table(pa.Table.from_pylist(corrections),BASE/'results/text_corrections'/Path(p['file']).name,compression='zstd')
            if changed:
                np.savez_compressed(BASE/'models'/f'cleaned_{Path(p["file"]).stem}.npz',row_ids=np.array([rows[i]['row_id'] for i in changed]),embeddings=vectors[changed].astype(np.float16))
        return labels,dict(part=Path(p['file']).stem,documents=len(labels),seconds=time.time()-start,
            changed_labels=sum(r['topic_changed'] for r in labels),changed_parents=sum(r['parent_changed'] for r in labels),
            text_cleaned=sum(r['text_cleaned'] for r in labels),status_counts=dict(Counter(r['assignment_status'] for r in labels)))

def assignment_schema():
    ints=['row_id','old_cluster500','raw_cluster1000','text_evidence_level','semantic_support_cluster1000','routing_body_characters','clean_text_nearest1000']
    bools=['text_cleaned','retracted','parent_changed','topic_changed','needs_review','eligible_for_topic_counts']
    strings=['doc_id','source','date','title','old_parent_id','old_parent_name','quality_status','quality_flags','final_parent_id','final_topic_id','final_topic_label','assignment_status','rule_id','candidate_topic_ids']
    return pa.schema([(x,pa.int64()) for x in ints]+[(x,pa.bool_()) for x in bools]+[(x,pa.string()) for x in strings]+[('semantic_support_cosine',pa.float32())])

def main():
    p=argparse.ArgumentParser();p.add_argument('--start',type=int,default=0);p.add_argument('--stop',type=int,default=259);p.add_argument('--resume',action='store_true')
    args=p.parse_args();engine=Refiner();parts=read(OLD/'data/INPUT_MANIFEST.json')['parts'];counts=Counter()
    for i in range(args.start,min(args.stop,len(parts))):
        meta=BASE/'logs'/f'part-{i:05d}.json'
        if args.resume and meta.exists() and (BASE/'results/assignments'/f'part-{i:05d}.parquet').exists():continue
        _,result=engine.part(parts[i]);dump(meta,result)
        counts.update(result['status_counts'])
        state=dict(stage='per_document_refinement',updated_utc=now(),completed_part=i+1,total_parts=len(parts),last_part=result,status_counts_this_run=dict(counts))
        dump(BASE/'logs'/f'worker_{args.start}_{args.stop}_progress.json',state)
        print(json.dumps(state,ensure_ascii=False),flush=True)
    print('CLASSIFICATION_RANGE_COMPLETE',args.start,args.stop,flush=True)

if __name__=='__main__':main()
