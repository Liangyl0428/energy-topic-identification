"""Full-population consistency validation for the new release."""
from run import *
import duckdb


def main():
    import subprocess
    complete=base.read(OUT/'SCOPE_APPLIED.json')
    assert complete['scope_ledger_sha256']==sha(OUT/'review/topic_scope_decisions.csv')
    assert complete['relation_review_overrides_sha256']==sha(OUT/'review/relation_review_overrides.csv')
    c=duckdb.connect();c.execute('SET threads=4');c.execute("SET memory_limit='4GB'")
    temp=OUT/'validation_tmp';temp.mkdir(exist_ok=True);c.execute('SET temp_directory=?',[str(temp)])
    c.read_parquet(str(OUT/'business_assignments/*.parquet'),union_by_name=True).create_view('a')
    c.read_parquet(str(OUT/'business_edges_ge_005/*.parquet'),union_by_name=True).create_view('e')
    checks={}
    identity=c.execute('SELECT count(*),count(DISTINCT row_id),count(DISTINCT doc_id),min(row_id),max(row_id) FROM a').fetchone()
    checks['all_record_identities_unique_and_complete']=identity==(5119004,5119004,5119004,0,5119003)
    counts=dict(c.execute('SELECT source,count(*) FROM a GROUP BY source').fetchall())
    checks['all_three_source_populations_complete']=counts=={'paper':4831088,'patent':281295,'policy':6621}
    bad=c.execute('''SELECT count(*) FROM a WHERE topic_count!=len(topic_ids) OR topic_count!=len(topic_contributions)
        OR list_min(topic_contributions)<0.10 OR retained_contribution>1.00001
        OR abs(retained_contribution-coalesce(list_sum(topic_contributions),0))>1e-6
        OR (NOT quality_gate_pass AND topic_count>0)''').fetchone()[0]
    checks['all_membership_lists_weights_and_abstentions_valid']=bad==0
    checks['excluded_pending_and_rejected_edges_absent_from_default']=c.execute('''SELECT count(*) FROM e WHERE business_included_at_010
        AND (scope_state NOT IN ('keep_core','keep_supporting') OR NOT quality_gate_pass OR relation_review_rejected OR relative_contribution<0.10)''').fetchone()[0]==0
    checks['all_five_known_bad_relations_rejected']=c.execute('SELECT count(*) FROM e WHERE relation_review_rejected').fetchone()[0]==5
    list_edges=c.execute('SELECT sum(topic_count) FROM a').fetchone()[0]
    edge_rows=c.execute('SELECT count(*) FROM e WHERE business_included_at_010').fetchone()[0]
    checks['assignment_lists_and_edge_counts_agree']=list_edges==edge_rows
    c.execute('''CREATE VIEW lists AS SELECT row_id,unnest(topic_ids) topic_id,unnest(topic_contributions) contribution FROM a''')
    mismatch=c.execute('''SELECT count(*) FROM lists l FULL OUTER JOIN (SELECT row_id,topic_id,relative_contribution FROM e WHERE business_included_at_010) q
        ON l.row_id=q.row_id AND l.topic_id=q.topic_id WHERE l.row_id IS NULL OR q.row_id IS NULL OR abs(l.contribution-q.relative_contribution)>1e-7''').fetchone()[0]
    checks['every_exported_membership_matches_exact_edge']=mismatch==0
    c.read_parquet([str(OUT/'full_model/contribution_edges_ge_005/*.parquet'),str(OUT/'transfer/contribution_edges_ge_005/*.parquet')],union_by_name=True).project('row_id,topic_id,relative_contribution').create_view('original_edges')
    raw_mismatch=c.execute('''SELECT count(*) FROM original_edges r FULL OUTER JOIN e USING(row_id,topic_id)
        WHERE r.row_id IS NULL OR e.row_id IS NULL OR r.relative_contribution IS DISTINCT FROM e.relative_contribution''').fetchone()[0]
    checks['all_original_edge_scores_preserved_without_renormalization']=raw_mismatch==0
    aggregated=c.execute('''SELECT source,count(*) records,sum(CASE WHEN topic_count>0 THEN 1 ELSE 0 END) assigned_documents,
        sum(CASE WHEN topic_count>1 THEN 1 ELSE 0 END) multiple_topic_documents,sum(topic_count) edges,
        sum(retained_contribution) contribution_mass FROM a GROUP BY source ORDER BY source''').df()
    expected=pd.read_csv(OUT/'threshold_scope_sensitivity.csv').query('threshold==.10 and stage=="retained"').sort_values('source')
    checks['published_counts_match_full_assignments']=all(np.allclose(aggregated[col],expected[col]) for col in ['records','assigned_documents','multiple_topic_documents','edges','contribution_mass'])
    status=c.execute('SELECT source,business_status,count(*) records FROM a GROUP BY ALL ORDER BY source,records DESC').df()
    status.to_csv(OUT/'assignment_status_counts.csv',index=False)
    h=np.load(OUT/'full_model/components.npy');mask=np.load(OUT/'broad_mask.npy')
    checks['exactly_500_nonnegative_topics_and_20_removed_terms']=h.shape[0]==500 and int(mask.sum())==20 and bool((h>=0).all()) and bool((h[:,mask]==0).all())
    checks['all_topics_have_scope_decisions']=len(pd.read_csv(OUT/'topic_catalog_reviewed.csv'))==500
    checks['paper_reference_and_diagnostic_ids_disjoint']=len(np.intersect1d(np.load(base.OLD/'train_row_ids.npy'),np.load(base.OLD/'test_row_ids.npy')))==0
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'final/energy-topic-identification/tests'),'-p','test_multilabel_scope.py','-v'],capture_output=True,text=True)
    (OUT/'unit_checks.log').write_text(result.stdout+result.stderr)
    checks['behavioral_unit_checks_pass']=result.returncode==0
    write(OUT/'VALIDATION.json',{'passed':all(checks.values()),'checks':checks,'identity':list(identity),
        'default_retained_edges':int(edge_rows),'raw_edge_score_mismatches':int(raw_mismatch),
        'scope_ledger_sha256':complete['scope_ledger_sha256'],'semantic_accuracy_validated':False})
    print(json.dumps(checks,indent=2));print(aggregated.to_string(index=False))
    assert all(checks.values()),checks


if __name__=='__main__':main()
