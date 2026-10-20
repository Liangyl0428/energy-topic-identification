"""Validate compact delivery integrity without treating it as semantic approval."""
import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
FINAL=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(FINAL))
from p1_common import read,write,sha

def main(refresh=False):
    manifest=FINAL/'provenance/P2_FILES.json'
    paths=[FINAL/'README.md',FINAL/'preview/index.html']
    paths+=list((FINAL/'docs').glob('P2*.md'))
    paths+=list((FINAL/'assets/p2').glob('*'))
    paths+=list((FINAL/'tools').glob('*p2*'))
    paths+=[FINAL/'tests/test_p2_delivery.py',FINAL/'energy-topic-identification/data/business_v2/development_title_review.json']
    paths+=[FINAL/'provenance'/n for n in ['P2_TESTS.xml','P2_BROWSER.json','P2_PREVIEW_DESKTOP.png','P2_PREVIEW_MOBILE.png']]
    for name in ['energy-topic-identification','energy-topic-hotspots','energy-technology-trl-crl']:
        paths+=list((FINAL/name/'assets/full_nmf500/p2').glob('*'))
    files={str(p.relative_to(FINAL)):sha(p) for p in sorted(paths) if p.is_file()}
    if refresh:
        write(manifest,{'scope':'P2 rules, code, local outputs, interface and technical verification','files':files})
    checks=[]
    def check(name,ok):checks.append({'name':name,'passed':bool(ok)})
    check('complete_manifest_inventory',set(read(manifest)['files'])==set(files))
    for p,digest in read(manifest)['files'].items():check('sha:'+p,files.get(p)==digest)
    s=read(FINAL/'assets/p2/SUMMARY.json');finger=s['input_fingerprint']
    check('builder_matches_outputs',sha(FINAL/'tools/build_p2.py')==finger['builder_sha256'])
    check('taxonomy_matches_outputs',sha(FINAL/'tools/p2_taxonomy.py')==finger['taxonomy_sha256'])
    check('all_records_screened',s['population_records']==5119004 and s['full_corpus_title_screening_completed'])
    check('honest_scope',not s['semantic_accuracy_independently_validated'] and s['expert_approved_topics']==0 and not s['future_predictions_available'])
    for p in [FINAL/'README.md',*sorted((FINAL/'docs').glob('*.md'))]:
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text()):
            if re.match(r'^[a-z]+:',target) or target.startswith('#'):continue
            check('doclink:'+p.name+':'+target,(p.parent/target.split('#')[0]).exists())
    tree=ET.parse(FINAL/'provenance/P2_TESTS.xml')
    suites=list(tree.getroot().iter('testsuite'))
    tests=sum(int(s.get('tests',0)) for s in suites)
    failures=sum(int(s.get('errors',0))+int(s.get('failures',0)) for s in suites)
    check('regression_tests',tests>=35 and failures==0)
    check('browser_interactions',read(FINAL/'provenance/P2_BROWSER.json')['passed'])
    membership=FINAL.parent/s['membership_artifact']
    if membership.exists():check('full_membership_fingerprint',sha(membership)==s['membership_sha256'])
    record={'passed':all(c['passed'] for c in checks),'checks':checks,'tests':tests,'failures':failures,
        'semantic_expert_approval':False,'production_deployed':False,
        'scope':'Local data, lineage, UI and regression verification; not semantic quality certification'}
    write(FINAL/'provenance/P2_VALIDATION.json',record)
    print({'passed':record['passed'],'checks':len(checks),'tests':tests,'failures':failures})
    if not record['passed']:
        print([c for c in checks if not c['passed']]);raise SystemExit(1)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true');a=p.parse_args();main(a.refresh)
