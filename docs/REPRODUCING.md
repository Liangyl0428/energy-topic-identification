# 运行与复现

## 可以直接运行的部分

在仓库根目录运行 `python3 tools/catalog.py --search 光伏` 查询主题名称或编号，使用 `--output work/pv.csv` 导出匹配结果。这是目录检索，不是新文档分类。

安装 `requirements.txt` 后，运行 `python3 tools/validate_release.py` 核对 750 类目录、Excel、CSV、汇总和文件哈希。无需原项目或 GPU。Excel 是汇总表，不包含 500 多万条逐文档标签。

## 保留的最终处理链

```text
冻结上游输入（语料、既有标签、候选向量）
  → refinement：对象/任务规则 + 文本质量 + 向量支持 + 精度防护
  → 正式文档归类决定
  → export750：统一 C0001–C0750 编号、逐类计数、校验、Excel 导出
```

`pipelines/` 只有 `refinement` 和 `export750` 两个目录。保留的算法和冻结规则来自最终结果处理链；旧聚类训练、对比试验、中间审计和历史交付程序已移除。初始主题发现的方法在根 README 中说明；本精简仓库不负责从零训练上游候选模型。

## 代码路径及外部输入

共享路径模块已适配当前仓库结构，不再引用 `jjjj/` 或原机器的依赖目录。`ROOT` 为仓库根目录；输入和输出约定如下：

| 路径 | 内容 |
| --- | --- |
| `inputs/baseline/data/` | 原语料 `corpus/part-*.parquet`、`INPUT_MANIFEST.json` |
| `inputs/baseline/results/` | 冻结底稿 `merged_topics.csv`、`raw_to_merged.csv`、`raw_labels.npy` |
| `inputs/baseline/models/` | 原文档向量 `embeddings/`、`multilingual_minilm/` 编码器 |
| `inputs/candidates/results/` | 冻结候选 `raw_labels.npy`、`secondary_labels.npy` |
| `inputs/candidates/models/` | 冻结候选中心 `topic_centroids.npy` |
| `pipelines/refinement/models/` | 冻结规则向量 `rule_name_vectors.npy` 和检索缓存 `rule_retrieval.json` |
| `pipelines/refinement/review/` | 随库提供的规则及语义修订 |
| `pipelines/refinement/results/` | 正式逐文档标签、清理文本及汇总；随库仅提供转换前的 `topic_dictionary.csv` |
| `pipelines/export750/` | 重新运行 750 类转换时的输出根目录 |
| 根目录 `results/` | 随库提供的已交付 750 类 Excel、CSV 和统计快照 |

除明确注明随库提供的文件外，上表中的输入均须另行准备。`finalize.py` 还读取冻结的 `pipelines/refinement/results/parent_processing_plan.csv` 和分类产生的 `logs/part-*.json`。本次保留核心执行逻辑，未将历史输入准备过程重新封装为自动管线。

有完整冻结输入时，在独立副本中安装 `requirements-pipeline.txt`，运行 `refinement/src/classify.py`（用 `--start`、`--stop` 指定语料分片）后运行 `finalize.py`。文本清理后重新编码使用 CUDAExecutionProvider，需要匹配的 GPU、CUDA 和模型文件。原判别阈值与规则没有改动。

也可以直接补齐已有正式决定，跳过分类重算。750 类转换所需文件包括 `refinement/results/ASSIGNMENT_MANIFEST.json`、正式分片、`SUMMARY.json`、`topic_dictionary.csv`、`VALIDATION.json`（位于 `refinement/` 根目录），以及原语料清单。完整校验还需正式标签数组、复核标记、原语料和清理文本。依次运行：

```bash
python3 pipelines/export750/src/build_flat.py
python3 pipelines/export750/src/validate_flat.py
python3 pipelines/export750/src/build_delivery.py
```

输出写入 `pipelines/export750/`，根目录的已交付结果不作为重算输出目录。正式决定的语义验收仍需研究者判断，脚本和规则不能替代人工复核。重算结果不应在未核验输入指纹和语义决定的情况下被称为与历史结果相同。

`docs/original/` 和 `provenance/original_audit/` 保存历史运行说明与证据，其中旧路径仅用于溯源，不是本仓库的运行路径。当前发布校验见 `provenance/RELEASE_VALIDATION.json`。
