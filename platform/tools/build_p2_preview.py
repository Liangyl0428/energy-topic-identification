"""Build a self-contained offline review surface from the actual P2 exports."""
import json
from pathlib import Path
FINAL=Path(__file__).resolve().parents[1]
data=json.loads((FINAL/'assets/p2/platform_data.json').read_text())
def select(rows,keys):return [{k:r[k] for k in keys} for r in rows]
topics=select(data['topics'],['business_topic_id','category','category_name','name','research_object','definition','signal','decision_question','recent_papers','previous_papers','share_growth_ratio','recent_share','recent_institutions','previous_institutions','quarter_counts','decision_interpretation','recommended_actions','potential_assessment','bottleneck_to_check','limitations'])
cases=select(data['cases'],['case_id','canonical_name','business_links','trl_display','crl_display','trl_public_evidence_stage','crl_public_evidence_stage','trl_stage_name','crl_stage_name','decision_stage','object_configuration','application_or_target_function','evidence_period','boundary','decision_brief','specific_questions','application_checks','trl_next_actions','crl_next_actions','evidence_links'])
legacy=select(data['legacy_topics'],['category_id','name','paper_documents','matched_unique_papers','unresolved_papers','business_composition','interpretation'])
evidence=[]
for t in topics:
 own=[r for r in data['evidence_samples'] if r['business_topic_id']==t['business_topic_id'] and r['sample_stratum']=='recent']
 evidence.extend(select(own,['business_topic_id','doc_id','title','date','source','matched_quotes','body_excerpt','url']))
compact={'summary':{k:data['summary'][k] for k in ['business_topics','population_records','object_cards']},'categories':data['categories'],'topics':topics,'cases':cases,'legacy':legacy,'evidence':evidence}
payload=json.dumps(compact,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
fragment=(FINAL/'tools/p2_preview.html').read_text().replace('__ENERGY_P2_DATA__',payload)
out=FINAL/'preview';out.mkdir(exist_ok=True)
(out/'index.html').write_text('<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>能源业务与决策解读</title><style>body{margin:0;padding:20px;background:#f4f7f8;max-width:1320px;margin:auto}@media(max-width:720px){body{padding:0}}</style></head><body>\n'+fragment+'\n</body></html>\n')
print('Offline preview:',out/'index.html','bytes',len(fragment.encode()))
