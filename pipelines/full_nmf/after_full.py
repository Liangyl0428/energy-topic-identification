"""Independent, opt-in postprocessor. Never signals or restarts the base run.

--arm snapshots the approved local changes and remote tips, then waits for the
existing base completion marker. Tests and experiments must pass before any
commit or non-force push. Logs and receipts live in the ignored run directory.
"""
from common import *
import argparse
import fcntl
import re
import shutil
import subprocess
import sys
import time
import runpy
from urllib.parse import urlsplit

NAMES=['energy-topic-identification','energy-topic-hotspots','energy-technology-trl-crl']
PY=ROOT/'.venv-hotspots/bin/python'
JOB=RUN/'postprocess'
GENERATED=['README.md','provenance/SHA256SUMS.json','provenance/FILE_MANIFEST.json','provenance/CORE_FILES.json']


def git(repo,*args):
    return subprocess.check_output(['git','-C',str(repo),*args],text=True,
        env={**os.environ,'GIT_TERMINAL_PROMPT':'0'},stderr=subprocess.PIPE,timeout=120).strip()


def changed(repo):
    a=git(repo,'diff','--name-only','-z','HEAD').split('\0')
    b=git(repo,'ls-files','--others','--exclude-standard','-z').split('\0')
    return sorted(set(a+b)-{''})


def generated(path):return path in GENERATED or path.startswith('assets/full_nmf500/')


def in_scope(path):
    return generated(path) or path.startswith(('pipelines/full_nmf/','docs/')) or path in {
        'docs/FULL_NMF.md','docs/FULL_EXPERIMENTS.md','requirements-full-nmf.txt',
        'tests/test_full_nmf.py','tests/test_full_experiments.py','tests/test_full_delivery.py',
        'tools/update_release_manifest.py','tools/check_current_release.py','tests/test_current_release.py'}


def remote_tip(repo,branch):
    lines=git(repo,'ls-remote','--heads','origin','refs/heads/'+branch).splitlines()
    if len(lines)!=1:raise ValueError('Expected existing unique remote branch')
    return lines[0].split()[0]


def capture(repo):
    if git(repo,'diff','--cached','--name-only'):raise ValueError('Existing staged changes; refusing to mix commits')
    paths=changed(repo)
    if any(not in_scope(p) for p in paths):raise ValueError('Unrelated worktree changes in '+repo.name)
    branch=git(repo,'branch','--show-current')
    if branch!='main':raise ValueError('Only the inspected existing main branch is authorized')
    head=git(repo,'rev-parse','HEAD');tip=remote_tip(repo,branch)
    if head!=tip:raise ValueError('Local and remote tips differ; no automatic merge or overwrite')
    url=git(repo,'remote','get-url','--push','origin')
    if git(repo,'remote','get-url','origin')!=url or git(repo,'remote','get-url','--push','--all','origin')!=url:
        raise ValueError('Different or multiple fetch/push destinations require manual review')
    parsed=urlsplit(url)
    target=(parsed.hostname or 'ssh')+parsed.path if parsed.scheme else url.split('@')[-1]
    allfiles=set(git(repo,'ls-files','-z','--cached','--others','--exclude-standard').split('\0'))-{''}
    files={p:sha(repo/p) for p in allfiles if not generated(p)}
    # This checks configured authorship without putting email addresses in receipts.
    git(repo,'var','GIT_AUTHOR_IDENT');git(repo,'var','GIT_COMMITTER_IDENT')
    git(repo,'push','--dry-run','origin','HEAD:refs/heads/'+branch)
    return {'branch':branch,'head':head,'remote_tip':tip,'remote_target':target,
        'remote_url_sha256':hashlib.sha256(url.encode()).hexdigest(),'files':files,'approved_changes':paths}


def verify_worktree(repo,record):
    if git(repo,'branch','--show-current')!=record['branch'] or git(repo,'rev-parse','HEAD')!=record['head']:
        raise ValueError('Branch or HEAD changed in '+repo.name)
    if hashlib.sha256(git(repo,'remote','get-url','--push','origin').encode()).hexdigest()!=record['remote_url_sha256']:
        raise ValueError('Push target changed')
    if git(repo,'remote','get-url','origin')!=git(repo,'remote','get-url','--push','origin') or git(repo,'remote','get-url','--push','--all','origin')!=git(repo,'remote','get-url','origin'):
        raise ValueError('Fetch/push destinations changed')
    if git(repo,'diff','--cached','--name-only'):raise ValueError('Unexpected staged changes')
    for path,digest in record['files'].items():
        if not (repo/path).is_file() or sha(repo/path)!=digest:raise ValueError('Code/input changed after arming: '+path)
    approved=set(record['approved_changes'])
    for path in changed(repo):
        if not generated(path) and path not in approved:raise ValueError('Unapproved changed file: '+path)
    if remote_tip(repo,record['branch'])!=record['remote_tip']:raise ValueError('Remote advanced; manual reconciliation required')


def checked_assets(repo):
    base=repo/'assets/full_nmf500'
    manifest=json.loads((base/'MANIFEST.json').read_text())
    files={p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file() and p.name!='MANIFEST.json'}
    if files!=set(manifest['files']):raise ValueError('Asset manifest inventory mismatch in '+repo.name)
    for rel,digest in manifest['files'].items():
        p=base/rel
        if p.is_symlink() or p.suffix not in {'.csv','.json','.md'} or p.stat().st_size>=10*1024**2 or sha(p)!=digest:
            raise ValueError('Invalid public artifact: '+rel)
        if re.search(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}',p.read_text()):raise ValueError('Possible credential in artifact')
    return manifest


def run(command,cwd=None):
    print('RUN',*map(str,command),flush=True)
    subprocess.run(list(map(str,command)),cwd=cwd,check=True,
        env={**os.environ,'GIT_TERMINAL_PROMPT':'0','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'})


def status(stage,**extra):
    dump(JOB/'STATUS.json',{'stage':stage,'updated_unix':time.time(),'pid':os.getpid(),**extra})


def verify_experiments(folder,classification_hash):
    marker=json.loads((folder/'COMPLETE.json').read_text())
    if not marker['passed'] or marker['classification_summary_sha256']!=classification_hash:
        raise ValueError('Experiment not completed on the current classification')
    for name,digest in marker['files'].items():
        if Path(name).name!=name or sha(folder/name)!=digest:raise ValueError('Experiment checksum mismatch')
    return marker


def package(source,experiments):
    classification_hash=sha(source/'SUMMARY.json')
    reports={}
    for name,folder in experiments.items():
        reports[name]=verify_experiments(folder,classification_hash)
    for name in NAMES:
        repo=ROOT/name;manifest=checked_assets(repo);base=repo/'assets/full_nmf500'
        if manifest['classification_summary_sha256']!=classification_hash:raise ValueError('Mixed base results')
        if name in experiments:
            folder=experiments[name];target=base/'experiments';target.mkdir(exist_ok=True)
            for filename in [*reports[name]['files'],'COMPLETE.json']:
                shutil.copy2(folder/filename,target/filename)
                if filename.endswith('.md'):
                    (target/filename).write_text(current_report_text((target/filename).read_text()))
                manifest['files']['experiments/'+filename]=sha(target/filename)
            renderer=repo/'pipelines/full_nmf/report.py'
            if renderer.is_file():
                runpy.run_path(str(renderer))['render'](target)
                manifest['files']['experiments/REPORT.md']=sha(target/'REPORT.md')
            public_marker={**reports[name],'files':{f:sha(target/f) for f in reports[name]['files']},
                'documentation_normalized':True,'source_complete_sha256':sha(folder/'COMPLETE.json')}
            dump(target/'COMPLETE.json',public_marker)
            manifest['files']['experiments/COMPLETE.json']=sha(target/'COMPLETE.json')
        delivery={'full_population_records':json.loads((source/'SUMMARY.json').read_text())['population_records'],
            'classification_summary_sha256':classification_hash,'experiments_passed':True,
            'experiment_complete_sha256':{n:sha(p/'COMPLETE.json') for n,p in experiments.items()},
            'publication':'Push receipts are recorded separately after remote verification; this file is not proof of push.',
            'evidence_limit':'Full topic mapping; maturity remains bounded to existing reviewed objects.'}
        dump(base/'POSTPROCESS_DELIVERY.json',delivery)
        manifest['files']['POSTPROCESS_DELIVERY.json']=sha(base/'POSTPROCESS_DELIVERY.json')
        dump(base/'MANIFEST.json',manifest)
        checked_assets(repo)
        readme=repo/'README.md';text=readme.read_text()
        notice='\n\n<!-- FULL_EXPERIMENTS -->\n全量消融与灵敏度实验已重新计算并通过验证。'
        notice+=('[实验报告](assets/full_nmf500/experiments/REPORT.md)。' if name in experiments else '[三仓库实验交付绑定](assets/full_nmf500/POSTPROCESS_DELIVERY.json)。')
        notice+='具体范围与证据边界见[实验及发布流程](docs/FULL_EXPERIMENTS.md)。\n'
        if '<!-- FULL_EXPERIMENTS -->' not in text:readme.write_text(text+notice)


def execute(config):
    marker=RUN/'ALL_REPOSITORIES_COMPLETE.json'
    while not marker.exists():
        status('waiting_for_base_completion',base_pid=config['base_pid'],does_not_stop_base=True)
        cmd=Path(f"/proc/{config['base_pid']}/cmdline")
        if not cmd.exists() or b'full_nmf/run.py' not in cmd.read_bytes():
            if marker.exists():break
            raise RuntimeError('Base runner exited before completion; no restart or publication attempted')
        time.sleep(30)
    source=json.loads((RUN/'SUMMARY.json').read_text())
    completion=json.loads((RUN/'COMPLETE.json').read_text())
    if not all(source[k] for k in ['full_training','full_inference','full_transfer']) or source['population_records']!=5119004:
        raise ValueError('Expected completed full frozen population')
    if completion['summary_sha256']!=sha(RUN/'SUMMARY.json') or completion['validation_sha256']!=sha(RUN/'VALIDATION.json'):
        raise ValueError('Completion hashes mismatch')
    if config.get('expected_model_sha256') and source.get('model_sha256')!=config['expected_model_sha256']:
        raise ValueError('Completed classification uses a different trained model')
    for name in NAMES:verify_worktree(ROOT/name,config['repositories'][name])
    hot=ROOT/NAMES[1];trl=ROOT/NAMES[2]
    hi=hot/'outputs/full_nmf500_20260926';ti=trl/'results/full_nmf500_20260926'
    outputs={NAMES[1]:hi/'experiments',NAMES[2]:ti/'experiments'}
    if config.get('reuse_verified_experiments'):
        for folder in outputs.values():verify_experiments(folder,sha(RUN/'SUMMARY.json'))
    else:
        status('hotspot_experiments')
        run([PY,hot/'pipelines/full_nmf/experiments.py','--classification',RUN,'--input',hi,'--output',outputs[NAMES[1]]])
        status('maturity_experiments')
        run([PY,trl/'pipelines/full_nmf/experiments.py','--classification',RUN,'--input',ti,'--output',outputs[NAMES[2]]])
    status('tests_and_packaging')
    run([PY,'-m','pytest','tests/test_keyword_nmf.py','tests/test_full_nmf.py','tests/test_full_delivery.py','-q'],ROOT/NAMES[0])
    run([PY,'-m','pytest','-q'],hot)
    run([PY,'-m','pytest','-q'],trl)
    for name in NAMES:verify_worktree(ROOT/name,config['repositories'][name])
    package(RUN,outputs)
    for name in NAMES:run([PY,ROOT/name/'tools/check_current_release.py','--write-manifest'])
    run([PY,ROOT/NAMES[0]/'tools/update_release_manifest.py'])
    run([PY,ROOT/NAMES[0]/'tools/validate_release.py'])
    run([PY,hot/'tools/update_release_manifest.py'])
    for name in NAMES:
        repo=ROOT/name;verify_worktree(repo,config['repositories'][name]);checked_assets(repo)
        git(repo,'diff','--check')
    dump(JOB/'EXPERIMENTS_AND_RELEASE_VALIDATED.json',{'passed':True,
        'classification_summary_sha256':sha(RUN/'SUMMARY.json'),'all_three_repositories_checked':True})
    status('committing')
    receipts={}
    # Prepare all three commits before pushing any repository.
    for name in NAMES:
        repo=ROOT/name;record=config['repositories'][name];verify_worktree(repo,record)
        paths=changed(repo)
        if not paths:raise ValueError('No delivery changes to commit')
        git(repo,'add','--',*paths)
        if set(git(repo,'diff','--cached','--name-only').splitlines())!=set(paths):raise ValueError('Index changed unexpectedly')
        git(repo,'commit','-m','Add full-corpus NMF500 results, diagnostics and delivery workflow')
        commit=git(repo,'rev-parse','HEAD')
        receipts[name]={'commit':commit,'branch':record['branch'],'remote':record['remote_target'],'pushed':False}
        dump(JOB/'PUSH_RECEIPTS.json',receipts)
    for name in NAMES:
        record=config['repositories'][name]
        if remote_tip(ROOT/name,record['branch'])!=record['remote_tip']:raise ValueError('Remote advanced before push')
    status('pushing')
    for name in NAMES:
        repo=ROOT/name;record=config['repositories'][name]
        if git(repo,'rev-parse','HEAD')!=receipts[name]['commit'] or changed(repo):raise ValueError('Worktree changed before push')
        if hashlib.sha256(git(repo,'remote','get-url','--push','origin').encode()).hexdigest()!=record['remote_url_sha256']:raise ValueError('Remote changed before push')
        if remote_tip(repo,record['branch'])!=record['remote_tip']:raise ValueError('Remote advanced before this push')
        git(repo,'push','origin','HEAD:refs/heads/'+record['branch'])
        tip=remote_tip(repo,record['branch'])
        if tip!=receipts[name]['commit']:raise ValueError('Remote commit verification failed')
        receipts[name].update(pushed=True,verified_remote_commit=tip)
        dump(JOB/'PUSH_RECEIPTS.json',receipts)
    dump(RUN/'FULL_DELIVERY_AND_PUSH_COMPLETE.json',{'passed':True,'repositories':receipts,
        'classification_summary_sha256':sha(RUN/'SUMMARY.json')})
    status('complete',repositories=receipts)


def main():
    p=argparse.ArgumentParser();p.add_argument('--arm',action='store_true');p.add_argument('--base-pid',type=int);a=p.parse_args()
    if not a.arm or not a.base_pid:p.error('Explicit --arm and --base-pid required; no implicit publication')
    JOB.mkdir(parents=True,exist_ok=True)
    lock=(JOB/'LOCK').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (JOB/'CONFIG.json').exists():raise RuntimeError('Already armed; inspect existing status, do not start duplicate publishers')
    try:
        status('preflight')
        config={'base_pid':a.base_pid,'created_unix':time.time(),'repositories':{n:capture(ROOT/n) for n in NAMES},
            'expected_model_sha256':json.loads((RUN/'TRAINING_COMPLETE.json').read_text())['model_sha256'],
            'authorized_workflow':'wait for base completion, full diagnostics, checks, local commits, non-force push to existing origin/main'}
        dump(JOB/'CONFIG.json',config)
        with (JOB/'runner.log').open('a',buffering=1) as log:
            os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
            execute(config)
    except Exception as exc:
        status('failed_no_further_publication',error_type=type(exc).__name__,error=str(exc),
            note='Existing base processes were not stopped. Inspect log and receipts; no force push or rollback.')
        raise


if __name__=='__main__':main()
