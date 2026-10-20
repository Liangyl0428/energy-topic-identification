from common import *
from refine_rules import *

# Only unequivocal non-energy senses are screened out by these disclosed rules.
# Absence of a match is NOT proof of irrelevance; the long tail remains unreviewed.
OUTSIDE_PATTERNS={
 'medical_disease':r'\b(?:cancer|carcinoma|tumou?r|lymphoma|leukemia|diabetes|diabetic|dementia|alzheimer|parkinson|schizophrenia|arthritis|hepatitis|asthma|myocardial|cardiac|coronary|renal|kidney|pulmonary|pulseless|epilepsy|epileptic|hypertension|fibrosis|sepsis|pneumonia|osteoporosis|glaucoma|retinopathy|encephalitis)\b',
 'medical_care':r'\b(?:patient|patients|clinical|surgical|surgery|surgeon|pharmacology|pharmacokinetic|chemotherapy|radiotherapy|anesthesia|anaesthesia|nursing|rehabilitation|vaccine|vaccination|antibiotic|antibody|antibodies|immunotherapy|biomarker|diagnosis|prognosis)\b',
 'cellular_biology':r'\b(?:gene|genes|genome|genomic|rna|dna|protein|proteins|enzyme|enzymes|receptor|receptors|neuron|neuronal|neurons|mitochondrial|chromosome|chromosomal|ribosomal|apoptosis|transcription|cytokine|cytokines|lymphocyte|lymphocytes)\b',
 'non_energy_power_sense':r'\b(?:purchasing power|power of attorney|power politics|power walking|sums of powers|prime power|perfect power|power of two|power structure|power transform|convolution power|formal power series|absolute power|symbolic power|will to power|manpower|empowerment)\b',
 'non_energy_solar_sense':r'\b(?:solar neutrino|solar mass|solar core|stellar wind|carbon star|solar system|solarisation)\b',
}

def main():
    c=connect();v=pd.read_csv(WORK/'all_raw_keywords.csv')
    syn=synonyms();v['canonical_name']=v.normalized_name.map(lambda s:syn.get(s,s))
    keys=sorted(v.canonical_name.unique());ids={s:f'KW{i+1:05d}' for i,s in enumerate(keys)}
    v['keyword_code']=v.canonical_name.map(ids)
    mapping={};missing=[]
    for t in TOPICS:
        for mode in ['direct','conditional']:
            for term in t[mode]:
                n=syn.get(normalize(term),normalize(term))
                old=mapping.get(n)
                assert old is None or old[:2]==(t['topic_code'],mode),(term,old,t)
                mapping[n]=(t['topic_code'],mode,term)
                if n not in ids:missing.append({'term':term,'topic_code':t['topic_code'],'mode':mode,'status':'not_observed_not_active'})
    broad={normalize(s) for s in BROAD_TERMS};outside={normalize(s) for s in OUTSIDE_TERMS};aux={normalize(s) for s in AUXILIARY_TERMS}
    rows=[]
    for n in keys:
        if n in mapping:
            tc,mode,label=mapping[n]
            state='direct' if mode=='direct' else 'conditional'
            basis='assistant_explicit_term_review';reason='明确能源对象或能源技术词，单独命中即可触发。' if mode=='direct' else '条件词：须与规定相关方向的直接词共现；通用支撑主题接受任一能源直接词，详见conditional_anchor_topics。'
            rule='explicit_topic_term'
        elif n in outside:
            tc='';state='excluded';basis='assistant_explicit_term_review';reason='已审词义为范围外或误导词义；不作为主题触发词，不删除含该词的论文。';rule='explicit_non_energy_sense'
        elif n in broad:
            tc='';state='broad_auxiliary';basis='assistant_explicit_term_review';reason='学科大类或宽泛领域；保留原词，不独立触发能源主题。';rule='explicit_broad_term'
        elif n in aux:
            tc='';state='general_auxiliary';basis='assistant_explicit_term_review';reason='通用物理、材料、方法、对象或多义词；未指定独立主题触发关系。';rule='explicit_generic_term'
        else:
            hit=next((r for r,p in OUTSIDE_PATTERNS.items() if re.search(p,n)),None)
            if hit:
                tc='';state='excluded_rule';basis='disclosed_rule_screen_not_individually_reviewed';reason='公开规则识别到医学、生物或其他非能源词义；仅从触发词表排除，保留待复核。';rule=hit
            else:
                tc='';state='unreviewed';basis='not_individually_reviewed';reason='尚未确认能独立识别能源主题；保持待审，不声称与能源无关。';rule='conservative_unmapped'
        rows.append({'keyword_code':ids[n],'canonical_name':n,'decision':state,'topic_code':tc,'review_basis':basis,'decision_reason':reason,'decision_rule':rule})
    d=pd.DataFrame(rows)
    d['conditional_anchor_topics']=d.apply(lambda r:' | '.join(conditional_anchors(r.topic_code)) if r.decision=='conditional' else '',axis=1)
    c.register('vocab_input',v)
    c.execute('CREATE OR REPLACE TABLE keyword_lookup AS SELECT * FROM vocab_input')
    freq=c.execute('''SELECT keyword_code,count(DISTINCT row_id) document_frequency FROM observations
        JOIN keyword_lookup USING(keyword_id) GROUP BY keyword_code''').df()
    aliases=v.groupby('keyword_code').agg(display_name=('raw_name','first'),source_keyword_ids=('keyword_id',lambda x:' | '.join(x)),raw_names=('raw_name',lambda x:' | '.join(x)),source_identity_count=('keyword_id','size')).reset_index()
    d=d.merge(freq,on='keyword_code',validate='one_to_one').merge(aliases,on='keyword_code',validate='one_to_one')
    d.to_csv(WORK/'keyword_dictionary.csv',index=False,encoding='utf-8-sig')
    v.to_csv(WORK/'keyword_aliases.csv',index=False,encoding='utf-8-sig')
    c.register('dict_input',d);c.execute('CREATE OR REPLACE TABLE dictionary AS SELECT * FROM dict_input')
    records=[]
    for t in TOPICS:
        own=d[d.topic_code==t['topic_code']]
        assert len(own)>0,t
        records.append({'topic_code':t['topic_code'],'name':t['name'],'definition':t['definition'],
            'direct_keywords':own[own.decision=='direct'].display_name.tolist(),
            'conditional_keywords':own[own.decision=='conditional'].display_name.tolist(),
            'conditional_anchor_topics':conditional_anchors(t['topic_code']),
            'conditional_anchor_rule':'any_explicit_energy_anchor' if not conditional_anchors(t['topic_code']) else 'only_listed_related_direct_topics',
            'direct_keyword_count':int(own.decision.eq('direct').sum()),
            'conditional_keyword_count':int(own.decision.eq('conditional').sum()),
            'topic_kind':'supporting_method_material' if 65<=int(t['topic_code'].split('T')[-1])<=70 else ('cross_cutting_energy' if 57<=int(t['topic_code'].split('T')[-1])<=63 else 'energy_technology_object'),
            'authority':'assistant_curated_from_observed_keywords_not_expert_approved'})
    write(WORK/'topic_definitions.json',records)
    flat=pd.DataFrame(records)
    for col in ['direct_keywords','conditional_keywords','conditional_anchor_topics']:flat[col]=flat[col].map(lambda s:' | '.join(s))
    flat.to_csv(WORK/'topic_catalog.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(missing).to_csv(WORK/'unobserved_candidate_terms.csv',index=False)
    summary={'topics':len(records),'raw_keyword_ids':len(v),'canonical_keywords':len(d),
        'decisions':d.decision.value_counts().to_dict(),
        'keyword_document_occurrences_by_decision':d.groupby('decision').document_frequency.sum().astype(int).to_dict(),
        'normalization':'Unicode NFKC, casefold, hyphen variants to spaces, collapse whitespace; retain sense qualifiers.',
        'synonym_groups':SYNONYM_GROUPS,'unobserved_candidate_terms_inactive':len(missing),
        'dictionary_sha256':sha(WORK/'keyword_dictionary.csv'),'aliases_sha256':sha(WORK/'keyword_aliases.csv'),
        'topic_definitions_sha256':sha(WORK/'topic_definitions.json'),
        'outside_screening_patterns':OUTSIDE_PATTERNS,
        'boundary':'All original keyword identities accounted for. Explicit trigger terms are assistant-reviewed; rule-excluded terms and the unreviewed long tail are not claimed to be individually manually reviewed. No unsupported automatic deletion.'}
    write(WORK/'DICTIONARY_COMPLETE.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
