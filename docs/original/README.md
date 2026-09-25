# 750类平级分类版

当前实际使用 **750 个类别**，统一编号 **C0001–C0750**，完整目录在一张表中平级列出。

入口：[中文工作簿](750类平级目录与文献标签.xlsx) · [类别CSV](results/category_dictionary.csv) · [结果说明](REPORT.md) · [字段说明](DATA_DICTIONARY.md)。

共 **5,119,004 条记录**：其中 **5,111,081 条各对应一个研究类别**，另 **7,923 条质量隔离**，类别为空，不增加研究类别数。目录仅统计实际归入各类别的记录，每条记录只计一次。

本次统一类别结构与编号，保留已有的正式归类决定。此前相对最初底稿的 **374,161 条研究主题标签调整**已全部继承；本次换号不计为新的语义改标。

仍有 **2,758,621 条待复核**。类别数不代表语义已完全无重合，沿用标签也不表示已经重新逐篇验证。原有语义判断基于自动规则与抽样诊断，未人工读完全部记录。

- `results/assignments/part-*.parquet`：259片完整文献标签，含文献ID、题名、来源、当前类别和复核状态。
- `results/category_dictionary.csv`：750个实际使用的类别及直接记录数，含论文、专利、政策计数。
- `results/final_labels.npy`：按`row_id`排列的类别整数索引；0–749对应类别字典，-1表示质量隔离。
- `results/analysis_count_labels.npy`：排除撤稿后的当前类别索引，其他为-1；其中仍可能包含待复核记录。
- `results/analysis_supported_labels.npy`：自动规则支持且非撤稿的类别索引，其他为-1。
- `results/needs_review.npy`、`results/quarantined.npy`：逐条布尔标记。
- `results/pending_review/`、`results/label_changes/`、`results/quality_quarantine/`：待复核、相对底稿标签变化和质量隔离记录。
- `results/text_corrections/`：已完成的文本清理副本；原始语料保留。
- `audit/label_crosswalk.csv`：历史正式标签到当前编号的映射；无记录的候选不进入类别目录。

工作簿展示完整类别表及汇总统计；500余万条逐条标签全部保存在Parquet文件中。

读取一条文献、清理后的正文与当前类别（系统`python3`）：

```sh
python3 /pyg-vepfs/public/lyl/openalex_energy_fetch/jjjj/bertopic750_flat_refined_20260925/src/read_flat.py --row-id 4006773 --output /tmp/flat_document.json
```

批量读取时把`src`加入Python搜索路径，调用`read_flat.iter_flat_parts()`；只需要题名和标签时传`include_body=False`。读取完整原文需保留原始语料目录`jjjj/bertopic500_all_sources_20260925/data/corpus/`。

结构转换脚本：`src/build_flat.py` → `src/validate_flat.py` → `src/build_delivery.py`。输入正式决定及哈希见`audit/INPUT_REFERENCES.json`。此前版本均保留；历史候选和规则证据可按`row_id`追溯。本版不重新运行语义模型。

全量一致性校验见`VALIDATION.json`，工作簿逐格回读校验见`audit/WORKBOOK_VALIDATION.json`，交付文件哈希见`DELIVERY_MANIFEST.json`。
