"""Copy compact verified outputs into each repository; never package raw corpora."""
from common import *
import shutil
import subprocess
import sys


def main():
    if not (RUN/'COMPLETE.json').exists():raise RuntimeError('Full classification is not complete')
    jobs=[(REPO,RUN,['SUMMARY.json','VALIDATION.json','REPORT.md','coverage.csv','topic_catalog.csv','topic_assignment_quality.csv','QUALITY_DIAGNOSTICS.json','ASSIGNMENTS_MANIFEST.json','TRAINING_COMPLETE.json','INFERENCE_COMPLETE.json','VOCABULARY_COMPLETE.json','ENCODING_COMPLETE.json']),
        (ROOT/'energy-topic-hotspots',ROOT/'energy-topic-hotspots/outputs/full_nmf500_20260926',['SUMMARY.json','REPORT.md','coverage.csv','topic_catalog.csv','hotspot_metrics.csv','quarter_counts.csv','institution_citation_context.csv','cross_source_signals.csv','transfer_source_summary.csv','core_components.csv','emerging_components.csv']),
        (ROOT/'energy-technology-trl-crl',ROOT/'energy-technology-trl-crl/results/full_nmf500_20260926',['SUMMARY.json','REPORT.md','theme_context_top3.csv','case_hotspot_links.csv','theme_evidence_profiles.csv'])]
    for repo,source,names in jobs:
        target=repo/'assets/full_nmf500';target.mkdir(parents=True,exist_ok=True)
        for name in names:
            shutil.copy2(source/name,target/name)
            if name.endswith('.md'):(target/name).write_text(current_report_text((target/name).read_text()))
        dump(target/'MANIFEST.json',{'files':{str(p.relative_to(target)):sha(p) for p in target.rglob('*') if p.is_file() and p.name!='MANIFEST.json'},'classification_summary_sha256':sha(RUN/'SUMMARY.json')})
        readme=repo/'README.md'
        text=readme.read_text()
        notice=('全量冻结快照已完成：4,831,088篇论文、281,295条专利、6,621条政策，共5,119,004条。'
            '查看[全量结果报告](assets/full_nmf500/REPORT.md)、[覆盖与校验记录](assets/full_nmf500/)。'
            '主题编号F0001–F0500；自动候选需语义审核。')
        opening=text.split('\n\n',2)
        if len(opening)!=3:raise ValueError('Unexpected README structure')
        readme.write_text(opening[0]+'\n\n'+notice+'\n\n'+opening[2])
        print('UPDATED',repo.name,len(names),'verified assets',flush=True)
    # Rebuild release manifests only after final assets and README are in place.
    for repo,_,_ in jobs:
        subprocess.run([sys.executable,str(repo/'tools/check_current_release.py'),'--write-manifest'],check=True)
    subprocess.run([sys.executable,str(REPO/'tools/update_release_manifest.py')],check=True)
    subprocess.run([sys.executable,str(REPO/'tools/validate_release.py')],check=True)
    hot=ROOT/'energy-topic-hotspots'
    subprocess.run([sys.executable,str(hot/'tools/update_release_manifest.py')],check=True)
    dump(RUN/'RELEASE_VALIDATION.json',{'identification':True,'hotspots':True,
        'maturity_assets_manifest':sha(ROOT/'energy-technology-trl-crl/assets/full_nmf500/MANIFEST.json')})


if __name__=='__main__':main()
