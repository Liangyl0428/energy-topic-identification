"""Read-only input preflight and provenance inventory for the frozen delivery."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import sys

FINAL=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(FINAL))
from runtime_config import load_runtime


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()


def inspect(config=None):
    rt=load_runtime(config);checks=[];files=[]
    def check(name,ok,detail=None):checks.append({'name':name,'passed':bool(ok),'detail':detail})
    def record(path,role):
        path=Path(path)
        check(role+'_exists',path.is_file(),str(path))
        if path.is_file():files.append({'role':role,'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path)})
    required={'raw_data_dir':'dir','corpus_dir':'dir','metadata_db':'file','keyword_sources':'file','classification_run':'dir','context_dir':'dir','bge_model_dir':'dir','bge_runtime_dir':'dir','bge_core_dir':'dir'}
    for key,kind in required.items():
        p=rt.path(key);check('path_'+key,p.is_file() if kind=='file' else p.is_dir(),str(p))
    record(rt.config_path,'runtime_config')
    cp=rt.path('classification_run');cm=rt.path('corpus_dir').parent/'INPUT_MANIFEST.json'
    for name in ['SUMMARY.json','COMPLETE.json','VALIDATION.json','ASSIGNMENTS_MANIFEST.json','topic_catalog.csv']:
        record(cp/name,'classification_'+name)
    record(cm,'corpus_manifest');record(rt.path('keyword_sources'),'keyword_source_inventory')
    for name in ['contexts.json','ENCODING.json','embeddings.npy']:record(rt.path('context_dir')/name,'maturity_context_'+name)
    corpus=json.loads(cm.read_text()) if cm.is_file() else {}
    classification=json.loads((cp/'SUMMARY.json').read_text()) if (cp/'SUMMARY.json').is_file() else {}
    if corpus:
        expected={Path(p['file']).name for p in corpus['parts']}
        actual={p.name for p in rt.path('corpus_dir').glob('part-*.parquet')}
        check('corpus_part_inventory',actual==expected,{'expected_parts':len(expected),'found_parts':len(actual)})
        check('corpus_population',sum(p['n'] for p in corpus['parts'])==classification.get('population_records'),classification.get('population_records'))
    if (cp/'COMPLETE.json').is_file():
        complete=json.loads((cp/'COMPLETE.json').read_text())
        for name,key in [('SUMMARY.json','summary_sha256'),('VALIDATION.json','validation_sha256')]:
            check('classification_bound_'+name,sha(cp/name)==complete[key])
        check('classification_passed',json.loads((cp/'VALIDATION.json').read_text()).get('passed'))
        check('assignment_manifest_bound',sha(cp/'ASSIGNMENTS_MANIFEST.json')==classification['assignments_manifest_sha256'])
    if rt.path('keyword_sources').is_file():
        inventory=json.loads(rt.path('keyword_sources').read_text())
        missing=[str(rt.source_path(x['path'])) for x in inventory if not rt.source_path(x['path']).is_file()]
        check('keyword_source_files',not missing,{'records':len(inventory),'missing_count':len(missing),'missing_examples':missing[:5]})
    metadata_columns=[]
    if rt.path('metadata_db').is_file():
        import duckdb
        conn=duckdb.connect(str(rt.path('metadata_db')),read_only=True)
        metadata_columns=conn.sql("PRAGMA table_info('works')").df()['name'].tolist();conn.close()
        check('metadata_schema',{'work_id','institutions','cited_by_count'}<=set(metadata_columns))
    bound_hash=sha(cp/'SUMMARY.json') if (cp/'SUMMARY.json').is_file() else None
    for module in ['energy-topic-identification','energy-topic-hotspots','energy-technology-trl-crl']:
        base=FINAL/module/'assets/full_nmf500'
        record(base/'SUMMARY.json',module+'_delivered_summary')
        if module!='energy-topic-identification':
            s=json.loads((base/'SUMMARY.json').read_text());check(module+'_classification_binding',s['classification_summary_sha256']==bound_hash)
    check('delivered_classification_matches_run',sha(FINAL/'energy-topic-identification/assets/full_nmf500/SUMMARY.json')==bound_hash)
    hot=json.loads((FINAL/'energy-topic-hotspots/assets/full_nmf500/SUMMARY.json').read_text())
    dataset=json.loads((FINAL/'energy-technology-trl-crl/data/dataset.json').read_text())
    windows=rt.config['windows']
    check('hotspots_cutoff',windows['hotspots_history'][1]==hot['cutoff']=='2026-06-30')
    check('hotspots_windows',windows['hotspots_history']==['2021-07-01','2026-06-30'] and windows['hotspots_core']==['2023-07-01','2026-06-30'] and windows['hotspots_recent']==['2025-07-01','2026-06-30'] and windows['hotspots_baseline']==['2022-07-01','2025-06-30'] and windows['cross_source_comparison']==['2026-01-01','2026-06-30'])
    check('maturity_cutoff',windows['maturity_assessment_cutoff']==dataset['assessment_cutoff']=='2026-09-25')
    for p in sorted((FINAL/'energy-technology-trl-crl/data').glob('*.json')):record(p,'maturity_evidence_'+p.name)
    return {'created_utc':datetime.now(timezone.utc).isoformat(),'passed':all(c['passed'] for c in checks),'runtime':rt.snapshot(),'source_counts':corpus.get('source_counts'),'source_date_ranges':corpus.get('date_ranges'),'selection_rules':corpus.get('selection_rules'),'classification_population_records':classification.get('population_records'),'classification_assigned_records':classification.get('assigned_records'),'classification_unassigned_records':classification.get('unassigned_records'),'hotspots_papers_used':hot['papers_used_for_hotspot_windows'],'maturity_evidence_cutoff':dataset['assessment_cutoff'],'metadata_columns':metadata_columns,'files':files,'checks':checks,'verification_limit':'Compact input manifests and evidence were freshly hashed. Full corpus/assignment part content and the metadata database were not rehashed; their existing audit records are retained. File presence and metadata schema were checked read-only. Output directories need not exist before a run.'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path);ap.add_argument('--output',type=Path,default=FINAL/'provenance/INPUT_MANIFEST.json');a=ap.parse_args()
    try:
        report=inspect(a.config)
    except (ValueError,KeyError,FileNotFoundError) as exc:
        raise SystemExit('Input preflight failed: '+str(exc))
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'passed':report['passed'],'checks':len(report['checks']),'inventory':str(a.output)},ensure_ascii=False))
    for c in report['checks']:
        if not c['passed']:print(json.dumps(c,ensure_ascii=False))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
