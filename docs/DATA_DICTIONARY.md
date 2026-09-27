# 当前数据字段

当前结果目录为assets/full_nmf500。

|文件|内容|
|---|---|
|topic_catalog.csv|500个topic_id、F格式category_id、name、top_keywords、论文／专利／政策数量、centroid_papers及审核状态|
|coverage.csv|source、input_records、assigned_records、unassigned_records|
|topic_assignment_quality.csv|相对Top1贡献、中位贡献差距、小差距比例|
|SUMMARY.json|数据范围、模型及中心哈希、训练与推断完整性|
|TRAINING_COMPLETE.json|训练参数、文档访问数、模型哈希|
|ASSIGNMENTS_MANIFEST.json|逐条分类分片SHA-256|
|VALIDATION.json|身份、覆盖、中心及跨来源匹配检查|

工作目录的assignments分片还保留row_id、doc_id、source、date、topic_id、category_id、assignment_status、assignment_method、nmf_relative_top1、nmf_relative_margin、Top3主题及cosine、top1_top2_margin、needs_review。

topic_id=-1为未分配；缺失分数不是0概率。Top1候选仍需语义核验。逐条Parquet与向量不随Git分发。
