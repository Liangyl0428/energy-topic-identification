"""从全量训练与分类诊断记录生成中文报告。"""
from pathlib import Path
import argparse
import json
import pandas as pd


def table(headers,rows):
    return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+''.join('| '+' | '.join(map(str,row))+' |\n' for row in rows)


def render(folder):
    folder=Path(folder);q=json.loads((folder/'QUALITY_DIAGNOSTICS.json').read_text());t=json.loads((folder/'TRAINING_COMPLETE.json').read_text());c=pd.read_csv(folder/'coverage.csv')
    text='# 全量主题识别：方法、覆盖与质量诊断\n\n## 结论\n\n全量冻结论文均进入处理流程；有可用关键词的论文参与 500 主题 NMF 训练并获得类别。专利和政策不参与论文 NMF 拟合，而是与论文主题中心进行语义向量匹配。缺失有效输入的记录保留为未分类，不用假标签补齐。\n\n'
    text+=table(['来源','输入记录','已分类','未分类'],[({'paper':'论文','patent':'专利','policy':'政策'}[r.source],f'{r.input_records:,}',f'{r.assigned_records:,}',f'{r.unassigned_records:,}') for r in c.itertuples()])
    text+='\n## 当前方法\n\n全量论文关键词形成词表与 TF-IDF 输入，MiniBatchNMF 完成固定轮数训练。计算每篇论文的主题贡献，选最高者作为类别。同一主题内有效论文 embedding 求均值并归一化，得到主题中心；专利和政策的归一化 embedding 与 500 个中心计算余弦相似度，取最高者为候选类别，同时保留 Top3 和相似度差距。全部语义向量使用同一 BGE-M3 模型，避免向量空间混用。\n\n## 训练诊断\n\n'
    text+=f"有效论文 {t['configuration']['fit_population']:,} 篇，完整训练 {t['configuration']['epochs']} 轮，累计访问 {t['paper_visits']:,} 篇次。\n\n"
    text+=table(['轮次','固定诊断输入相对重构误差','累计访问篇次'],[(r['epoch'],f"{r['diagnostic_relative_error']:.6f}",f"{r['paper_visits']:,}") for r in t['history']])
    text+='\n误差来自固定前 1,024 行诊断输入，不是全量重构误差、独立测试集或语义准确率。误差降低说明诊断输入拟合改善；固定轮数不保证全局最优。\n\n## 类别规模与边界\n\n'
    text+=table(['诊断项','结果'],[['使用的主题数',q['active_topics']],['最大主题论文量',f"{q['largest_topic_papers']:,}"],['最大主题占已分类论文比例',f"{q['largest_topic_share']:.2%}"],['最近中心余弦中位数',f"{q['centroid_nearest_cosine_median']:.4f}"],['最近中心余弦最大值',f"{q['centroid_nearest_cosine_max']:.4f}"],['最近中心余弦超过0.95的主题数',q['topics_with_nearest_cosine_over_095']]])
    text+='\n主题全部被使用且没有单一超大主题，不代表划分正确。较高的中心相似度提示嵌入空间明显重叠，Top1 仍可能边界模糊。余弦不是概率，分类差距也未经过准确率校准。\n\n## 本报告的边界\n\n没有专家标注准确率或独立留出集语义评估，也没有重训不同主题数的消融实验，不能声称 500 是最优主题数。本报告只解释当前已保存的训练、覆盖和几何诊断，不混入其他方法的结果。\n\n明细：[主题目录](topic_catalog.csv)、[逐主题诊断](topic_assignment_quality.csv)、[覆盖](coverage.csv)、[训练记录](TRAINING_COMPLETE.json)、[几何诊断](QUALITY_DIAGNOSTICS.json)、[完整性校验](VALIDATION.json)。模型、原始语料和逐条向量保留在本地，不随 Git 分发，见 [复现说明](../../docs/REPRODUCING.md)。\n'
    (folder/'REPORT.md').write_text(text)
    return text


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    render(parser.parse_args().input)
