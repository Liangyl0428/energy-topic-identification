"""Refresh current delivery inventories after P1, without changing P0 audit logs."""
from pathlib import Path
import subprocess
import sys

FINAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FINAL))
from p1_common import read, write, sha, VERSION
MODULES = ['energy-topic-identification', 'energy-topic-hotspots', 'energy-technology-trl-crl']


def main():
    for name in MODULES:
        repo = FINAL / name; base = repo / 'assets/full_nmf500'
        meta = read(base / 'POSTPROCESS_DELIVERY.json')
        meta.update(p1_business_version=VERSION,
                    p1_scope='Business review overlay, grounded numeric insights, bounded case actions and evidence links',
                    p1_full_business_scope_approved=False,
                    p1_original_numeric_artifacts_unchanged=True,
                    p1_reviewed_subset_counts_recomputed=True)
        write(base / 'POSTPROCESS_DELIVERY.json', meta)
        manifest = read(base / 'MANIFEST.json')
        manifest['files'] = {p.relative_to(base).as_posix(): sha(p) for p in sorted(base.rglob('*'))
                             if p.is_file() and p.name != 'MANIFEST.json'}
        write(base / 'MANIFEST.json', manifest)
        subprocess.run([sys.executable, str(repo / 'tools/check_current_release.py'), '--write-manifest'], check=True)
    for name in MODULES[:2]:
        subprocess.run([sys.executable, str(FINAL / name / 'tools/update_release_manifest.py')], check=True)
    paths = [FINAL / n for n in ['README.md', 'p1_common.py', 'tools/build_p1.py',
             'tools/refresh_p1_manifests.py', 'tools/validate_p1.py', 'tests/test_p1_delivery.py', 'provenance/P1_BASELINE.json']]
    paths += list((FINAL / 'docs').glob('*.md')) + list((FINAL / 'assets/p1').glob('*'))
    paths += [FINAL / 'energy-topic-identification/pipelines/business/build.py',
              FINAL / 'energy-topic-hotspots/src/energy_hotspots/insights.py',
              FINAL / 'energy-technology-trl-crl/trl_crl/insights.py']
    paths += list((FINAL / 'energy-topic-identification/data/business_review').glob('*.json'))
    for name in MODULES:
        repo = FINAL / name
        paths += [repo / 'README.md', repo / 'provenance/CORE_FILES.json',
                  repo / 'assets/full_nmf500/MANIFEST.json', repo / 'assets/full_nmf500/POSTPROCESS_DELIVERY.json']
        paths += list((repo / 'assets/full_nmf500/p1').glob('*'))
    paths += [FINAL / 'energy-topic-identification/provenance/SHA256SUMS.json',
              FINAL / 'energy-topic-hotspots/provenance/FILE_MANIFEST.json']
    write(FINAL / 'provenance/P1_FILES.json', {
        'version': VERSION, 'scope': 'P1 code, business inputs, outputs, documentation and current release manifests',
        'files': {str(p.relative_to(FINAL)): sha(p) for p in sorted(set(paths)) if p.is_file()}})


if __name__ == '__main__':
    main()
