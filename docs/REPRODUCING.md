# 如何使用这个仓库

只看主题表的话，打开 [Excel](../results/750类平级目录与文献标签.xlsx) 即可。下面的操作适合希望用代码查询、检查或重新计算结果的读者。

文中的命令都在仓库根目录运行，需要 Python 3.10 或更新版本。

## 查询和导出主题

按名称中的文字搜索，例如“储能”：

```bash
python3 tools/catalog.py --search 储能
```

按编号查找某个主题：

```bash
python3 tools/catalog.py --id C0001
```

把搜索结果另存为 CSV：

```bash
python3 tools/catalog.py --search 储能 --output work/storage.csv
```

`--search` 匹配主题名称或编号中的文字。以上操作只需要 Python 自带的功能，无需下载模型。为避免覆盖已有文件，导出时应使用尚不存在的文件名。

## 检查下载的结果是否完整

先安装检查 Excel 所需的依赖，再运行检查程序：

```bash
python3 -m pip install -r requirements.txt
python3 tools/validate_release.py
```

运行成功时会输出 `"passed": true`。程序会检查主题编号、数量汇总、Excel 与 CSV 的对应关系，以及文件校验值。

这一步检查的是文件和数据的一致性。它不会重新阅读原文，也不会评价每篇记录分得是否准确。

## 想重新计算分类，需要准备什么

仓库提供了文本编码、BERTopic 聚类、最终分类和导出代码，但没有附带完整原始语料、逐篇标签、模型权重和向量。因此，下载仓库后可以直接查目录、核对结果；要运行完整分类，还需要取得原项目中已经准备好的输入。

这些输入包括原文、此前的分类标签、候选主题向量和规则对应的向量。它们组成了一次固定的数据版本；文档中提到“冻结输入”时，指的就是这组用于产生本次结果的既定文件。

实际处理顺序是：

```text
原语料
    ↓
embedding：分段编码，生成文档向量
    ↓
topic_modeling：生成候选类别和主题词
    ↓
类别合并与规则准备：结合文本审阅确定采用的类别
    ↓
refinement：清理文本，检查分类证据，修订归属
    ↓
每篇记录的正式分类结果和复核标记
    ↓
export750：统一编号，汇总数量，检查并导出 Excel
```

初始编码和聚类的操作详见[编码和主题聚类](EMBEDDING_BERTOPIC.md)。聚类产生的类别还需要语义合并、审阅和规则准备，才能进入最终分类；这些步骤尚未全部做成一键运行程序。下面介绍最终分类和导出的输入约定。

### 输入文件放在哪里

下表中的路径都相对于仓库根目录。没有注明“已提供”的文件，需要另行准备。

| 路径 | 需要的内容 |
| --- | --- |
| `inputs/baseline/data/` | 原语料分片 `corpus/part-*.parquet` 和文件清单 `INPUT_MANIFEST.json` |
| `inputs/baseline/results/` | 既有分类目录 `merged_topics.csv`、映射 `raw_to_merged.csv` 和标签 `raw_labels.npy` |
| `inputs/baseline/models/` | 文档向量 `embeddings/` 和编码器 `multilingual_minilm/` |
| `inputs/candidates/results/` | 候选标签 `raw_labels.npy`、`secondary_labels.npy` |
| `inputs/candidates/models/` | 候选主题中心 `topic_centroids.npy` |
| `pipelines/refinement/models/` | 规则向量 `rule_name_vectors.npy` 和检索信息 `rule_retrieval.json` |
| `pipelines/refinement/review/` | **已提供**：分类规则、语义修订和别名对应关系 |
| `pipelines/refinement/results/` | **仅提供 `topic_dictionary.csv`**：其余逐文档结果和汇总需生成或补齐 |

`.npy` 保存数值数组，`.parquet` 保存逐行数据，`.json` 保存配置或文件清单。文件名和内容都需要与代码约定一致。

### 重新运行分类

建议在仓库的独立副本中运行，以便保留已有规则和结果。先安装分类与导出的依赖：

```bash
python3 -m pip install -r requirements-pipeline.txt
```

输入齐备后，运行 `pipelines/refinement/src/classify.py`，再运行同目录的 `finalize.py`。分类程序支持用 `--start` 和 `--stop` 指定处理哪些数据分片，可先查看参数：

```bash
python3 pipelines/refinement/src/classify.py --help
```

`finalize.py` 还会读取 `pipelines/refinement/results/parent_processing_plan.csv`，以及分类生成的 `pipelines/refinement/logs/part-*.json`。其中的处理计划也需要从原输入补齐。

文本清理后重新编码的步骤要求可用的 GPU、匹配的 CUDA 环境和模型文件。仅安装 Python 依赖不足以完成这一步。

### 已有逐篇分类，只想重新生成 750 类结果

这种情况下，可以直接使用已有正式分类，跳过前面的分类计算。先补齐：

- `pipelines/refinement/results/` 下的 `ASSIGNMENT_MANIFEST.json`、正式数据分片、`SUMMARY.json` 和 `topic_dictionary.csv`。
- `pipelines/refinement/VALIDATION.json`，即原正式分类的验证记录。
- 原语料清单；完整校验还会读取原语料、正式标签数组、复核标记和清理文本。

然后依次运行：

```bash
python3 pipelines/export750/src/build_flat.py
python3 pipelines/export750/src/validate_flat.py
python3 pipelines/export750/src/build_delivery.py
```

新生成的文件写入 `pipelines/export750/`。仓库根目录 `results/` 中保存的是已经交付的结果表，程序不会把它当作这次重算的输出位置。

输入文件和审阅决定的差异都可能影响重算结果。需要复现原结果时，应同时核对输入版本和分类决定；仅看到 750 个类别，并不足以证明两次结果相同。

## 原始文档和校验记录在哪

`docs/original/` 保留了原项目交付时的说明，`provenance/original_audit/` 保留了历史检查记录。里面可能出现原项目路径，阅读当前仓库时以本页的路径为准。

[文件来源清单](../provenance/SOURCE_FILES.json)记录核心文件来自哪里，[发布校验记录](../provenance/RELEASE_VALIDATION.json)记录本仓库最近一次检查的结果。这些资料主要供追溯和核对使用，日常浏览主题表无需先阅读它们。
