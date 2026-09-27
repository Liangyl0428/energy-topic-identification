"""Publisher safety checks use only disposable local Git repositories."""
from pathlib import Path
import json
import importlib.util
import subprocess
import sys
import pytest

SRC=Path(__file__).resolve().parents[1]/'pipelines/full_nmf'
sys.path.insert(0,str(SRC))
spec=importlib.util.spec_from_file_location('full_delivery',SRC/'after_full.py')
delivery=importlib.util.module_from_spec(spec);spec.loader.exec_module(delivery)


def git(repo,*args):
    return subprocess.check_output(['git','-C',str(repo),*args],text=True,stderr=subprocess.PIPE).strip()


def fixture_repo(tmp_path):
    remote=tmp_path/'remote.git';subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
    repo=tmp_path/'repo';repo.mkdir();git(repo,'init','-b','main')
    git(repo,'config','user.name','Fixture');git(repo,'config','user.email','fixture@example.invalid')
    (repo/'README.md').write_text('baseline')
    git(repo,'add','README.md');git(repo,'commit','-m','baseline')
    git(repo,'remote','add','origin',str(remote));git(repo,'push','-u','origin','main')
    path=repo/'pipelines/full_nmf';path.mkdir(parents=True)
    (path/'new.py').write_text('value=1\n')
    return repo


def test_frozen_code_and_remote_are_required(tmp_path):
    repo=fixture_repo(tmp_path);record=delivery.capture(repo)
    delivery.verify_worktree(repo,record)
    assert git(repo,'rev-parse','HEAD')==record['remote_tip']
    (repo/'pipelines/full_nmf/new.py').write_text('value=2\n')
    with pytest.raises(ValueError,match='Code/input changed'):delivery.verify_worktree(repo,record)


def test_unrelated_work_is_not_staged(tmp_path):
    repo=fixture_repo(tmp_path);record=delivery.capture(repo)
    (repo/'unrelated.txt').write_text('user work')
    with pytest.raises(ValueError,match='Unapproved changed file'):delivery.verify_worktree(repo,record)
    assert git(repo,'diff','--cached','--name-only')==''
    assert delivery.remote_tip(repo,'main')==record['remote_tip']


def test_evaluation_is_required_and_checksums_are_enforced(tmp_path):
    source=tmp_path/'run';folder=source/'topic_evaluation';folder.mkdir(parents=True)
    delivery.dump(source/'SUMMARY.json',{'fixture':True})
    delivery.dump(folder/'COMPLETE.json',{'passed':True,
        'classification_summary_sha256':delivery.sha(source/'SUMMARY.json'),'files':{}})
    with pytest.raises(ValueError,match='coherence'):
        delivery.verify_topic_evaluation(source)
    (folder/'RESULTS.md').write_text('fixture')
    delivery.dump(folder/'COMPLETE.json',{'passed':True,
        'classification_summary_sha256':delivery.sha(source/'SUMMARY.json'),
        'files':{'RESULTS.md':'incorrect_digest'}})
    with pytest.raises(ValueError,match='checksum'):
        delivery.verify_topic_evaluation(source)


def test_remote_changes_block_publication(tmp_path):
    repo=fixture_repo(tmp_path);record=delivery.capture(repo)
    other=tmp_path/'other';subprocess.run(['git','clone',str(tmp_path/'remote.git'),str(other)],check=True,capture_output=True)
    git(other,'checkout','main');git(other,'config','user.name','Fixture');git(other,'config','user.email','fixture@example.invalid')
    (other/'README.md').write_text('another editor')
    git(other,'add','README.md');git(other,'commit','-m','external change');git(other,'push','origin','main')
    with pytest.raises(ValueError,match='Remote advanced'):delivery.verify_worktree(repo,record)


def test_missing_base_marker_does_not_run_experiments_or_push(tmp_path,monkeypatch):
    monkeypatch.setattr(delivery,'RUN',tmp_path);monkeypatch.setattr(delivery,'JOB',tmp_path/'postprocess')
    monkeypatch.setattr(delivery,'run',lambda *a,**k:pytest.fail('Must not run before base completion'))
    monkeypatch.setattr(delivery,'git',lambda *a,**k:pytest.fail('Must not touch Git before base completion'))
    with pytest.raises(RuntimeError,match='Base runner exited'):delivery.execute({'base_pid':99999999})
    assert not (tmp_path/'FULL_DELIVERY_AND_PUSH_COMPLETE.json').exists()


def test_orchestrator_commits_and_verifies_three_local_remotes(tmp_path,monkeypatch):
    names=['one','two','three'];records={}
    for name in names:
        folder=tmp_path/name;folder.mkdir()
        repo=fixture_repo(folder)
        records[name]=delivery.capture(repo)
    paths=[name+'/repo' for name in names]
    config={'base_pid':99999999,'repositories':{path:records[name] for path,name in zip(paths,names)}}
    source=tmp_path/'classification';source.mkdir();job=source/'postprocess';job.mkdir()
    monkeypatch.setattr(delivery,'ROOT',tmp_path);monkeypatch.setattr(delivery,'RUN',source)
    monkeypatch.setattr(delivery,'JOB',job);monkeypatch.setattr(delivery,'NAMES',paths)
    (source/'ALL_REPOSITORIES_COMPLETE.json').write_text('{}')
    delivery.dump(source/'SUMMARY.json',{'full_training':True,'full_inference':True,'full_transfer':True,'population_records':5119004})
    delivery.dump(source/'VALIDATION.json',{'passed':True})
    delivery.dump(source/'COMPLETE.json',{'summary_sha256':delivery.sha(source/'SUMMARY.json'),'validation_sha256':delivery.sha(source/'VALIDATION.json')})
    calls=[]
    monkeypatch.setattr(delivery,'run',lambda command,cwd=None:calls.append(command))
    def package(*args):
        for path in paths:
            base=tmp_path/path/'assets/full_nmf500';base.mkdir(parents=True)
            (base/'REPORT.md').write_text('Synthetic fixture artifact, not a real full-data result.')
            delivery.dump(base/'MANIFEST.json',{'files':{'REPORT.md':delivery.sha(base/'REPORT.md')}})
    monkeypatch.setattr(delivery,'package',package)
    monkeypatch.setattr(delivery,'verify_topic_evaluation',lambda source:pytest.fail('Current delivery must not require version comparisons'))
    delivery.execute(config)
    receipt=json.loads((source/'FULL_DELIVERY_AND_PUSH_COMPLETE.json').read_text())
    assert receipt['passed'] and len(calls)==11
    for path in paths:
        row=receipt['repositories'][path]
        assert row['pushed'] and row['verified_remote_commit']==delivery.remote_tip(tmp_path/path,'main')
        assert row['commit']!=config['repositories'][path]['head']


def test_packaging_does_not_publish_comparison_reports(tmp_path,monkeypatch):
    source=tmp_path/'run';source.mkdir()
    delivery.dump(source/'SUMMARY.json',{'population_records':5119004})
    comparison=source/'topic_evaluation';comparison.mkdir()
    (comparison/'REPORT.md').write_text('Optional analysis is not a current publication artifact.')
    repo=tmp_path/'repo';base=repo/'assets/full_nmf500';base.mkdir(parents=True)
    (repo/'README.md').write_text('# Current method\n\nCurrent implementation.\n')
    (base/'REPORT.md').write_text('Current result.')
    delivery.dump(base/'MANIFEST.json',{'classification_summary_sha256':delivery.sha(source/'SUMMARY.json'),
        'files':{'REPORT.md':delivery.sha(base/'REPORT.md')}})
    monkeypatch.setattr(delivery,'ROOT',tmp_path);monkeypatch.setattr(delivery,'NAMES',['repo'])
    delivery.package(source,{})
    assert not (base/'topic_evaluation').exists()
    assert 'TOPIC_EVALUATION' not in (repo/'README.md').read_text()
    delivery.checked_assets(repo)
