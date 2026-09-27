"""Documentation refresh must preserve current code and detect broken delivery."""
from pathlib import Path
import importlib.util
import hashlib
import pytest

SRC=Path(__file__).resolve().parents[1]/'tools/check_current_release.py'
spec=importlib.util.spec_from_file_location('current_release_checks',SRC)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_missing_or_changed_core_file_fails(tmp_path):
    p=tmp_path/'core.py';p.write_text('value=1\n')
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    m.verify_hashes(tmp_path,{'core.py':digest})
    p.write_text('value=2\n')
    with pytest.raises(ValueError,match='Checksum'):m.verify_hashes(tmp_path,{'core.py':digest})
    with pytest.raises(ValueError,match='Missing'):m.verify_hashes(tmp_path,{'missing.py':digest})

def test_outdated_docs_and_broken_links_fail(tmp_path,monkeypatch):
    p=tmp_path/'README.md'
    monkeypatch.setattr(m,'git_paths',lambda *a,**k:{'README.md'})
    p.write_text('v0.2.1')
    with pytest.raises(ValueError,match='Outdated'):m.check_docs(tmp_path)
    p.write_text('[entry](missing.py)')
    with pytest.raises(ValueError,match='Broken'):m.check_docs(tmp_path)
    p.write_text('Current full-corpus pipeline')
    assert m.check_docs(tmp_path)==1

def test_paths_cannot_escape_repo(tmp_path):
    with pytest.raises(ValueError):m.checked_path(tmp_path,'../outside.py')
