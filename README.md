# 能源电力主题识别

提供能源论文主题分类、关键词证据和业务主题定义。最新已交付版本是 **72 主题关键词词典第二轮语义审核版**；原 F500、RBK500 和 P2 保留为独立版本，不能互换编号或沿用彼此的统计。

| 版本 | 内容与状态 | 入口 |
|---|---|---|
| KWD 第二轮 | 4,831,088 篇论文，72 个主题；1,807,502 篇命中，4,694,128 条多标签关系；语义审核未完成 | [浏览](platform/assets/keyword_dictionary_semantic_review_r2/关键词主题浏览.html) / [接口](platform/assets/keyword_dictionary_semantic_review_r2/platform_data.json) / [审核问题](platform/assets/keyword_dictionary_semantic_review_r2/REVIEW.json) |
| P2 业务主题 | 9 类业务、51 个题名检索主题；包含定义、用途、趋势和对象决策卡 | [业务手册](platform/docs/P2业务主题与决策使用手册.md) / [预览](platform/preview/index.html) |
| RBK500 多主题 | 数据驱动 500 主题与范围初审；专利政策为迁移候选，内容未通过正式业务验收 | [预览](platform/preview/nmf500_multilabel.html) / [验收记录](platform/acceptance/nmf500_multilabel_20261019/ACCEPTANCE.json) |
| F500 | 全量关键词 TF-IDF + NMF 与 BGE-M3 跨来源候选，5,119,004 条冻结记录 | [主题目录](assets/full_nmf500/topic_catalog.csv) / [报告](assets/full_nmf500/REPORT.md) |

最新词典尚有 43,263 个词未逐项审读；未命中不等于能源无关。本版没有重算专利、政策、热点、趋势或 TRL/CRL。完整逐篇分片的路径、大小和 SHA256 见 [外部文件清单](platform/EXTERNAL_FILES.json)，原数据未删除。

## 代码与接口

- [第二轮关键词流水线](pipelines/keyword_dictionary_review_r2/)：词典、归属、复核、查询和导出。
- [第一轮词典](pipelines/keyword_dictionary/)与[K500流水线](pipelines/multilabel_scope/)：保留可追溯版本。
- [F500流水线](pipelines/full_nmf/)：关键词准备、训练、编码和跨来源候选。
- [P2业务定义](assets/full_nmf500/p2/business_taxonomy.json)、[F编号追溯](assets/full_nmf500/p2/f_topic_bridge.json)。
- [共享业务文档和联调资料](platform/)、[组装工具](tools/assemble_platform.py)。
- `pipelines/keyword_dictionary_full_review/` 是尚未形成发布结果的审核工具，不能当作已完成的第三版。

## 本地验证

```bash
python -m pip install -r requirements-nmf500.txt -r requirements.txt duckdb threadpoolctl openpyxl
python -m pytest tests -q --import-mode=importlib --ignore=tests/test_embedding_pool.py --ignore=tests/test_topic_components.py
python tools/validate_release.py
python tools/check_platform_assets.py
```

上述命令运行当前 CPU 流程与交付测试。可选的 ONNX 池化和 BERTopic 兼容测试分别需要 ONNX/ONNX Runtime 及 `requirements-topic-modeling.txt` 依赖，安装后可单独运行对应测试文件。

## 数据与运行边界

Git 保存源码、配置、紧凑统计、抽样证据和业务解读。大型原始 `data/`、冻结语料、向量、模型、数据库和全量逐篇导出继续留在外部工作区。克隆仓库可阅读交付及运行测试，不等于拥有全量重算输入。

全量流水线通过 `config/runtime_paths.json` 指定输入，支持 `ENERGY_DATA_ROOT`、`ENERGY_CORPUS_DIR`、`ENERGY_METADATA_DB`、`ENERGY_CLASSIFICATION_RUN` 等环境变量。相对路径按配置文件位置解析。三个仓库并列克隆可进行联合运行；跨模块 P1/P2 构建请先组装平台目录，见[平台接入说明](docs/PLATFORM_INTEGRATION.md)。

本次为仓库整理和现有成果同步，未重训分类、重算热点或抬高成熟度等级。各版本范围和编号必须随接口展示；程序检查通过不等于语义准确率或专家验收通过。

[算法方法](docs/METHOD.md) · [复现说明](docs/REPRODUCING.md) · [文件用途](docs/PROJECT_STRUCTURE.md) · [核心文件清单](docs/CORE_FILES.md)
