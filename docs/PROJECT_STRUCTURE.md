# 项目结构与逐文件用途

## 从哪里开始

模块基础计算入口在 `pipelines/full_nmf/`；F500 与 P1/P2 模块成果在 `assets/full_nmf500/`。主题识别仓库另有关键词及多主题流水线，联合手册、预览和紧凑交付在其 `platform/`。不同版本的范围和入口以 README 为准。`tests/fixtures/` 是固定回归输入，不是另一套待选用成果。共享模块和兼容实现因当前调用或测试需要而保留，不应直接替代全量入口。

阅读 [当前报告](../assets/full_nmf500/REPORT.md)、[方法](METHOD.md) 和 [复现步骤](REPRODUCING.md)。下面逐项列出全部 Git 管理的文件及目录，不用省略号隐藏文件。

## 完整结构图

```text
energy-topic-identification/  # 当前发布源码与紧凑成果
├── .github/  # 远端自动化配置
│   └── workflows/  # 持续集成工作流
│       └── nmf.yml  # 自动安装依赖并运行测试和校验
├── assets/  # 发布用的紧凑结果；不是原始语料
│   └── full_nmf500/  # 当前全量 500 主题流程或成果
│       ├── p1/  # F500业务解释与证据接口
│       │   ├── INPUTS.json  # 结果/配置：INPUTS
│       │   ├── business_taxonomy.json  # 结果/配置：business / taxonomy
│       │   ├── reviewed_memberships.csv  # 结果/配置：reviewed / memberships
│       │   ├── reviewed_memberships.json  # 结果/配置：reviewed / memberships
│       │   ├── scope_evidence.csv  # 结果/配置：scope / evidence
│       │   ├── scope_evidence.json  # 结果/配置：scope / evidence
│       │   ├── scope_review_queue.csv  # 结果/配置：scope / review / queue
│       │   ├── scope_review_queue.json  # 结果/配置：scope / review / queue
│       │   ├── scope_reviews.csv  # 结果/配置：scope / reviews
│       │   ├── scope_reviews.json  # 结果/配置：scope / reviews
│       │   ├── topic_business_cards.csv  # 结果/配置：topic / business / cards
│       │   ├── topic_business_cards.json  # 结果/配置：topic / business / cards
│       │   ├── topic_business_mappings.csv  # 结果/配置：topic / business / mappings
│       │   └── topic_business_mappings.json  # 结果/配置：topic / business / mappings
│       ├── p2/  # 51个题名业务主题及对应趋势/对象解读
│       │   ├── business_taxonomy.csv  # 结果/配置：business / taxonomy
│       │   ├── business_taxonomy.json  # 结果/配置：business / taxonomy
│       │   ├── evidence_samples.csv  # 结果/配置：evidence / samples
│       │   ├── evidence_samples.json  # 结果/配置：evidence / samples
│       │   ├── f_business_membership_counts.csv  # 结果/配置：f / business / membership / counts
│       │   ├── f_topic_bridge.csv  # 结果/配置：f / topic / bridge
│       │   └── f_topic_bridge.json  # 结果/配置：f / topic / bridge
│       ├── ASSIGNMENTS_MANIFEST.json  # 本地逐条分类分片指纹
│       ├── ENCODING_COMPLETE.json  # 全量编码完成记录
│       ├── INFERENCE_COMPLETE.json  # 全量论文推断完成记录
│       ├── MANIFEST.json  # 当前发布结果的 SHA-256 指纹
│       ├── POSTPROCESS_DELIVERY.json  # 三仓库交付及实验绑定记录
│       ├── QUALITY_DIAGNOSTICS.json  # 类别规模和中心重叠诊断，非准确率
│       ├── REPORT.md  # 面向读者的结果报告
│       ├── SUMMARY.json  # 机器可读统计摘要
│       ├── TRAINING_COMPLETE.json  # 训练配置、轮次诊断及模型指纹
│       ├── VALIDATION.json  # 数据完整性检查结果
│       ├── VOCABULARY_COMPLETE.json  # 词表拟合范围与参数
│       ├── coverage.csv  # 按来源统计输入、已分类与未分类数量
│       ├── topic_assignment_quality.csv  # 逐主题分类差距与几何诊断
│       └── topic_catalog.csv  # 主题编号、关键词与规模
├── config/  # 目录：config
│   └── runtime_paths.json  # 结果/配置：runtime / paths
├── data/  # 有边界的成熟度证据输入，必须保留
│   ├── business_review/  # 目录：business / review
│   │   ├── SOURCE_SNAPSHOT.json  # 结果/配置：SOURCE / SNAPSHOT
│   │   ├── documents.json  # 结果/配置：documents
│   │   ├── scope_decisions.json  # 结果/配置：scope / decisions
│   │   ├── taxonomy.json  # 结果/配置：taxonomy
│   │   └── topic_definitions.json  # 结果/配置：topic / definitions
│   └── business_v2/  # 目录：business / v2
│       └── development_title_review.json  # 结果/配置：development / title / review
├── docs/  # 方法、数据、复现与目录说明
│   ├── CORE_FILES.md  # 核心文件与外部大文件边界
│   ├── DATA_DICTIONARY.md  # 字段解释
│   ├── FULL_EXPERIMENTS.md  # 实验设计和解释限制
│   ├── FULL_NMF.md  # 全量主题流程说明
│   ├── METHOD.md  # 当前算法与适用边界
│   ├── PLATFORM_INTEGRATION.md  # 结果/配置：PLATFORM / INTEGRATION
│   ├── PROJECT_STRUCTURE.md  # 本文件：全部受版本管理文件的用途索引
│   ├── REPRODUCING.md  # 环境、输入和复现步骤
│   └── RESULTS.md  # 结果说明
├── pipelines/  # 计算与复现入口
│   ├── business/  # 目录：business
│   │   └── build.py  # 构建本阶段计算结果
│   ├── embedding/  # 向量编码与池化兼容组件
│   │   └── src/  # 可导入的算法模块
│   │       ├── download_encoder.py  # 下载固定修订的兼容编码器权重；不是当前 BGE-M3 下载入口
│   │       ├── embedding_common.py  # 兼容编码流程的路径、文本清洗和文件校验函数
│   │       ├── encode.py  # 批量文本向量编码
│   │       └── pool_encoder.py  # 为兼容 ONNX 编码器增加池化与归一化输出
│   ├── full_nmf/  # 当前全量主流程
│   │   ├── after_full.py  # 实验、校验和三仓库交付编排
│   │   ├── common.py  # 公共路径、配置和辅助函数
│   │   ├── encode.py  # 批量文本向量编码
│   │   ├── fast_nmf.py  # NMF 数值计算与批处理加速
│   │   ├── finalize.py  # 主题中心、跨来源分类与全量校验
│   │   ├── optimize_encoder.py  # 优化编码模型运行格式
│   │   ├── prepare.py  # 全量清洗、关键词统计与矩阵构建
│   │   ├── publish_local.py  # 将紧凑成果发布到仓库 assets
│   │   ├── report.py  # 生成人类可读结果报告
│   │   ├── resume_delivery.py  # 安全恢复未完成交付
│   │   ├── run.py  # 编排全量分类与下游计算
│   │   ├── status.py  # 读取阶段标记显示进度
│   │   └── train.py  # 全量 NMF 分批训练与论文推断
│   ├── keyword_dictionary/  # 第一轮关键词多标签分类
│   │   ├── build_dictionary.py  # 兼容回归辅助：build / dictionary；保留用于依赖链或测试
│   │   ├── classify.py  # 兼容回归辅助：classify；保留用于依赖链或测试
│   │   ├── common.py  # 公共路径、配置和辅助函数
│   │   ├── curation.py  # 兼容回归辅助：curation；保留用于依赖链或测试
│   │   ├── curation_additions.py  # 兼容回归辅助：curation / additions；保留用于依赖链或测试
│   │   ├── prepare.py  # 全量清洗、关键词统计与矩阵构建
│   │   ├── publish.py  # 兼容回归辅助：publish；保留用于依赖链或测试
│   │   ├── query.py  # 兼容回归辅助：query；保留用于依赖链或测试
│   │   ├── refine_rules.py  # 兼容回归辅助：refine / rules；保留用于依赖链或测试
│   │   ├── review.py  # 候选主题范围及语义审核应用
│   │   ├── samples.py  # 兼容回归辅助：samples；保留用于依赖链或测试
│   │   └── validate.py  # 固定回归输出的数据约束检查
│   ├── keyword_dictionary_full_review/  # 进行中的语境审核工具；尚非完成交付
│   │   ├── README.md  # 项目入口：当前方法、结果及运行说明
│   │   ├── check_progress.py  # 兼容回归辅助：check / progress；保留用于依赖链或测试
│   │   ├── common.py  # 公共路径、配置和辅助函数
│   │   ├── context_batches.py  # 兼容回归辅助：context / batches；保留用于依赖链或测试
│   │   ├── prepare_context.py  # 兼容回归辅助：prepare / context；保留用于依赖链或测试
│   │   ├── prepare_supplementary.py  # 兼容回归辅助：prepare / supplementary；保留用于依赖链或测试
│   │   ├── record_context_overrides.py  # 兼容回归辅助：record / context / overrides；保留用于依赖链或测试
│   │   ├── resolve_terms.py  # 兼容回归辅助：resolve / terms；保留用于依赖链或测试
│   │   └── review_batches.py  # 兼容回归辅助：review / batches；保留用于依赖链或测试
│   ├── keyword_dictionary_review_r2/  # 第二轮词典与逐篇触发审核
│   │   ├── audit_r2.py  # 兼容回归辅助：audit / r2；保留用于依赖链或测试
│   │   ├── build_dictionary.py  # 兼容回归辅助：build / dictionary；保留用于依赖链或测试
│   │   ├── classify.py  # 兼容回归辅助：classify；保留用于依赖链或测试
│   │   ├── common.py  # 公共路径、配置和辅助函数
│   │   ├── curation.py  # 兼容回归辅助：curation；保留用于依赖链或测试
│   │   ├── curation_additions.py  # 兼容回归辅助：curation / additions；保留用于依赖链或测试
│   │   ├── prepare.py  # 全量清洗、关键词统计与矩阵构建
│   │   ├── publish_r2.py  # 兼容回归辅助：publish / r2；保留用于依赖链或测试
│   │   ├── query.py  # 兼容回归辅助：query；保留用于依赖链或测试
│   │   ├── refine_rules.py  # 兼容回归辅助：refine / rules；保留用于依赖链或测试
│   │   ├── round2_review.py  # 兼容回归辅助：round2 / review；保留用于依赖链或测试
│   │   ├── samples_r2.py  # 兼容回归辅助：samples / r2；保留用于依赖链或测试
│   │   └── validate.py  # 固定回归输出的数据约束检查
│   ├── keyword_nmf/  # 关键词矩阵与 NMF 共享组件及兼容回归
│   │   └── src/  # 可导入的算法模块
│   │       ├── components.py  # 可复用主题模型、指标和分类组件；关键词组件被当前全量流程直接调用
│   │       ├── run_pipeline.py  # 关键词矩阵构建、NMF 拟合和回归所需辅助函数
│   │       └── selection_experiments.py  # 固定回归指标的权重与选择敏感性检查，不是当前成果报告
│   ├── multilabel_scope/  # K500多标签与能源范围审阅
│   │   ├── controlled/  # 从外部实验目录补齐的NMF依赖源码
│   │   │   ├── experiment.py  # 兼容回归辅助：experiment；保留用于依赖链或测试
│   │   │   └── fast_nmf.py  # NMF 数值计算与批处理加速
│   │   ├── apply_scope.py  # 兼容回归辅助：apply / scope；保留用于依赖链或测试
│   │   ├── check_preview.cjs  # 结果/配置：check / preview
│   │   ├── preview.html  # 结果/配置：preview
│   │   ├── publish.py  # 兼容回归辅助：publish；保留用于依赖链或测试
│   │   ├── query.py  # 兼容回归辅助：query；保留用于依赖链或测试
│   │   ├── review.py  # 候选主题范围及语义审核应用
│   │   ├── run.py  # 编排全量分类与下游计算
│   │   ├── transfer.py  # 兼容回归辅助：transfer；保留用于依赖链或测试
│   │   └── validate.py  # 固定回归输出的数据约束检查
│   └── topic_modeling/  # 主题组件兼容回归代码；不是全量生产入口
│       └── src/  # 可导入的算法模块
│           ├── candidate_common.py  # 兼容候选模型的路径、主题数和随机种子配置
│           ├── components.py  # 可复用主题模型、指标和分类组件；关键词组件被当前全量流程直接调用
│           ├── experiment_components.py  # 重用逐文档词频缓存的主题模型组件
│           ├── lexical.py  # 中英文分词与词项分析器
│           ├── topic_common.py  # 兼容主题流程的路径、文本和校验工具
│           ├── train_baseline.py  # 兼容主题训练与流式计数实现，供组件回归使用
│           └── train_candidates.py  # 兼容候选主题模型训练实现，非当前生产入口
├── platform/  # 跨模块业务手册、接口、预览及版本化紧凑交付
│   ├── acceptance/  # 目录：acceptance
│   │   └── nmf500_multilabel_20261019/  # 目录：nmf500 / multilabel / 20261019
│   │       ├── ACCEPTANCE.json  # 结果/配置：ACCEPTANCE
│   │       ├── AUDIT_CHECKS.json  # 结果/配置：AUDIT / CHECKS
│   │       ├── K500验收报告.html  # 结果/配置：K500验收报告
│   │       ├── K500验收问题与抽样.xlsx  # 结果/配置：K500验收问题与抽样
│   │       ├── MANIFEST.json  # 当前发布结果的 SHA-256 指纹
│   │       ├── REPORT_VALIDATION.json  # 结果/配置：REPORT / VALIDATION
│   │       ├── acceptance_checklist.csv  # 结果/配置：acceptance / checklist
│   │       ├── cross_review.csv  # 结果/配置：cross / review
│   │       ├── issues.csv  # 结果/配置：issues
│   │       ├── keyword_trace.csv  # 结果/配置：keyword / trace
│   │       ├── near_duplicate_components.csv  # 结果/配置：near / duplicate / components
│   │       ├── paper_review.csv  # 结果/配置：paper / review
│   │       ├── topic_count_distribution.csv  # 结果/配置：topic / count / distribution
│   │       └── topic_review.csv  # 结果/配置：topic / review
│   ├── assets/  # 发布用的紧凑结果；不是原始语料
│   │   ├── keyword_dictionary_multilabel/  # 目录：keyword / dictionary / multilabel
│   │   │   ├── BROWSER_CHECK.json  # 结果/配置：BROWSER / CHECK
│   │   │   ├── CLASSIFIED.json  # 结果/配置：CLASSIFIED
│   │   │   ├── DELIVERY_CHECK.json  # 结果/配置：DELIVERY / CHECK
│   │   │   ├── DICTIONARY_COMPLETE.json  # 结果/配置：DICTIONARY / COMPLETE
│   │   │   ├── PREPARED.json  # 结果/配置：PREPARED
│   │   │   ├── RELEASE.json  # 结果/配置：RELEASE
│   │   │   ├── REVIEW.json  # 结果/配置：REVIEW
│   │   │   ├── SOURCE_CHECK.json  # 结果/配置：SOURCE / CHECK
│   │   │   ├── VALIDATION.json  # 数据完整性检查结果
│   │   │   ├── all_raw_keywords.csv  # 结果/配置：all / raw / keywords
│   │   │   ├── assignment_status_counts.csv  # 结果/配置：assignment / status / counts
│   │   │   ├── keyword_aliases.csv  # 结果/配置：keyword / aliases
│   │   │   ├── keyword_dictionary.csv  # 结果/配置：keyword / dictionary
│   │   │   ├── keywords_per_paper.csv  # 结果/配置：keywords / per / paper
│   │   │   ├── new_topic_samples.parquet  # 结果/配置：new / topic / samples
│   │   │   ├── platform_data.json  # 结果/配置：platform / data
│   │   │   ├── previous_audit_regression.parquet  # 结果/配置：previous / audit / regression
│   │   │   ├── review_metadata.parquet  # 结果/配置：review / metadata
│   │   │   ├── rule_refinement_regression.csv  # 结果/配置：rule / refinement / regression
│   │   │   ├── sample_all_keywords.csv  # 结果/配置：sample / all / keywords
│   │   │   ├── sample_review.csv  # 结果/配置：sample / review
│   │   │   ├── topic_catalog.csv  # 主题编号、关键词与规模
│   │   │   ├── topic_counts.csv  # 结果/配置：topic / counts
│   │   │   ├── topic_definitions.json  # 结果/配置：topic / definitions
│   │   │   ├── topics_per_paper.csv  # 结果/配置：topics / per / paper
│   │   │   ├── unobserved_candidate_terms.csv  # 结果/配置：unobserved / candidate / terms
│   │   │   ├── 使用与接入说明.html  # 结果/配置：使用与接入说明
│   │   │   ├── 关键词主题浏览.html  # 结果/配置：关键词主题浏览
│   │   │   ├── 关键词词典与多主题审阅.xlsx  # 结果/配置：关键词词典与多主题审阅
│   │   │   ├── 待审核关键词.csv  # 结果/配置：待审核关键词
│   │   │   └── 有效关键词主题映射.csv  # 结果/配置：有效关键词主题映射
│   │   ├── keyword_dictionary_semantic_review_r2/  # 目录：keyword / dictionary / semantic / review / r2
│   │   │   ├── CLASSIFIED.json  # 结果/配置：CLASSIFIED
│   │   │   ├── DICTIONARY_COMPLETE.json  # 结果/配置：DICTIONARY / COMPLETE
│   │   │   ├── INPUT_REUSE.json  # 结果/配置：INPUT / REUSE
│   │   │   ├── PREPARED.json  # 结果/配置：PREPARED
│   │   │   ├── RELEASE.json  # 结果/配置：RELEASE
│   │   │   ├── REVIEW.json  # 结果/配置：REVIEW
│   │   │   ├── SAMPLES.json  # 结果/配置：SAMPLES
│   │   │   ├── SEMANTIC_REVIEW_CHECK.json  # 结果/配置：SEMANTIC / REVIEW / CHECK
│   │   │   ├── VALIDATION.json  # 数据完整性检查结果
│   │   │   ├── all_raw_keywords.csv  # 结果/配置：all / raw / keywords
│   │   │   ├── assignment_status_counts.csv  # 结果/配置：assignment / status / counts
│   │   │   ├── document_keyword_review.csv  # 结果/配置：document / keyword / review
│   │   │   ├── fresh_topic_samples.parquet  # 结果/配置：fresh / topic / samples
│   │   │   ├── keyword_aliases.csv  # 结果/配置：keyword / aliases
│   │   │   ├── keyword_dictionary.csv  # 结果/配置：keyword / dictionary
│   │   │   ├── keywords_per_paper.csv  # 结果/配置：keywords / per / paper
│   │   │   ├── missing_keyword_suggestions.csv  # 结果/配置：missing / keyword / suggestions
│   │   │   ├── new_direct_term_samples.parquet  # 结果/配置：new / direct / term / samples
│   │   │   ├── paper_semantic_review.csv  # 结果/配置：paper / semantic / review
│   │   │   ├── platform_data.json  # 结果/配置：platform / data
│   │   │   ├── previous_semantic_issues.csv  # 结果/配置：previous / semantic / issues
│   │   │   ├── previous_semantic_review_regression.parquet  # 结果/配置：previous / semantic / review / regression
│   │   │   ├── review_metadata.parquet  # 结果/配置：review / metadata
│   │   │   ├── review_sample_hashes.json  # 结果/配置：review / sample / hashes
│   │   │   ├── reviewed_examples.parquet  # 结果/配置：reviewed / examples
│   │   │   ├── sample_source_keywords.csv  # 结果/配置：sample / source / keywords
│   │   │   ├── term_semantic_review.csv  # 结果/配置：term / semantic / review
│   │   │   ├── topic_catalog.csv  # 主题编号、关键词与规模
│   │   │   ├── topic_count_comparison.csv  # 结果/配置：topic / count / comparison
│   │   │   ├── topic_counts.csv  # 结果/配置：topic / counts
│   │   │   ├── topic_definitions.json  # 结果/配置：topic / definitions
│   │   │   ├── topics_per_paper.csv  # 结果/配置：topics / per / paper
│   │   │   ├── unobserved_candidate_terms.csv  # 结果/配置：unobserved / candidate / terms
│   │   │   ├── 使用与接入说明.html  # 结果/配置：使用与接入说明
│   │   │   ├── 关键词主题浏览.html  # 结果/配置：关键词主题浏览
│   │   │   ├── 待审核关键词.csv  # 结果/配置：待审核关键词
│   │   │   ├── 有效关键词主题映射.csv  # 结果/配置：有效关键词主题映射
│   │   │   └── 第二轮语义审核.xlsx  # 结果/配置：第二轮语义审核
│   │   ├── nmf500_multilabel_scope/  # 目录：nmf500 / multilabel / scope
│   │   │   ├── BROWSER_VALIDATION.json  # 结果/配置：BROWSER / VALIDATION
│   │   │   ├── K500多主题归属与范围审核.xlsx  # 结果/配置：K500多主题归属与范围审核
│   │   │   ├── PROTOCOL.json  # 实验参数、范围、限制与输入指纹
│   │   │   ├── RELEASE.json  # 结果/配置：RELEASE
│   │   │   ├── VALIDATION.json  # 数据完整性检查结果
│   │   │   ├── assignment_status_counts.csv  # 结果/配置：assignment / status / counts
│   │   │   ├── cross_source_case_review.csv  # 结果/配置：cross / source / case / review
│   │   │   ├── platform_data.json  # 结果/配置：platform / data
│   │   │   ├── relation_review_overrides.csv  # 结果/配置：relation / review / overrides
│   │   │   ├── threshold_scope_sensitivity.csv  # 结果/配置：threshold / scope / sensitivity
│   │   │   ├── topic_catalog.csv  # 主题编号、关键词与规模
│   │   │   ├── topic_counts_by_source_threshold.csv  # 结果/配置：topic / counts / by / source / threshold
│   │   │   ├── topic_display_labels.csv  # 结果/配置：topic / display / labels
│   │   │   ├── topic_scope_decisions.csv  # 结果/配置：topic / scope / decisions
│   │   │   └── 使用与接入说明.html  # 结果/配置：使用与接入说明
│   │   ├── p1/  # F500业务解释与证据接口
│   │   │   ├── BUILD.json  # 结果/配置：BUILD
│   │   │   ├── P1_review.xlsx  # 结果/配置：P1 / review
│   │   │   ├── SUMMARY.json  # 机器可读统计摘要
│   │   │   └── platform_examples.json  # 结果/配置：platform / examples
│   │   └── p2/  # 51个题名业务主题及对应趋势/对象解读
│   │       ├── SUMMARY.json  # 机器可读统计摘要
│   │       ├── platform_data.json  # 结果/配置：platform / data
│   │       └── 业务主题与决策解读.xlsx  # 结果/配置：业务主题与决策解读
│   ├── config/  # 目录：config
│   │   ├── keyword_dictionary_multilabel.json  # 结果/配置：keyword / dictionary / multilabel
│   │   ├── keyword_dictionary_semantic_review_r2.json  # 结果/配置：keyword / dictionary / semantic / review / r2
│   │   ├── nmf500_multilabel_release.json  # 结果/配置：nmf500 / multilabel / release
│   │   └── runtime_paths.json  # 结果/配置：runtime / paths
│   ├── docs/  # 方法、数据、复现与目录说明
│   │   ├── P0修复验收.md  # 结果/配置：P0修复验收
│   │   ├── P1修复验收.md  # 结果/配置：P1修复验收
│   │   ├── P2业务主题与决策使用手册.md  # 结果/配置：P2业务主题与决策使用手册
│   │   ├── P2接口与复现说明.md  # 结果/配置：P2接口与复现说明
│   │   ├── 平台业务与使用说明.md  # 结果/配置：平台业务与使用说明
│   │   ├── 数据与指标字典.md  # 结果/配置：数据与指标字典
│   │   ├── 模块接口与展示规范.md  # 结果/配置：模块接口与展示规范
│   │   └── 运行配置与输入清单.md  # 结果/配置：运行配置与输入清单
│   ├── preview/  # 目录：preview
│   │   ├── index.html  # 结果/配置：index
│   │   └── nmf500_multilabel.html  # 结果/配置：nmf500 / multilabel
│   ├── provenance/  # 文件指纹与审计元数据
│   │   ├── INPUT_MANIFEST.json  # 结果/配置：INPUT / MANIFEST
│   │   ├── P0_FILES.json  # 结果/配置：P0 / FILES
│   │   ├── P0_TESTS.xml  # 结果/配置：P0 / TESTS
│   │   ├── P0_TEST_SUMMARY.json  # 结果/配置：P0 / TEST / SUMMARY
│   │   ├── P0_VALIDATION.json  # 结果/配置：P0 / VALIDATION
│   │   ├── P1_BASELINE.json  # 结果/配置：P1 / BASELINE
│   │   ├── P1_FILES.json  # 结果/配置：P1 / FILES
│   │   ├── P1_REBUILD.json  # 结果/配置：P1 / REBUILD
│   │   ├── P1_TESTS.xml  # 结果/配置：P1 / TESTS
│   │   ├── P1_VALIDATION.json  # 结果/配置：P1 / VALIDATION
│   │   ├── P2_BROWSER.json  # 结果/配置：P2 / BROWSER
│   │   ├── P2_FILES.json  # 结果/配置：P2 / FILES
│   │   ├── P2_PREVIEW_DESKTOP.png  # 结果/配置：P2 / PREVIEW / DESKTOP
│   │   ├── P2_PREVIEW_MOBILE.png  # 结果/配置：P2 / PREVIEW / MOBILE
│   │   ├── P2_TESTS.xml  # 结果/配置：P2 / TESTS
│   │   ├── P2_VALIDATION.json  # 结果/配置：P2 / VALIDATION
│   │   └── p0_maturity_plot_check.png  # 结果/配置：p0 / maturity / plot / check
│   ├── tests/  # 自动化测试及固定输入
│   │   ├── test_p1_delivery.py  # 回归测试：p1 / delivery
│   │   ├── test_p2_delivery.py  # 回归测试：p2 / delivery
│   │   └── test_runtime_config.py  # 回归测试：runtime / config
│   ├── tools/  # 发布校验、清单及维护工具
│   │   ├── build_p1.py  # 兼容回归辅助：build / p1；保留用于依赖链或测试
│   │   ├── build_p2.py  # 兼容回归辅助：build / p2；保留用于依赖链或测试
│   │   ├── build_p2_preview.py  # 兼容回归辅助：build / p2 / preview；保留用于依赖链或测试
│   │   ├── check_inputs.py  # 兼容回归辅助：check / inputs；保留用于依赖链或测试
│   │   ├── check_p2_preview.cjs  # 结果/配置：check / p2 / preview
│   │   ├── p2_preview.html  # 结果/配置：p2 / preview
│   │   ├── p2_taxonomy.py  # 兼容回归辅助：p2 / taxonomy；保留用于依赖链或测试
│   │   ├── refresh_p0_manifests.py  # 兼容回归辅助：refresh / p0 / manifests；保留用于依赖链或测试
│   │   ├── refresh_p1_manifests.py  # 兼容回归辅助：refresh / p1 / manifests；保留用于依赖链或测试
│   │   ├── validate_p0.py  # 兼容回归辅助：validate / p0；保留用于依赖链或测试
│   │   ├── validate_p1.py  # 兼容回归辅助：validate / p1；保留用于依赖链或测试
│   │   └── validate_p2.py  # 兼容回归辅助：validate / p2；保留用于依赖链或测试
│   ├── EXTERNAL_FILES.json  # 未提交Git的完整逐篇分片路径、大小和SHA256
│   ├── README.md  # 项目入口：当前方法、结果及运行说明
│   ├── p1_common.py  # 业务导出的类型与版本辅助函数
│   └── runtime_config.py  # 可搬迁的显式输入路径解析
├── provenance/  # 文件指纹与审计元数据
│   ├── CORE_FILES.json  # 当前核心文件完整性清单
│   └── SHA256SUMS.json  # 发布或回归审计记录：SHA256SUMS
├── tests/  # 自动化测试及固定输入
│   ├── fixtures/  # 仅用于兼容回归，不代表当前成果
│   │   └── nmf500/  # 固定回归目录；不作为当前结果使用
│   │       ├── experiments/  # 固定回归目录；不作为当前结果使用
│   │       │   ├── PROTOCOL.json  # 固定回归输入/期望值；不作为当前结果使用：实验参数、范围、限制与输入指纹
│   │       │   └── selection_sensitivity.csv  # 固定回归输入/期望值；不作为当前结果使用
│   │       ├── CURRENT_INFERENCE_AUDIT.json  # 固定回归输入/期望值；不作为当前结果使用
│   │       ├── MANIFEST.json  # 固定回归输入/期望值；不作为当前结果使用：当前发布结果的 SHA-256 指纹
│   │       ├── assignment_changes_v021.csv  # 固定回归输入/期望值；不作为当前结果使用
│   │       ├── candidate_metrics.csv  # 固定回归输入/期望值；不作为当前结果使用
│   │       ├── current_confidence_thresholds.json  # 固定回归输入/期望值；不作为当前结果使用
│   │       ├── current_topic_catalog.csv  # 固定回归输入/期望值；不作为当前结果使用
│   │       ├── current_validation_metrics.csv  # 固定回归输入/期望值；不作为当前结果使用
│   │       ├── selection.json  # 固定回归输入/期望值；不作为当前结果使用
│   │       ├── stability_metrics.csv  # 固定回归输入/期望值；不作为当前结果使用
│   │       ├── topic_assignment_quality.csv  # 固定回归输入/期望值；不作为当前结果使用：逐主题分类差距与几何诊断
│   │       ├── transfer_changes_v021.csv  # 固定回归输入/期望值；不作为当前结果使用
│   │       ├── transfer_recalibration_audit.csv  # 固定回归输入/期望值；不作为当前结果使用
│   │       └── uniform_inference_changes.csv  # 固定回归输入/期望值；不作为当前结果使用
│   ├── test_current_release.py  # 回归测试：current / release
│   ├── test_embedding_pool.py  # 回归测试：embedding / pool
│   ├── test_full_delivery.py  # 回归测试：full / delivery
│   ├── test_full_nmf.py  # 回归测试：full / nmf
│   ├── test_keyword_nmf.py  # 回归测试：keyword / nmf
│   ├── test_multilabel_scope.py  # 回归测试：multilabel / scope
│   ├── test_portable_runtime.py  # 回归测试：portable / runtime
│   ├── test_readable_report.py  # 回归测试：readable / report
│   ├── test_repository_packaging.py  # 回归测试：repository / packaging
│   └── test_topic_components.py  # 回归测试：topic / components
├── tools/  # 发布校验、清单及维护工具
│   ├── assemble_platform.py  # 把三个仓库组装成新的平台联调目录
│   ├── check_current_release.py  # 校验核心代码、成果指纹和文档链接
│   ├── check_platform_assets.py  # 核验紧凑交付及外部逐篇分片指纹
│   ├── project_structure.py  # 重建本结构图及逐文件用途
│   ├── update_release_manifest.py  # 更新发布文件指纹
│   └── validate_release.py  # 发布完整性校验入口
├── .gitattributes  # Git 文本与二进制属性
├── .gitignore  # 排除缓存、本地大数据和运行输出
├── README.md  # 项目入口：当前方法、结果及运行说明
├── p1_common.py  # 业务导出的类型与版本辅助函数
├── requirements-full-nmf.txt  # 运行/测试依赖版本约束（用途由文件后缀区分）
├── requirements-nmf500.txt  # 运行/测试依赖版本约束（用途由文件后缀区分）
├── requirements-pipeline.txt  # 运行/测试依赖版本约束（用途由文件后缀区分）
├── requirements-topic-modeling.txt  # 运行/测试依赖版本约束（用途由文件后缀区分）
├── requirements.txt  # 运行/测试依赖版本约束（用途由文件后缀区分）
└── runtime_config.py  # 可搬迁的显式输入路径解析
```

## 不随仓库发布的本地内容

`work/`、`outputs/` 或 `results/` 中的全量运行目录保存训练权重、向量、逐条分类、数据库和日志；原始文献及编码器权重也属于外部运行输入。这些文件体量大，不是本结构图漏列的源码，具体输入位置与生成步骤见复现说明。删除仓库中的旧发布快照不会删除这些运行数据。

## 维护本图

新增、移动或删除文件后运行 `python tools/project_structure.py`。只扫描 Git 可见文件，不扫描原始语料；发布前还应运行核心文件校验。每个文件名后为其作用；测试数据不可用于宣称当前模型效果。
