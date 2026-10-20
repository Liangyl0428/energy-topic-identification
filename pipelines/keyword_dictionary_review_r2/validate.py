from common import *
from curation import synonyms

def main():
    c=connect();checks={}
    c.read_parquet(str(WORK/'paper_assignments/*.parquet')).create_view('export_a')
    c.read_parquet(str(WORK/'paper_topic_relations/*.parquet')).create_view('export_e')
    checks['all_papers_present_once']=c.execute('SELECT count(*),count(DISTINCT row_id),count(DISTINCT doc_id),min(row_id),max(row_id) FROM export_a').fetchone()==(4831088,4831088,4831088,0,4831087)
    checks['all_48329_source_keyword_ids_accounted_for']=c.execute('SELECT count(*),count(DISTINCT keyword_id) FROM keyword_lookup').fetchone()==(48329,48329)
    checks['all_source_observations_preserved']=c.execute('SELECT count(*) FROM observations').fetchone()[0]==58998384
    checks['one_relation_per_document_topic']=c.execute('SELECT count(*) FROM (SELECT row_id,topic_code,count(*) n FROM export_e GROUP BY ALL HAVING n>1)').fetchone()[0]==0
    checks['no_membership_for_empty_or_nontrigger_keywords']=c.execute("SELECT count(*) FROM export_a WHERE (topic_count>0)!=(len(anchor_keyword_codes)>0) OR (classification_status='no_keywords' AND raw_keyword_count<>0)").fetchone()[0]==0
    checks['membership_lists_agree_with_edges']=c.execute('''SELECT count(*) FROM
        (SELECT row_id,unnest(topic_codes) topic_code FROM export_a) a FULL JOIN export_e e USING(row_id,topic_code)
        WHERE a.row_id IS NULL OR e.row_id IS NULL''').fetchone()[0]==0
    checks['all_topic_counts_and_lists_valid']=c.execute('SELECT count(*) FROM export_a WHERE topic_count<>len(topic_codes) OR topic_count<>len(list_distinct(topic_codes))').fetchone()[0]==0
    checks['every_relation_has_observed_keyword_evidence']=c.execute('''SELECT count(*) FROM
        (SELECT row_id,topic_code,unnest(matched_source_keyword_ids) source_keyword_id FROM export_e) e
        ANTI JOIN eligible_hits h USING(row_id,topic_code,source_keyword_id)''').fetchone()[0]==0
    checks['all_expected_matches_exported']=c.execute('''SELECT count(*) FROM
        (SELECT DISTINCT h.row_id,h.topic_code FROM eligible_hits h JOIN anchors a USING(row_id)) q
        FULL JOIN export_e e USING(row_id,topic_code) WHERE q.row_id IS NULL OR e.row_id IS NULL''').fetchone()[0]==0
    checks['conditional_hits_have_compatible_anchor']=c.execute("SELECT count(*) FROM eligible_hits h JOIN anchors a USING(row_id) WHERE h.decision='conditional' AND len(h.allowed_anchor_topics)>0 AND len(list_intersect(h.allowed_anchor_topics,a.anchor_topic_codes))=0").fetchone()[0]==0
    checks['conditional_relations_have_same_document_direct_anchor']=c.execute('SELECT count(*) FROM export_e WHERE NOT has_direct_hit AND len(anchor_keywords)=0').fetchone()[0]==0
    checks['export_doc_ids_match_source']=c.execute('SELECT count(*) FROM export_e e JOIN papers p USING(row_id) WHERE e.doc_id<>p.doc_id').fetchone()[0]==0
    expected=json.loads((WORK/'CLASSIFIED.json').read_text())['counts']
    checks['summary_counts_match_exports']=c.execute('SELECT count(*),sum(topic_count),count(*) FILTER(WHERE topic_count>0),count(*) FILTER(WHERE topic_count>1) FROM export_a').fetchone()==(expected['papers'],expected['relations'],expected['assigned_papers'],expected['multilabel_papers'])
    low=c.execute('''SELECT count(DISTINCT h.row_id),count(*) FROM candidate_hits h JOIN anchors USING(row_id)
        JOIN dictionary d USING(keyword_code) WHERE d.document_frequency<10''').fetchone()
    zero=c.execute('SELECT count(*) FROM candidate_hits JOIN anchors USING(row_id) WHERE source_keyword_score=0').fetchone()[0]
    d=pd.read_csv(WORK/'keyword_dictionary.csv').fillna('');ds=d.set_index('canonical_name').to_dict('index');syn=synonyms()
    def rule(words):
        rows=[ds.get(syn.get(normalize(x),normalize(x)),{}) for x in words]
        anchors={r['topic_code'] for r in rows if r.get('decision')=='direct'}
        return {r['topic_code'] for r in rows if r.get('decision')=='direct' or (anchors and r.get('decision')=='conditional' and (not r.get('conditional_anchor_topics') or bool(anchors & set(r['conditional_anchor_topics'].split(' | ')))))}
    behavior={
        'ambiguous_hydrogen_is_not_fuel':not rule(['Hydrogen']),
        'solar_wind_does_not_match_solar_energy':not rule(['Solar wind']),
        'medical_lithium_is_not_a_battery':not rule(['Lithium (medication)']),
        'generic_transition_is_not_energy_transition':not rule(['Transition (genetics)','Economy']),
        'method_only_does_not_create_energy_topic':not rule(['Machine learning','Graphene']),
        'energy_plus_method_yields_multiple_topics':len(rule(['Lithium-ion battery','Machine learning','Graphene']))==3,
        'synonyms_do_not_duplicate_themes':len(rule(['Hydropower','Hydroelectricity','HYDRO POWER']))==1,
        'hyphen_variants_are_normalized':rule(['Lithium–ion battery'])==rule(['Lithium-ion battery']) and bool(rule(['Lithium-ion battery'])),
        'all_matching_themes_no_top_n_cap':len(rule(['Wind power','Solar cell','Hydrogen storage','Tokamak','Natural gas','Flow battery','Supercapacitor','Microgrid','Smart grid','Economic dispatch','Heat pump','Petroleum','Electric vehicle']))==13,
        'hydrothermal_pv_does_not_create_geothermal': 'KWD-T0010' not in rule(['Solar cell','Hydrothermal circulation']),
        'coal_boiler_does_not_create_nuclear_topic': 'KWD-T0013' not in rule(['Coal','Nuclear engineering']),
        'pv_dielectric_does_not_create_insulation_topic': 'KWD-T0032' not in rule(['Solar cell','Dielectric']),
        'powerline_relay_does_not_create_protection_topic': 'KWD-T0031' not in rule(['Power-line communication','Relay']),
        'transmission_line_alone_is_ambiguous':not rule(['Transmission line']),
        'unknown_terms_abstain':not rule(['not-a-real-keyword-xyz']),
    }
    checks['behavioral_checks']=all(behavior.values())
    reference=ROOT/'final/assets/nmf500_multilabel_scope';old=json.loads((reference/'RELEASE.json').read_text())
    checks['old_nmf_deliverables_unchanged']=all(sha(reference/n)==h for n,h in old['files'].items())
    result={'passed':all(checks.values()),'checks':checks,'behavioral_checks':behavior,
        'low_frequency_trigger_documents':int(low[0]),'low_frequency_trigger_hits':int(low[1]),
        'zero_score_hits_retained_because_presence_is_rule':int(zero),
        'semantic_accuracy_validated':False,
        'scope':'Full-population integrity and rule correctness; not evidence that source keywords are semantically accurate.'}
    write(WORK/'VALIDATION.json',result);print(json.dumps(result,ensure_ascii=False,indent=2));assert result['passed']

if __name__=='__main__':main()
