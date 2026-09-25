from refine_common import *
from decision_guards import ACCEPTED,guard,quality_veto
from text_quality import process
from collections import Counter

def main():
    m=read(BASE/'results/ASSIGNMENT_MANIFEST.json');s=read(BASE/'results/SUMMARY.json');n=m['documents']
    catalog=pd.read_csv(BASE/'results/topic_dictionary.csv').fillna('')
    cat=catalog.set_index('topic_id').to_dict('index');parents=catalog[catalog.kind.eq('parent')]
    labels=np.load(BASE/'results/final_labels.npy',mmap_mode='r');plabels=np.load(BASE/'results/final_parent_labels.npy',mmap_mode='r')
    leaf=np.load(BASE/'results/analysis_leaf_labels.npy',mmap_mode='r');review=np.load(BASE/'results/needs_review.npy',mmap_mode='r')
    assert all(len(a)==n for a in [labels,plabels,leaf,review])
    assert np.array_equal(catalog.topic_index,np.arange(len(catalog)))
    assert len(parents)==486 and catalog.topic_id.is_unique
    assert all(c in set(parents.topic_id) for c in catalog.loc[catalog.kind.eq('child'),'parent_id'])
    child_names=catalog.loc[catalog.kind.eq('child'),'name']
    assert child_names.is_unique and not (set(child_names)&set(parents.name))
    old=pd.read_csv(OLD/'results/merged_topics.csv').fillna('')
    assert list(parents.topic_id)==list(old.merged_topic_id) and list(parents.name)==list(old.name)
    parts=read(OLD/'data/INPUT_MANIFEST.json')['parts'];raw=np.load(OLD/'results/raw_labels.npy',mmap_mode='r')
    raw1000=np.load(NEW/'results/raw_labels.npy',mmap_mode='r');tot=Counter();tc=Counter();statuses=Counter();qc=Counter()
    schemas=set();correction_checks=0;embedding_rows=0
    for i,(p,o) in enumerate(zip(parts,m['parts'])):
        f=BASE/o['file'];assert sha(f)==o['sha256'],f
        table=pq.read_table(f);df=table.to_pandas();a=p['first_row'];b=a+p['n']
        schemas.add(str(table.schema.remove_metadata()))
        assert np.array_equal(df.row_id,np.arange(a,b)),f
        assert len(df)==p['n']==o['n'] and a==o['first_row']
        orig=pq.read_table(OLD/p['file'],columns=['row_id','doc_id','source','date','retracted']).to_pandas()
        for col in ['row_id','doc_id','source','date','retracted']:
            assert orig[col].fillna('').tolist()==df[col].fillna('').tolist(),(f,col)
        assert np.array_equal(df.old_cluster500,raw[a:b]) and np.array_equal(df.raw_cluster1000,raw1000[a:b])
        assert np.array_equal(df.final_topic_index,labels[a:b]) and np.array_equal(df.final_parent_index,plabels[a:b])
        assert np.array_equal(np.where(df.eligible_for_leaf_analysis,df.final_topic_index,-1),leaf[a:b])
        assert np.array_equal(df.needs_review,review[a:b])
        for tid,g in df.groupby('final_topic_id'):
            d=cat[tid];assert g.final_topic_index.eq(d['topic_index']).all()
            assert g.final_topic_label.eq(d['name']).all() and g.final_parent_id.eq(d['parent_id']).all()
        accepted=df.assignment_status.isin(ACCEPTED)
        assert df.loc[accepted,'text_evidence_level'].eq(3).all()
        assert df.loc[accepted,'rule_id'].ne('').all() and df.loc[accepted,'semantic_support_cosine'].notna().all()
        assert not df.loc[accepted,'needs_review'].any()
        assert all(guard(r) is None for r in df.loc[accepted].to_dict('records'))
        assert all(quality_veto(r) is None for r in df.loc[accepted].to_dict('records'))
        assert df.loc[df.topic_changed&~df.final_topic_id.str.startswith('Q.'),'assignment_status'].isin(ACCEPTED).all()
        assert df.loc[df.needs_review,'review_reason'].ne('').all()
        assert not df.loc[df.eligible_for_leaf_analysis,'retracted'].any()
        assert df.loc[df.eligible_for_leaf_analysis,'final_topic_id'].map(lambda t:cat[t]['kind']=='child').all()
        pending=pq.read_table(BASE/'results/pending_review'/f.name).to_pandas()
        assert list(pending.row_id)==list(df.loc[df.needs_review,'row_id'])
        changes=pq.read_table(BASE/'results/label_changes'/f.name,columns=['row_id']).column(0).to_pylist()
        assert changes==df.loc[df.topic_changed,'row_id'].tolist()
        correction_file=BASE/'results/text_corrections'/f.name
        if correction_file.exists():
            cr=pq.read_table(correction_file).to_pylist()
            assert sorted(r['row_id'] for r in cr)==sorted(df.loc[df.text_cleaned,'row_id'])
            originals=pq.read_table(OLD/p['file'],columns=['row_id','title','body','usable'])
            source={r['row_id']:r for r in originals.take(pa.array([r['row_id']-a for r in cr])).to_pylist()}
            for c in cr:
                r=source[c['row_id']];q=process(r['title'],r['body'],r['usable'])
                assert hashlib.sha256((r['title'] or '').encode()).hexdigest()==c['original_title_sha256']
                assert hashlib.sha256((r['body'] or '').encode()).hexdigest()==c['original_body_sha256']
                assert q['title']==c['clean_title'] and q['body']==c['clean_body']
                assert hashlib.sha256(c['clean_body'].encode()).hexdigest()==c['clean_body_sha256']
                if q['quality']!='unresolved_template':
                    assert 'cheminform is a weekly abstracting service' not in q['body'].lower()
                    assert 'wydawnictwo sigma-not wydaje czasopisma fachowe' not in q['body'].lower()
                correction_checks+=1
        else:assert not df.text_cleaned.any()
        ef=BASE/'models'/f'cleaned_{f.stem}.npz'
        encoded=df.loc[df.text_cleaned&df.initial_quality_status.isin(['cleaned_title_only','cleaned_text']),'row_id'].tolist()
        if encoded:
            ev=np.load(ef);assert list(ev['row_ids'])==encoded and ev['embeddings'].shape==(len(encoded),384)
            norms=np.linalg.norm(ev['embeddings'].astype(np.float32),axis=1)
            assert np.isfinite(ev['embeddings']).all() and np.all(np.abs(norms-1)<.005)
            embedding_rows+=len(encoded)
        tot['documents']+=len(df);tot['needs_review']+=len(pending);tot['label_changes']+=len(changes)
        tot['leaf_analysis']+=int(df.eligible_for_leaf_analysis.sum());tot['retracted']+=int(df.retracted.sum())
        tc.update(df.final_topic_id.value_counts().to_dict());statuses.update(df.assignment_status.value_counts().to_dict());qc.update(df.quality_status.value_counts().to_dict())
        if i%25==0:print('validated_output_parts',i+1,len(parts),flush=True)
    assert len(schemas)==1,schemas
    assert tot['documents']==n==5119004
    assert tot['needs_review']==s['totals']['needs_review']==int(review.sum())
    assert tot['label_changes']==s['totals']['topic_changed']
    assert correction_checks==s['totals']['text_cleaned']
    assert dict(statuses)==s['counts']['status'] and dict(qc)==s['counts']['quality']
    assert sum(tc.values())==n
    for tid,c in cat.items():assert c['assigned_documents']==tc[tid]
    parent_catalog=pd.read_csv(BASE/'results/main_directory_486_refined.csv')
    qsum=sum(v for k,v in tc.items() if k.startswith('Q.'))
    assert int(parent_catalog.final_inclusive_documents.sum())+qsum==n
    assert int(parent_catalog.final_direct_parent_documents.sum())+int(parent_catalog.accepted_child_documents.sum())+qsum==n
    assert read(BASE/'review/INPUT_INTEGRITY.json')['passed']
    assert read(BASE/'review/REGRESSION_CHECKS.json')['passed']
    result=dict(created_utc=now(),passed=True,documents=n,parts=len(parts),parents=486,
        original_identifiers_sources_dates_retraction_flags_unchanged=True,row_ids_complete_unique_contiguous=True,
        original_500_and_1000_labels_preserved=True,original_486_names_and_ids_preserved=True,
        final_label_arrays_match_parquet=True,all_topic_and_parent_references_valid=True,one_parent_per_child=True,no_identical_parent_child_names=True,
        parent_child_quality_counts_conserved=True,one_stable_assignment_schema=True,
        accepted_decisions_pass_precision_guards=True,pending_review_and_change_tables_match=True,
        correction_records_verified=correction_checks,cleaned_embeddings_verified=embedding_rows,
        prior_input_hashes_verified=True,totals=tot,
        limitation='Integrity and decision-rule checks are not semantic accuracy estimates; automated labels remain subject to documented review limitations.')
    dump(BASE/'VALIDATION.json',result);print('OUTPUT_VALIDATION_PASSED',n,flush=True)

if __name__=='__main__':main()
