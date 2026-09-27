# 能源电力主题识别

以全量论文的OpenAlex关键词进行TF-IDF + NMF主题建模，再将全部可用专利、政策匹配到论文主题中心。当前目录为500个主题，编号F0001–F0500。

## 当前流程

1. 从4,831,088篇论文提取关键词，用全部论文统计文档频率、拟合IDF。
2. 对全部非零关键词论文训练500组件MiniBatchNMF，共5轮；冻结H后统一推断论文归属。
3. 对论文、专利、政策共5,119,004条记录生成同一BGE-M3空间的1024维归一化向量。
4. 每个主题内有效论文向量求均值并归一化。专利／政策与500个中心计算余弦，取最高者为候选类别，保留Top3及差距。
5. 校验记录身份、覆盖数量、中心范数和全部跨来源最大余弦归属，输出供热点及成熟度流程使用的结果。

已分类5,104,807条，14,197条因缺少有效关键词或可用文本保留未分类。自动候选仍需语义审核，未宣称人工准确率。

## 核心代码与结果

|内容|入口|
|---|---|
|完整流水线|[run.py](pipelines/full_nmf/run.py)|
|关键词与TF-IDF|[prepare.py](pipelines/full_nmf/prepare.py)|
|NMF训练及统一推断|[train.py](pipelines/full_nmf/train.py)、[fast_nmf.py](pipelines/full_nmf/fast_nmf.py)、[components.py](pipelines/keyword_nmf/src/components.py)|
|全来源embedding|[encode.py](pipelines/full_nmf/encode.py)|
|主题中心与跨来源匹配|[finalize.py](pipelines/full_nmf/finalize.py)|
|500主题目录|[topic_catalog.csv](assets/full_nmf500/topic_catalog.csv)|
|覆盖及程序校验|[coverage.csv](assets/full_nmf500/coverage.csv)、[VALIDATION.json](assets/full_nmf500/VALIDATION.json)|

[算法方法](docs/METHOD.md) · [字段说明](docs/DATA_DICTIONARY.md) · [复现运行](docs/REPRODUCING.md) · [核心文件清单](docs/CORE_FILES.md) · [实验与交付](docs/FULL_EXPERIMENTS.md)。

Git包含核心源码、参数记录和紧凑结果；大型原始语料、完整向量、训练矩阵和模型权重保留在工作区，不是克隆即有的全量数据包。

## 目录导航

[完整项目结构及每个文件用途](docs/PROJECT_STRUCTURE.md)。当前成果在 `assets/full_nmf500/`；`tests/fixtures/` 只用于回归测试。
