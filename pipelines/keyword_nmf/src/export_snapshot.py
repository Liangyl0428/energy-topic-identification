"""Publish small numeric results, not full texts, fitted model or BGE vectors."""
import hashlib
import json
import shutil
from pathlib import Path

REPO=Path(__file__).resolve().parents[3]


def export():
    source=REPO/'pipelines/keyword_nmf/results'
    dest=REPO/'assets/nmf500'
    dest.mkdir(parents=True,exist_ok=True)
    for name in ['candidate_metrics.csv','selection.json','stability_metrics.csv','REPORT.md']:
        shutil.copy2(source/name,dest/name)
    hot=REPO.parent/'energy-topic-hotspots/outputs/nmf500'
    for original,name in [('topic_catalog.csv','current_topic_catalog.csv'),
                          ('confidence_thresholds.json','current_confidence_thresholds.json'),
                          ('uniform_inference_changes.csv','uniform_inference_changes.csv'),
                          ('transfer_recalibration_audit.csv','transfer_recalibration_audit.csv')]:
        shutil.copy2(hot/original,dest/name)
    manifest={str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(dest.rglob('*')) if p.is_file() and p.name!='MANIFEST.json'}
    (dest/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Exported',len(manifest),'files')


if __name__=='__main__':
    export()
