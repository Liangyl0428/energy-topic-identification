"""Post-hoc model-selection sensitivity and metric ablation, no new model fitting."""
import argparse
import json
from pathlib import Path

import pandas as pd
import numpy as np

REPO=Path(__file__).resolve().parents[3]
METRICS={'sampled_cosine_silhouette':False,'simplified_silhouette_mean':False,
         'davies_bouldin':True,'nearest_center_cosine_mean':True,
         'empty_topic_fraction':True,'keyword_embedding_ari':False}


def choose(frame,penalty=.15,tolerance=.05,omit=None):
    if not np.isfinite([penalty,tolerance]).all() or penalty<0 or tolerance<0:
        raise ValueError('Penalty and tolerance must be finite and nonnegative')
    if omit is not None and omit not in METRICS:
        raise ValueError('Unknown metric ablation')
    z=frame[frame.requested_k.between(450,550)].set_index('requested_k')
    if z.empty or not z.index.is_unique or not np.isfinite(z[list(METRICS)]).all().all():
        raise ValueError('Selection requires unique candidates and complete finite metrics')
    ranks=pd.DataFrame({m:z[m].rank(ascending=ascending) for m,ascending in METRICS.items() if m!=omit})
    score=ranks.mean(axis=1)+penalty*abs(z.index-500)/50
    tied=score[score<=score.min()+tolerance]
    return min(tied.index,key=lambda k:(abs(k-500),score[k],k))


def run(inp,out):
    out.mkdir(parents=True,exist_ok=True)
    metrics=pd.read_csv(inp/'candidate_metrics.csv')
    rows=[]
    for penalty in [0.,.05,.15,.30]:
        for tolerance in [0.,.01,.02,.05,.10]:
            rows.append(dict(kind='preference_sensitivity',omitted_metric='',penalty=penalty,
                practical_tie_tolerance=tolerance,selected_k=choose(metrics,penalty,tolerance)))
    for omit in METRICS:
        rows.append(dict(kind='selection_metric_ablation',omitted_metric=omit,penalty=.15,
            practical_tie_tolerance=.05,selected_k=choose(metrics,omit=omit)))
    result=pd.DataFrame(rows)
    result.to_csv(out/'selection_sensitivity.csv',index=False)
    assert choose(metrics)==500
    report='''# 历史v0.2.0 NMF模型选择灵敏度与指标消融

复用已运行的 K=400/450/500/550/600、seed29、80%抽样实验，不重复训练。
本脚本检验 450–550 候选区间内选模偏好与六项指标留一，不是 TF-IDF/编码器表示消融。
500 是结合“约500”的业务偏好所得，不是各项指标一致支持的唯一最优值。
0.05 实际并列容差是在看到网格结果后记录的选择规则，未预注册；不能解释为统计显著性。
无容差、原惩罚权重时选择450；容差0.05时选择500。

500的抽样余弦轮廓系数为负（约-0.0866），最近簇心余弦约0.955，
说明关键词 NMF 类别在 BGE 空间仍有较大重叠，不能据此声称得到500个清晰分离的语义簇。
seed29验证ARI约0.734；80%训练样本验证ARI约0.603，后者达到30次迭代上限，
同时受样本变化和未充分收敛影响，不能将变化全部归因于采样。

## 选择结果

'''+result.to_markdown(index=False)+'''

K网格使用拟合时的训练W标签评估。v0.2.0下游改用所有切分统一model.transform，
当时标签改变1735篇训练论文；重建中心后专利646条、政策139条Top1改变。
上述是历史推断方式对照，不是v0.2.1实验，也不是重新训练或泛化准确率。
v0.2.1另修复NMF组件尺度依赖，相对v0.2.0生产标签改变30,359篇；
当前生效目录见 ../current_topic_catalog.csv，当前几何指标见 ../current_validation_metrics.csv。
历史网格目录仅用于记录选择过程，不据此声称新推断的最优K。
跨来源余弦的拒绝阈值、来源删除实验见热点仓库 assets/nmf500/experiments。
'''
    (out/'REPORT.md').write_text(report)
    (out/'PROTOCOL.json').write_text(json.dumps(dict(retrained=False,post_hoc=True,
        eligible_k=[450,500,550],penalties=[0.,.05,.15,.30],tolerances=[0.,.01,.02,.05,.10],
        metric_ablation=list(METRICS),does_not_measure_expert_accuracy=True),indent=2)+'\n')
    print(result.to_string(index=False))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,default=REPO/'assets/nmf500')
    p.add_argument('--output',type=Path,default=REPO/'assets/nmf500/experiments')
    args=p.parse_args()
    run(args.input,args.output)
