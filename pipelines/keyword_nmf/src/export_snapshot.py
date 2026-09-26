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
    for name in ['candidate_metrics.csv','selection.json','stability_metrics.csv']:
        shutil.copy2(source/name,dest/name)
    shutil.copy2(source/'REPORT.md',dest/'V020_MODEL_REPORT.md')
    hot=REPO.parent/'energy-topic-hotspots/outputs/nmf500_v021'
    for original,name in [('topic_catalog.csv','current_topic_catalog.csv'),
                          ('confidence_thresholds.json','current_confidence_thresholds.json'),
                          ('uniform_inference_changes.csv','uniform_inference_changes.csv'),
                          ('transfer_recalibration_audit.csv','transfer_recalibration_audit.csv')]:
        shutil.copy2(hot/original,dest/name)
    audit=json.loads((dest/'CURRENT_INFERENCE_AUDIT.json').read_text())
    m=audit['actual_inference_metrics']
    report=f'''# v0.2.1 主题分类重算

对142,000篇冻结论文统一执行固定H推断，使用 W[j] × ||H[j]||₂ 的贡献比较，
消除等价NMF分解中主题尺度对Top1的影响。保留500个组件编号，实际499个有论文。
与v0.2.0生产标签相比改变{audit['changed_from_v020']:,}篇（{audit['fraction_changed_from_v020']:.2%}）。

当前验证集抽样轮廓系数{m['sampled_cosine_silhouette']:.4f}，
BGE最近中心与关键词标签Top1一致率{m['keyword_embedding_top1_agreement']:.2%}，
ARI为{m['keyword_embedding_ari']:.4f}。这些是几何诊断，不是人工分类准确率；
主题仍重叠明显，500只作为冻结业务粒度，不能声称自然分离或选模最优。

current_topic_catalog.csv 为当前目录；current_validation_metrics.csv 是修正后的独立验证指标；
assignment_changes_v021.csv 和 topic_assignment_quality.csv 记录标签变动及歧义。
所有专利/政策均为待语义复核候选，论文相似度过滤不保证跨来源分类正确。

candidate_metrics.csv、selection.json、stability_metrics.csv及experiments/保留历史选模实验；
它们使用旧fit-W标签，不是v0.2.1分类指标。旧报告见V020_MODEL_REPORT.md。
严格审查与复现边界见 ../../docs/V0.2.1_AUDIT.md。
'''
    (dest/'REPORT.md').write_text(report)
    manifest={str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(dest.rglob('*')) if p.is_file() and p.name!='MANIFEST.json'}
    (dest/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Exported',len(manifest),'files')


if __name__=='__main__':
    export()
