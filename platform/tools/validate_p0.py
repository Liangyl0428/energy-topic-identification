"""End-to-end P0 acceptance against current evidence and the pre-edit Git state."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import numpy as np
import pandas as pd

FINAL=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(FINAL),str(FINAL/'energy-technology-trl-crl')]
from runtime_config import load_runtime
from trl_crl.delivery import refresh_export,typed_units
from trl_crl.pipeline import assess


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    rt=load_runtime();checks=[]
    def check(name,ok,detail=None):checks.append({'name':name,'passed':bool(ok),'detail':detail})
    repo=FINAL/'energy-technology-trl-crl';base=repo/'assets/full_nmf500'
    catalog=pd.read_csv(FINAL/'energy-topic-identification/assets/full_nmf500/topic_catalog.csv').set_index('category_id')
    d=pd.read_csv(base/'case_hotspot_links.csv',dtype={'trl_public_evidence_stage':'Int64','crl_public_evidence_stage':'Int64'})
    _,results=assess(repo/'data');expected=typed_units(results).set_index('case_id')
    check('122_unique_objects',len(d)==122 and d.case_id.is_unique and set(d.case_id)==set(expected.index))
    check('current_names_match',d.category_name.eq(d.category_id.map(catalog.name)).all())
    check('legacy_metadata_preserved',{'legacy_category_id','legacy_category_name','legacy_category_ids'}<=set(d.columns))
    check('current_category_ids',all(json.loads(row.category_ids)==[row.category_id] for row in d.itertuples()))
    for axis,maximum in [('trl',9),('crl',5)]:
        field=axis+'_public_evidence_stage'
        current=d.set_index('case_id')[field].sort_index();truth=expected[field].sort_index()
        check(axis+'_equals_engine',current.equals(truth))
        check(axis+'_valid_integer_range',current.dropna().between(1,maximum).all())
        check(axis+'_status_consistent',(d[axis+'_evidence_status'].eq('supported')==d[field].notna()).all())
        check(axis+'_unknown_explanation',d.loc[d[field].isna(),axis+'_missing_evidence'].fillna('').str.len().gt(0).all())
    check('known_unknown_counts',int(d.trl_public_evidence_stage.isna().sum())==14 and int(d.crl_public_evidence_stage.isna().sum())==99)
    paired=d.dropna(subset=['trl_public_evidence_stage','crl_public_evidence_stage'])
    check('13_plot_coordinates',len(paired)==13 and int(d.paired_axes_usable.sum())==13)
    records=json.loads((base/'case_hotspot_links.json').read_text())
    check('json_native_integer_null',all((r[k] is None or type(r[k]) is int) for r in records for k in ['trl_public_evidence_stage','crl_public_evidence_stage']))
    check('json_arrays',all(r['category_ids']==[r['category_id']] for r in records))
    check('json_csv_alignment',[r['case_id'] for r in records]==d.case_id.tolist())
    schema=json.loads((base/'case_hotspot_links.schema.json').read_text())
    check('schema_nullable_contract',schema['items']['properties']['trl_public_evidence_stage']['type']==['integer','null'])
    profiles=pd.read_csv(base/'theme_evidence_profiles.csv')
    check('no_theme_or_formal_grades',profiles.theme_trl.isna().all() and profiles.theme_crl.isna().all() and d.formal_trl.isna().all() and d.formal_crl.isna().all())
    with tempfile.TemporaryDirectory(prefix='energy-p0-') as tmp:
        out=Path(tmp)/'case_hotspot_links.csv'
        refresh_export(repo/'data',base/'case_hotspot_links.csv',FINAL/'energy-topic-identification/assets/full_nmf500/topic_catalog.csv',out)
        check('postprocess_idempotent',sha(out)==sha(base/'case_hotspot_links.csv') and sha(out.with_suffix('.json'))==sha(base/'case_hotspot_links.json'))
    rebuilt=rt.path('data_root')/'work/p0_repair_20261018/full_build/case_hotspot_links.csv'
    if rebuilt.is_file():
        f=pd.read_csv(rebuilt,dtype={'trl_public_evidence_stage':'Int64','crl_public_evidence_stage':'Int64'}).set_index('case_id')
        old=d.set_index('case_id');fields=['category_id','category_name','trl_public_evidence_stage','crl_public_evidence_stage']
        check('real_full_build_matches_export',f[fields].sort_index().equals(old[fields].sort_index()))
        check('real_full_mapping_unchanged',np.allclose(f.mapping_cosine.sort_index(),old.mapping_cosine.sort_index(),rtol=0,atol=1e-12))
    else:check('real_full_build_matches_export',False,'Missing isolated real-input rebuild')
    unchanged={
        'energy-topic-identification':['assets/full_nmf500/topic_catalog.csv','assets/full_nmf500/SUMMARY.json','pipelines/full_nmf/train.py'],
        'energy-topic-hotspots':['assets/full_nmf500/hotspot_metrics.csv','assets/full_nmf500/quarter_counts.csv','src/energy_hotspots/scoring.py'],
        'energy-technology-trl-crl':['trl_crl/engine.py','trl_crl/rules.py','trl_crl/pipeline.py']+[p.relative_to(repo).as_posix() for p in sorted((repo/'data').glob('*.json'))],
    }
    for module,paths in unchanged.items():
        for rel in paths:
            original=subprocess.check_output(['git','-C',str(FINAL/module),'show','HEAD:'+rel])
            check('unchanged_'+module+'/'+rel,hashlib.sha256(original).hexdigest()==sha(FINAL/module/rel))
    inputs=json.loads((FINAL/'provenance/INPUT_MANIFEST.json').read_text())
    check('input_preflight',inputs['passed'])
    check('input_config_fresh',next(x['sha256'] for x in inputs['files'] if x['role']=='runtime_config')==sha(rt.config_path))
    releases={}
    for module in unchanged:
        source=FINAL/module/'tools/check_current_release.py'
        spec=importlib.util.spec_from_file_location('p0_check_'+module,source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        releases[module]=m.validate(FINAL/module,require_tracked=False)
        check('release_'+module,releases[module]['passed'])
        for p in (FINAL/module/'pipelines/full_nmf').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
    check('python_syntax',True)
    # A plotting smoke check uses only nonmissing same-object pairs.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure,ax=plt.subplots(figsize=(5,3.8));ax.scatter(paired.trl_public_evidence_stage.to_numpy(dtype=float),paired.crl_public_evidence_stage.to_numpy(dtype=float),alpha=.65)
    ax.set(xlabel='TRL (public evidence)',ylabel='CRL (public evidence)',xlim=(.5,9.5),ylim=(.5,5.5),xticks=range(1,10),yticks=range(1,6),title='13 bounded objects with both axes')
    target=FINAL/'provenance/p0_maturity_plot_check.png';figure.tight_layout();figure.savefig(target,dpi=150);plt.close(figure)
    check('numeric_plot_rendered',target.is_file() and target.stat().st_size>0)
    report={'created_utc':datetime.now(timezone.utc).isoformat(),'passed':all(x['passed'] for x in checks),'checks':checks,'release_checks':releases,'counts':results['SUMMARY'],'name_mismatches_before':122,'name_mismatches_after':int(d.category_name.ne(d.category_id.map(catalog.name)).sum()),'external_model_calls':0,'full_classification_or_hotspots_recomputed':False,'maturity_mapping_rebuilt_for_validation':True,'production_publish_or_git_commit':False,'scope':'P0 export and runtime contracts; no semantic taxonomy approval or new maturity evidence.'}
    dest=FINAL/'provenance/P0_VALIDATION.json';dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'checks':len(checks),'objects':len(d),'same_object_pairs':len(paired),'output':str(dest)},ensure_ascii=False))
    for c in checks:
        if not c['passed']:print(json.dumps(c,ensure_ascii=False))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
