# Energy Topic Identification · 能源电力主题识别

能源电力领域的论文、专利和政策主题识别，包含核心代码、方法说明和 **750 个主题的完整结果表**。当前目录统一编号为 **C0001–C0750**，结果快照日期为 2026-09-25。

## 查看结果

- [750 主题 Excel：目录、来源数量、改标流向与复核统计](results/750类平级目录与文献标签.xlsx)
- [750 主题 CSV：方便浏览和程序读取](results/category_dictionary.csv)
- [结果汇总 JSON](results/SUMMARY.json)
- [历史标签到 750 类的映射](provenance/original_audit/label_crosswalk.csv)
- [原始结果报告](docs/original/REPORT.md) · [字段说明](docs/original/DATA_DICTIONARY.md)

| 项目 | 数量 |
| --- | ---: |
| 当前主题 | 750 |
| 输入记录 | 5,119,004 |
| 已归入研究类别 | 5,111,081 |
| 质量隔离 | 7,923 |
| 相对最初底稿调整研究主题标签 | 374,161 |
| 仍待复核的记录（含质量隔离） | 2,758,621 |

每条已归类记录只计入一个当前主题。类别表的 `documents` 是直接归类数量；`countable_documents` 排除撤稿；`supported_documents` 进一步限定为获得自动规则支持的非撤稿记录。三个数量不能混用。

## 识别思路

1. **统一多源语料。** 将论文、专利、政策整理为题名、正文、来源和全局 `row_id`，保留来源及质量标记。
2. **多语言语义编码。** 使用多语言 MiniLM，将长文本分段编码并聚合为文档向量；初始编码覆盖各段，后续规则判别有自己的证据范围。
3. **主题发现。** 对向量做 PCA64 与 L2 归一化，在 BERTopic 中使用 MiniBatchKMeans 形成固定数量的候选主题，再从真实文本词频提取 c-TF-IDF 主题词。500 类底稿和 1000 类试验使用论文/专利/政策 70%/25%/5% 的训练权重；1000 类试验全局重新聚类。
4. **语义整理与精细修订。** 结合主题词、代表文本、相近主题和同义审阅整理目录，再通过“研究对象 + 研究任务”规则、向量支持、文本清理及精度防护修订文档归属。证据不足、多任务冲突和过宽候选保留待复核标记。
5. **形成 750 类平级目录。** 将已有正式决定中实际使用的 486 个主类与 264 个子类统一编号为 C0001–C0750；质量隔离独立保存。该步骤不重新训练模型，也不新增语义改标，统计按文档直接归属计算，避免父子类重复计数。

**750 是整理后的当前目录数量，并非一次聚类自动发现的天然类别数。** 当前结果基于自动规则和抽样诊断，仍有待复核记录；没有独立金标准，不能据此宣称分类准确率或所有主题在语义上完全互斥。

## 核心代码

代码保留原阶段目录及原实现，便于追溯已交付结果。

| 目录（均位于 `pipelines/jjjj/`） | 作用与主要入口 |
| --- | --- |
| `bertopic500_all_sources_20260925/src` | 语料准备、分段编码、初始聚类：`prepare.py`、`encode.py`、`cluster.py` |
| `bertopic1000_all_sources_20260925/src` | 1000 类全局候选聚类及主题词：`train.py`、`experiment_components.py` |
| `bertopic1000_semantic_merged_20260925/src` | 同义主题审阅与映射：`semantic_mapping.py`、`apply_merges.py` |
| `bertopic990_strict_overlap_audit_20260925/src` | 主题重合和文本质量审计 |
| `bertopic486_hierarchical_refined_20260925/src` | 精细分类：`taxonomy.py`、`rule_engine.py`、`classify.py`、`decision_guards.py`、`text_quality.py` |
| `bertopic750_flat_refined_20260925/src` | 当前目录转换、完整标签校验与交付：`build_flat.py`、`validate_flat.py`、`build_delivery.py` |

精细分类目录下的 `review/` 保存冻结规则、语义修订和别名决定；`provenance/SOURCE_FILES.json` 记录迁移文件的来源与 SHA-256。

## 本地查看与校验

Python 3.10+。目录查询仅使用标准库：

```bash
python3 tools/catalog.py --id C0001
python3 tools/catalog.py --search 储能
python3 tools/catalog.py --search 储能 --output work/storage.csv
```

校验依赖及命令：

```bash
python3 -m pip install -r requirements.txt
python3 tools/validate_release.py
```

校验覆盖：750 个连续编号、逐主题来源计数、全局汇总、Excel 与 CSV 逐行一致性、迁移文件和发布文件哈希、Python 语法。无需联网、GPU 或原项目目录。

## 全流程复现范围

本仓库提供**核心实现与冻结结果**。全量语料、500 多万条逐文档标签、模型权重、向量和词频缓存不随 Git 仓库分发；仅克隆本仓库不能重跑完整训练，也不能直接对任意新文档提供已验证的分类预测。

查看与校验上述结果可以独立运行。若需全量重算，须补齐原始输入并恢复阶段目录，详见 [复现说明](docs/REPRODUCING.md)。训练依赖另列于 `requirements-pipeline.txt`。原始校验报告是历史运行证据，当前打包校验记录见 [发布校验](provenance/RELEASE_VALIDATION.json)。
