"""Packaging must not depend on mutable experiment code or overwrite deliveries."""
from pathlib import Path
import importlib.util
import os
import subprocess
import sys
import pytest

REPO = Path(__file__).resolve().parents[1]


def test_multilabel_rules_import_without_external_workspace(tmp_path):
    env = {**os.environ, 'ENERGY_DATA_ROOT': str(tmp_path), 'PYTHONDONTWRITEBYTECODE': '1'}
    code = 'import sys; sys.path.insert(0, sys.argv[1]); import run, review; assert run.base.relative_contributions'
    subprocess.run([sys.executable, '-c', code, str(REPO / 'pipelines/multilabel_scope')],
                   env=env, cwd=tmp_path, check=True, capture_output=True)
    assert list(tmp_path.iterdir()) == []


def test_assembly_rejects_existing_output_without_changing_it(tmp_path):
    spec = importlib.util.spec_from_file_location('assemble', REPO / 'tools/assemble_platform.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / 'delivery'
    output.mkdir()
    sentinel = output / 'user.txt'
    sentinel.write_text('keep')
    with pytest.raises(FileExistsError):
        module.assemble(tmp_path, output)
    assert sentinel.read_text() == 'keep'
