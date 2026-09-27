"""Audit the current full-corpus source, artifacts and documentation (stdlib)."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
ESSENTIAL={
    'energy-topic-identification':[
        'pipelines/full_nmf/common.py','pipelines/full_nmf/run.py',
        'pipelines/full_nmf/prepare.py','pipelines/full_nmf/train.py',
        'pipelines/full_nmf/fast_nmf.py','pipelines/full_nmf/encode.py',
        'pipelines/full_nmf/finalize.py','pipelines/full_nmf/publish_local.py',
        'pipelines/keyword_nmf/src/components.py','requirements-full-nmf.txt',
        'assets/full_nmf500/topic_catalog.csv','assets/full_nmf500/coverage.csv',
        'assets/full_nmf500/TRAINING_COMPLETE.json','assets/full_nmf500/VALIDATION.json'],
    'energy-topic-hotspots':[
        'pipelines/full_nmf/build.py','pipelines/full_nmf/experiments.py',
        'src/energy_hotspots/scoring.py','pyproject.toml',
        'assets/full_nmf500/hotspot_metrics.csv','assets/full_nmf500/quarter_counts.csv',
        'assets/full_nmf500/institution_citation_context.csv','assets/full_nmf500/experiments/COMPLETE.json'],
    'energy-technology-trl-crl':[
        'pipelines/full_nmf/build.py','pipelines/full_nmf/experiments.py',
        'pipelines/nmf500/mapping.py','pipelines/nmf500/experiments.py',
        'pipelines/nmf500/encode_context.py','trl_crl/engine.py','trl_crl/rules.py',
        'trl_crl/pipeline.py','data/objects.json','data/sources.json','data/evidence.json',
        'data/observations.json','data/gate_reviews.json','data/technical_profiles.json',
        'requirements.txt','assets/full_nmf500/case_hotspot_links.csv',
        'assets/full_nmf500/theme_context_top3.csv','assets/full_nmf500/experiments/COMPLETE.json'],
}
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()

def git_paths(root,untracked=False):
    args=['git','-C',str(root),'ls-files','-z','--cached']
    if untracked:args+=['--others','--exclude-standard']
    return set(subprocess.check_output(args).decode().split('\0'))-{''}

def inventory(root):
    result=[]
    for rel in git_paths(root,True):
        p=root/rel
        if not p.is_file():continue
        if (p.suffix=='.py' or rel.startswith('assets/full_nmf500/')
            or rel.startswith('data/') and p.suffix=='.json'
            or rel.startswith('docs/') and p.suffix=='.md'
            or rel=='README.md' or rel=='pyproject.toml'
            or p.name.startswith('requirements') and p.suffix=='.txt'):
            result.append(rel)
    return sorted(result)

def checked_path(root,rel):
    p=(root/rel).resolve()
    if not p.is_relative_to(root.resolve()) or not p.is_file() or (root/rel).is_symlink():
        raise ValueError('Missing/unsafe core file: '+rel)
    return p

def verify_hashes(root,files):
    for rel,digest in files.items():
        if sha(checked_path(root,rel))!=digest:raise ValueError('Checksum mismatch: '+rel)

def check_docs(root):
    count=0
    for rel in git_paths(root,True):
        p=root/rel
        if p.suffix!='.md' or not p.is_file():continue
        text=p.read_text();count+=1
        prose=re.sub(r'```[\s\S]*?```|`[^`]*`','',text)
        if re.search(r'v0\.2\.1|v020|v021|版本对比|主题效果对比|统一口径效果对比|历史版本|样本版|750(?:个|类|主题)',prose,re.I):
            raise ValueError('Outdated public documentation: '+rel)
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
            target=target.strip().split(' "')[0].strip('<>')
            if re.match(r'^[a-z]+:',target) or target.startswith('#'):continue
            target=unquote(target.split('#')[0])
            if not (p.parent/target).exists():raise ValueError('Broken link: '+rel+' -> '+target)
    return count

def validate(root=ROOT,require_tracked=True):
    core=root/'provenance/CORE_FILES.json'
    data=json.loads(core.read_text())
    for rel in ESSENTIAL[root.name]+['README.md','docs/METHOD.md','docs/REPRODUCING.md','tools/check_current_release.py']:
        if rel not in data['files']:raise ValueError('Required file omitted: '+rel)
    if set(data['files'])!=set(inventory(root)):raise ValueError('Core inventory changed')
    if require_tracked and not set(data['files'])<=git_paths(root):
        raise ValueError('Core files not yet in Git index')
    verify_hashes(root,data['files'])
    base=root/'assets/full_nmf500'
    manifest=json.loads((base/'MANIFEST.json').read_text())
    actual={str(p.relative_to(base)) for p in base.rglob('*') if p.is_file() and p.name!='MANIFEST.json'}
    if set(manifest['files'])!=actual:raise ValueError('Current artifact inventory mismatch')
    if any(p.startswith('topic_evaluation/') for p in actual):raise ValueError('Comparison artifacts in current release')
    verify_hashes(base,manifest['files'])
    complete=base/'experiments/COMPLETE.json'
    if complete.exists():
        record=json.loads(complete.read_text())
        if not record['passed'] or record['classification_summary_sha256']!=manifest['classification_summary_sha256']:
            raise ValueError('Experiment binding mismatch')
        verify_hashes(complete.parent,record['files'])
    summary=json.loads((base/'SUMMARY.json').read_text())
    population=summary.get('population_records',summary.get('classification_input_records',summary.get('full_source_records')))
    if population!=5119004:raise ValueError('Full population missing')
    docs=check_docs(root)
    return {'passed':True,'core_files':len(data['files']),'documents':docs,'population_records':population,
        'current_artifacts':len(actual),'all_core_files_tracked':require_tracked}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--write-manifest',action='store_true')
    args=p.parse_args()
    if args.write_manifest:
        files=inventory(ROOT)
        for rel in ESSENTIAL[ROOT.name]:
            if rel not in files:raise ValueError('Missing required core input: '+rel)
        data={'scope':'Current source, local modules, configuration, tests, evidence and compact results',
            'external_assets':'Full corpora, trained weights, embeddings and metadata databases are workspace runtime inputs; see docs/REPRODUCING.md.',
            'files':{rel:sha(ROOT/rel) for rel in files}}
        path=ROOT/'provenance/CORE_FILES.json';path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'core_files_written':len(files)}))
    else:print(json.dumps(validate(),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
