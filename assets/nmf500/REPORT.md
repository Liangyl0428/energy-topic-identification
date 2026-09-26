# v0.2.1 主题分类重算

对142,000篇冻结论文统一执行固定H推断，使用 W[j] × ||H[j]||₂ 的贡献比较，
消除等价NMF分解中主题尺度对Top1的影响。保留500个组件编号，实际499个有论文。
与v0.2.0生产标签相比改变30,359篇（21.38%）。

当前验证集抽样轮廓系数-0.0797，
BGE最近中心与关键词标签Top1一致率35.67%，
ARI为0.1783。这些是几何诊断，不是人工分类准确率；
主题仍重叠明显，500只作为冻结业务粒度，不能声称自然分离或选模最优。

current_topic_catalog.csv 为当前目录；current_validation_metrics.csv 是修正后的独立验证指标；
assignment_changes_v021.csv 和 topic_assignment_quality.csv 记录标签变动及歧义。
所有专利/政策均为待语义复核候选，论文相似度过滤不保证跨来源分类正确。

candidate_metrics.csv、selection.json、stability_metrics.csv及experiments/保留历史选模实验；
它们使用旧fit-W标签，不是v0.2.1分类指标。旧报告见V020_MODEL_REPORT.md。
严格审查与复现边界见 ../../docs/V0.2.1_AUDIT.md。
