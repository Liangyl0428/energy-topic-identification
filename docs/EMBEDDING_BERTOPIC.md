# 文本编码和 BERTopic 怎么运行

这部分代码负责最前面的两步：把原文转换为语义向量，再把内容相近的记录分组、提取主题词。后续的合并、细分和 750 类整理见[方法说明](METHOD.md)。

## 两个目录分别做什么

| 目录 | 文件 | 作用 |
| --- | --- | --- |
| `pipelines/embedding/src/` | `download_encoder.py` | 下载固定版本的多语言 MiniLM 模型 |
| 同上 | `pool_encoder.py` | 给 ONNX 模型添加带掩码的平均池化和向量归一化 |
| 同上 | `encode.py` | 分段处理题名和正文，保存每篇记录的 384 维向量 |
| `pipelines/topic_modeling/src/` | `lexical.py` | 中英文分词、建立词表、保存全文词频 |
| 同上 | `train_baseline.py` | 训练 500 类底稿，生成主题词、标签和中心向量 |
| 同上 | `train_candidates.py` | 复用同一批文档向量、PCA 和词频，重新训练 1000 类候选 |
| 同上 | `components.py`、`experiment_components.py` | BERTopic 使用的投影、固定聚类器、词频累计和 c-TF-IDF 组件 |

其余 `*_common.py` 文件定义路径和通用读写函数。代码按功能组织，两种聚类粒度共用同一套语料，不再各建一个历史版本目录。

## 使用的算法

**文本编码。** 模型为 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`，下载脚本固定了模型版本。长文本分段进入模型，各段向量再按覆盖的文本长度加权汇总，得到一篇记录的向量。政策文本额外兼顾开头叙述部分，避免超长数字附件淹没政策主题。正文各段均参与编码。

**聚类。** 对文档向量计算按来源加权的 PCA，降到 64 维后归一化，再使用 MiniBatchKMeans 聚类。训练权重为论文 70%、专利 25%、政策 5%，随机种子为 500。500 类和 1000 类是预先设置的粒度。

**主题词。** 在 BERTopic 中，将训练好的聚类器固定下来，按类别累计真实题名和正文的词频，再用 c-TF-IDF 计算有代表性的词。固定词表的选择使用抽样文本，选好词表后，词频统计覆盖全部文本。1000 类流程中传给 BERTopic 的行号字符串只用于标记文档身份，主题词来自预先计算的真实文本词频。

因此，这里使用的是自定义聚类和词频组件的 BERTopic。降维使用 PCA，聚类使用 MiniBatchKMeans，并未采用默认的 UMAP/HDBSCAN 组合。

## 运行前准备

需要 Python 3.10+，建议在独立环境和仓库副本中执行：

```bash
python3 -m pip install -r requirements-topic-modeling.txt
```

该依赖文件包含 `bertopic==0.17.3` 和编码、词频处理所需的包。实际编码沿用原项目的 ONNX FP16 模型和 CUDA 执行方式，需要匹配的 NVIDIA GPU、CUDA 和 ONNX Runtime 环境。聚类、词频处理及小规模组件测试主要使用 CPU。这里固定了 BERTopic 版本，其余依赖清单不是原运行环境的完整锁文件。

模型由下载脚本获取，不包含在 Git 仓库中。下载权重需要网络；文本编码和聚类在本地进行，代码不会把原文发送到模型 API。

### 原语料的格式

把已整理的语料放在 `inputs/baseline/data/corpus/`，并提供 `inputs/baseline/data/INPUT_MANIFEST.json`。语料清洗和来源数据库导入脚本未在本次补回范围内。

每个 Parquet 分片至少需要以下列：

| 列 | 内容 |
| --- | --- |
| `row_id` | 从 0 开始连续的全局整数行号；同一分片内按行号排列 |
| `source` | `paper`、`patent` 或 `policy`；原词表抽样流程要求每个分片只包含一种来源 |
| `title`、`body` | 字符串形式的题名和正文，没有正文时用空字符串 |
| `usable` | 布尔值，表示文本是否可用于编码和聚类 |

文件清单包含 `documents`（总行数）、`source_counts`（三类来源的记录数）和 `parts`（有序分片列表）。每个分片条目包含 `file`（相对于 `inputs/baseline/` 的路径）、`first_row`、`n` 和该 Parquet 文件的 `sha256`。

后续 `refinement` 还会用到文献编号、日期、撤稿标记等原始字段，准备语料时应一并保留。以上两种训练入口沿用原数据规模和参数，要求三种来源都有可用记录，并有足够数据支撑 500/1000 个非空类别；不适合直接拿几条示例文本运行。

## 按什么顺序运行

在仓库根目录执行。每一步完成后，再开始下一步。

### 1. 下载模型并编码

```bash
python3 pipelines/embedding/src/download_encoder.py
python3 pipelines/embedding/src/pool_encoder.py
python3 pipelines/embedding/src/encode.py
```

模型写入 `inputs/baseline/models/multilingual_minilm/`。文档向量写入 `inputs/baseline/models/embeddings/`，每个向量分片与对应的语料分片逐行对齐。编码完成后生成 `EMBEDDING_AUDIT.json`，记录输入校验值、模型版本和处理数量。

### 2. 统计真实文本的词频

```bash
python3 pipelines/topic_modeling/src/lexical.py
```

输出为 `inputs/baseline/models/vectorizer.joblib`、`models/bow/` 下的词频分片及 `BOW_AUDIT.json`。词表中的中文词使用 jieba 分词，英文及技术术语按代码中的规则处理。

### 3. 生成 500 类底稿

```bash
python3 pipelines/topic_modeling/src/train_baseline.py
```

主要输出位于 `inputs/baseline/`：

- `results/raw_500_topics.csv`：类别数量、主题词和来源数量。
- `results/raw_labels.npy`：每条记录的原始聚类编号；文本不可用时为 `-2`。
- `models/topic_centroids.npy`：主题中心向量。
- `models/projection.joblib`、`models/reduced.npy`：PCA 投影和降维后的文档向量。
- `models/bertopic500.joblib`：保存的 BERTopic 模型。

### 4. 生成 1000 类候选

```bash
python3 pipelines/topic_modeling/src/train_candidates.py
```

这一入口读取上一步的语料、向量、PCA 和词频，重新进行全局聚类，输出到 `inputs/candidates/`。主要文件包括 `results/raw_1000_topics.csv`、`results/raw_labels.npy`、`results/secondary_labels.npy`、`models/topic_centroids.npy` 和 `models/bertopic1000.joblib`。

两个训练入口会拒绝覆盖已有完成标记的运行。更换语料或训练参数时，请使用独立副本和一套新的输出文件，避免复用旧投影、词表或模型缓存。

保存的模型使用了本目录中的自定义类。加载 `.joblib` 模型前，需要把 `pipelines/topic_modeling/src/` 加入 Python 搜索路径。

## 如何接到最终 750 类

这两个目录产生的向量和标签，与现有 `refinement` 的 `inputs/baseline/`、`inputs/candidates/` 路径约定一致。但初始聚类编号还需要经过类别合并和规则准备，才能成为正式研究主题。

具体来说，500 类合并为 486 类时采用的 `merged_topics.csv`、`raw_to_merged.csv`，以及细分时使用的规则向量、检索信息和处理计划，仍需要补齐原项目的对应文件。已有规则记录保存在 `pipelines/refinement/review/`。本次补回的是 embedding 与 BERTopic 算法核心，没有把人工语义判断和全部历史输入准备封装为自动程序。

这次没有重跑数百万条原语料，也没有重新生成 750 主题表。已交付的 Excel、CSV 和统计继续保存在根目录 `results/`。

## 小规模验证

安装上述依赖后，可运行组件测试：

```bash
python3 -m unittest discover -s tests -v
```

测试使用构造的小数据检查池化、词频累计和 BERTopic 主题词计算，不下载真实模型，也不要求完整语料。这些测试用于验证代码组件；完整训练结果仍需在实际语料和运行环境下核对。
