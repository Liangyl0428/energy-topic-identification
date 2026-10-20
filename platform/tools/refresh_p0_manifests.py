"""Refresh local delivery checksums after an authorized P0 edit; never commit/push."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys

FINAL=Path(__file__).resolve().parents[1]
NAMES=['energy-topic-identification','energy-topic-hotspots','energy-technology-trl-crl']


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    for name in NAMES:
        repo=FINAL/name;base=repo/'assets/full_nmf500';meta=base/'POSTPROCESS_DELIVERY.json'
        d=json.loads(meta.read_text())
        d.update(documentation_only_refresh=False,p0_repair='2026-10-18',p0_scope='Typed maturity export, current topic identity, explicit runtime configuration and data dictionary',classification_and_hotspot_values_unchanged=True)
        if name=='energy-technology-trl-crl':
            d.update(computed_numeric_artifacts_unchanged=False,maturity_assessment_values_unchanged=True,maturity_export_schema='integer_or_null_with_separate_status_and_text',current_category_names_synchronized=True)
        meta.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
        previous=json.loads((base/'MANIFEST.json').read_text())
        previous['files']={p.relative_to(base).as_posix():sha(p) for p in sorted(base.rglob('*')) if p.is_file() and p.name!='MANIFEST.json'}
        (base/'MANIFEST.json').write_text(json.dumps(previous,ensure_ascii=False,indent=2)+'\n')
        subprocess.run([sys.executable,str(repo/'tools/check_current_release.py'),'--write-manifest'],check=True)
    subprocess.run([sys.executable,str(FINAL/NAMES[0]/'tools/update_release_manifest.py')],check=True)
    subprocess.run([sys.executable,str(FINAL/NAMES[1]/'tools/update_release_manifest.py')],check=True)


if __name__=='__main__':main()
