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

`pipelines/` 只保留直接用于最终分类决定和 750 类交付的两个模块，共 13 个 Python 文件：

| 目录 | 作用与主要入口 |
| --- | --- |
| [`pipelines/refinement/src`](pipelines/refinement/src) | 最终分类与修订：`taxonomy.py` 定义对象/任务规则，`rule_engine.py` 匹配证据，`classify.py` 结合向量支持决定归属，`text_quality.py` 清理文本，`decision_guards.py` 防止误归类，`finalize.py` 固化正式决定 |
| [`pipelines/export750/src`](pipelines/export750/src) | 750 类输出：`build_flat.py` 统一编号和汇总，`validate_flat.py` 校验完整标签，`build_delivery.py` 生成工作簿，`read_flat.py` 读取逐文档结果 |

[`pipelines/refinement/review`](pipelines/refinement/review) 保存最终使用的规则、语义修订和别名决定；`results/topic_dictionary.csv` 是转为 C0001–C0750 之前的标签字典，用于对照。源码中的旧标签编号是溯源字段，不代表本仓库另有多套最终主题目录。

历史上不同主题数量的训练试验、版本比较和中间审计只在“识别思路”中说明，不再分目录收录。`provenance/SOURCE_FILES.json` 记录保留文件的原始来源及当前校验和；路径适配过的文件另保留原始校验和。

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

查看与校验上述结果可以独立运行。若需重算最终分类与导出，须补齐冻结的上游输入，详见 [复现说明](docs/REPRODUCING.md)。分类与导出依赖另列于 `requirements-pipeline.txt`。原始校验报告是历史运行证据，当前打包校验记录见 [发布校验](provenance/RELEASE_VALIDATION.json)。
