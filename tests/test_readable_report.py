"""报告必须可再生，不能写入原始 JSON 块或空表。"""
from pathlib import Path
import runpy
import shutil

ROOT=Path(__file__).resolve().parents[1]

def test_readable_report_is_reproducible(tmp_path):
    source=ROOT/'assets/full_nmf500'
    for p in source.iterdir():
        if p.is_file():shutil.copy2(p,tmp_path/p.name)
    report=runpy.run_path(str(ROOT/'pipelines/full_nmf/report.py'))['render'](tmp_path)
    assert report==(source/'REPORT.md').read_text()
    assert '## 结论' in report
    assert '| ---' in report
    assert '"input_sha256"' not in report
    assert '"classification_summary_sha256"' not in report
    assert '不' in report


def test_structure_lists_every_versioned_file():
    import subprocess
    files=subprocess.check_output(['git','-C',str(ROOT),'ls-files','-z']).decode().split('\0')
    text=(ROOT/'docs/PROJECT_STRUCTURE.md').read_text()
    for rel in files:
        if rel and (ROOT/rel).is_file():assert Path(rel).name in text,rel
