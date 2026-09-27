# 项目结构与逐文件用途

## 从哪里开始

当前计算入口是 `pipelines/full_nmf/`，当前成果仅在 `assets/full_nmf500/`。`tests/fixtures/` 是固定回归输入，不是另一套待选用成果。共享模块和兼容实现因当前调用或测试需要而保留，不应直接替代全量入口。

阅读 [当前报告](../assets/full_nmf500/REPORT.md)、[方法](METHOD.md) 和 [复现步骤](REPRODUCING.md)。下面逐项列出全部 Git 管理的文件及目录，不用省略号隐藏文件。

## 完整结构图

```text
energy-topic-identification/  # 当前发布源码与紧凑成果
├── .github/  # 远端自动化配置
│   └── workflows/  # 持续集成工作流
│       └── nmf.yml  # 自动安装依赖并运行测试和校验
├── assets/  # 发布用的紧凑结果；不是原始语料
│   └── full_nmf500/  # 当前全量 500 主题流程或成果
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
├── docs/  # 方法、数据、复现与目录说明
│   ├── CORE_FILES.md  # 核心文件与外部大文件边界
│   ├── DATA_DICTIONARY.md  # 字段解释
│   ├── FULL_EXPERIMENTS.md  # 实验设计和解释限制
│   ├── FULL_NMF.md  # 全量主题流程说明
│   ├── METHOD.md  # 当前算法与适用边界
│   ├── PROJECT_STRUCTURE.md  # 本文件：全部受版本管理文件的用途索引
│   ├── REPRODUCING.md  # 环境、输入和复现步骤
│   └── RESULTS.md  # 结果说明
├── pipelines/  # 计算与复现入口
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
│   ├── keyword_nmf/  # 关键词矩阵与 NMF 共享组件及兼容回归
│   │   └── src/  # 可导入的算法模块
│   │       ├── components.py  # 可复用主题模型、指标和分类组件；关键词组件被当前全量流程直接调用
│   │       ├── run_pipeline.py  # 关键词矩阵构建、NMF 拟合和回归所需辅助函数
│   │       └── selection_experiments.py  # 固定回归指标的权重与选择敏感性检查，不是当前成果报告
│   └── topic_modeling/  # 主题组件兼容回归代码；不是全量生产入口
│       └── src/  # 可导入的算法模块
│           ├── candidate_common.py  # 兼容候选模型的路径、主题数和随机种子配置
│           ├── components.py  # 可复用主题模型、指标和分类组件；关键词组件被当前全量流程直接调用
│           ├── experiment_components.py  # 重用逐文档词频缓存的主题模型组件
│           ├── lexical.py  # 中英文分词与词项分析器
│           ├── topic_common.py  # 兼容主题流程的路径、文本和校验工具
│           ├── train_baseline.py  # 兼容主题训练与流式计数实现，供组件回归使用
│           └── train_candidates.py  # 兼容候选主题模型训练实现，非当前生产入口
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
│   ├── test_readable_report.py  # 回归测试：readable / report
│   └── test_topic_components.py  # 回归测试：topic / components
├── tools/  # 发布校验、清单及维护工具
│   ├── check_current_release.py  # 校验核心代码、成果指纹和文档链接
│   ├── project_structure.py  # 重建本结构图及逐文件用途
│   ├── update_release_manifest.py  # 更新发布文件指纹
│   └── validate_release.py  # 发布完整性校验入口
├── .gitignore  # 排除缓存、本地大数据和运行输出
├── README.md  # 项目入口：当前方法、结果及运行说明
├── requirements-full-nmf.txt  # 运行/测试依赖版本约束（用途由文件后缀区分）
├── requirements-nmf500.txt  # 运行/测试依赖版本约束（用途由文件后缀区分）
├── requirements-pipeline.txt  # 运行/测试依赖版本约束（用途由文件后缀区分）
├── requirements-topic-modeling.txt  # 运行/测试依赖版本约束（用途由文件后缀区分）
└── requirements.txt  # 运行/测试依赖版本约束（用途由文件后缀区分）
```

## 不随仓库发布的本地内容

`work/`、`outputs/` 或 `results/` 中的全量运行目录保存训练权重、向量、逐条分类、数据库和日志；原始文献及编码器权重也属于外部运行输入。这些文件体量大，不是本结构图漏列的源码，具体输入位置与生成步骤见复现说明。删除仓库中的旧发布快照不会删除这些运行数据。

## 维护本图

新增、移动或删除文件后运行 `python tools/project_structure.py`。只扫描 Git 可见文件，不扫描原始语料；发布前还应运行核心文件校验。每个文件名后为其作用；测试数据不可用于宣称当前模型效果。
