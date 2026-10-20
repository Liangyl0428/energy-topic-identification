"""A fresh standalone checkout resolves its own configuration without workspace parents."""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_config_and_data_overrides_are_independent_of_cwd(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('standalone_runtime', REPO / 'runtime_config.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.chdir(tmp_path)
    cfg = module.load_runtime(environ={'ENERGY_DATA_ROOT': str(tmp_path / 'external data')})
    assert cfg.config_path == REPO / 'config/runtime_paths.json'
    assert cfg.path('raw_data_dir') == tmp_path / 'external data/data'
    assert cfg.path('delivery_root') == REPO.parent
    assert cfg.path('hotspots_run') == REPO.parent / 'energy-topic-hotspots/outputs/full_nmf500_20260926'
