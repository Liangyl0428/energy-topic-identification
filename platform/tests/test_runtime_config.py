import importlib.util
import json
from pathlib import Path
import shutil
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime_config import load_runtime


def test_relative_paths_are_config_relative_and_cwd_independent(tmp_path,monkeypatch):
    folder=tmp_path/'portable bundle';(folder/'config').mkdir(parents=True)
    p=folder/'config/paths.json'
    p.write_text(json.dumps({'schema_version':1,'paths':{'data_root':'../../external data','corpus_dir':'{data_root}/frozen corpus','metadata_db':"{data_root}/owner's database.duckdb"},'windows':{}}))
    monkeypatch.chdir('/tmp')
    cfg=load_runtime(p,environ={})
    assert cfg.path('data_root')==(tmp_path/'external data').resolve()
    assert cfg.path('corpus_dir')==tmp_path/'external data/frozen corpus'
    assert cfg.path('metadata_db')==tmp_path/"external data/owner's database.duckdb"
    with pytest.raises(FileNotFoundError,match='metadata_db'):cfg.require('metadata_db','file')


def test_env_override_and_legacy_run_precedence(tmp_path):
    cfg=load_runtime(ROOT/'config/runtime_paths.json',environ={'ENERGY_DATA_ROOT':str(tmp_path),'ENERGY_CORPUS_DIR':str(tmp_path/'override'),'ENERGY_CLASSIFICATION_RUN':str(tmp_path/'new'),'FULL_NMF_RUN':str(tmp_path/'legacy')})
    assert cfg.path('corpus_dir')==tmp_path/'override'
    assert cfg.path('classification_run')==tmp_path/'legacy'
    assert cfg.path('metadata_db')==tmp_path/'analyze/data/independent_corpus.duckdb'


def test_moved_bundle_resolves_its_own_delivery_paths(tmp_path):
    folder=tmp_path/'moved final';(folder/'config').mkdir(parents=True)
    shutil.copy2(ROOT/'runtime_config.py',folder/'runtime_config.py')
    shutil.copy2(ROOT/'config/runtime_paths.json',folder/'config/runtime_paths.json')
    spec=importlib.util.spec_from_file_location('moved_runtime',folder/'runtime_config.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    cfg=module.load_runtime(environ={'ENERGY_DATA_ROOT':str(tmp_path/'external')})
    assert cfg.path('hotspots_run')==folder/'energy-topic-hotspots/outputs/full_nmf500_20260926'
    assert cfg.path('maturity_run')==folder/'energy-technology-trl-crl/results/full_nmf500_20260926'


def test_cycles_and_missing_config_fail_clearly(tmp_path):
    p=tmp_path/'paths.json';p.write_text(json.dumps({'schema_version':1,'paths':{'data_root':'{corpus_dir}','corpus_dir':'{data_root}'},'windows':{}}))
    with pytest.raises(ValueError,match='Cyclic'):load_runtime(p,environ={}).path('data_root')
    with pytest.raises(FileNotFoundError,match='ENERGY_PLATFORM_CONFIG'):load_runtime(tmp_path/'missing.json',environ={})


def test_embedded_source_paths_rebase_only_through_declared_prefix(tmp_path):
    cfg=load_runtime(ROOT/'config/runtime_paths.json',environ={'ENERGY_DATA_ROOT':str(tmp_path)})
    assert cfg.source_path('/pyg-vepfs/public/lyl/openalex_energy_fetch/data/article/paper.csv')==tmp_path/'data/article/paper.csv'
    assert cfg.source_path('/unrelated/paper.csv')==Path('/unrelated/paper.csv')
