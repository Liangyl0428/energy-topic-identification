"""Verify published local P1 inputs, contracts, references and release hashes."""
from pathlib import Path
import importlib.util
import sys
import re
import xml.etree.ElementTree as ET

FINAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FINAL))
from p1_common import read, sha, write


def main():
    write(FINAL / 'provenance/P1_VALIDATION.json', {'passed': False, 'state': 'validation_running'})
    checks = []
    def check(name, condition):
        checks.append({'name': name, 'passed': bool(condition)})
    for rel, digest in read(FINAL / 'provenance/P1_FILES.json')['files'].items():
        check('sha:' + rel, sha(FINAL / rel) == digest)
    build = read(FINAL / 'assets/p1/BUILD.json')
    for kind in ['inputs', 'code']:
        for rel, digest in build[kind].items():
            check(kind + ':' + rel, sha(FINAL / rel) == digest)
    for name in ['energy-topic-identification', 'energy-topic-hotspots', 'energy-technology-trl-crl']:
        repo = FINAL / name
        spec = importlib.util.spec_from_file_location('release_' + name, repo / 'tools/check_current_release.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        check('release:' + name, module.validate(repo, require_tracked=False)['passed'])
    for path in [FINAL / 'README.md', *sorted((FINAL / 'docs').glob('*.md'))]:
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text()):
            if re.match(r'^[a-z]+:', target) or target.startswith('#'): continue
            target = target.split('#')[0]
            check('doclink:' + str(path.relative_to(FINAL)) + ':' + target, (path.parent / target).exists())
    root = ET.parse(FINAL / 'provenance/P1_TESTS.xml').getroot()
    suites = list(root.iter('testsuite'))
    tests = sum(int(s.get('tests', 0)) for s in suites)
    failures = sum(int(s.get('failures', 0)) + int(s.get('errors', 0)) for s in suites)
    check('p1_and_p0_regression_tests', tests >= 15 and failures == 0)
    summary = read(FINAL / 'assets/p1/SUMMARY.json')
    check('honest_coverage', summary['detailed_topic_cards'] == 3 and summary['full_cluster_scope_approved'] == 0
          and not summary['full_business_ranking_recomputed'] and summary['object_insights'] == 122)
    passed = all(c['passed'] for c in checks)
    write(FINAL / 'provenance/P1_VALIDATION.json', {'passed': passed, 'checks': checks,
          'test_count': tests, 'failures': failures, 'summary': summary,
          'scope': 'Local P1 integration and source integrity; no independent expert scope approval'})
    print({'passed': passed, 'checks': len(checks), 'tests': tests, 'failures': failures})
    if not passed:
        print([c for c in checks if not c['passed']]); raise SystemExit(1)


if __name__ == '__main__':
    main()
