# 主题表的字段说明

本页主要解释 [category_dictionary.csv](../results/category_dictionary.csv)。它有 750 行主题数据，第一行为列名；Excel“类别目录”中的中文列与这些字段对应。

## 编号和名称

| 字段 | 含义 |
| --- | --- |
| `category_id` | 主题编号，如 `C0001`；日常引用主题时建议使用这一列 |
| `category_name` | 主题的中文名称 |
| `category_index` | 程序使用的整数编号，范围为 0–749；例如 0 对应 `C0001` |

## 每个主题有多少记录

| 字段 | 含义 |
| --- | --- |
| `documents` | 当前归入这个主题的记录总数 |
| `paper_documents` | 其中的论文数 |
| `patent_documents` | 其中的专利数 |
| `policy_documents` | 其中的政策记录数 |
| `countable_documents` | 排除撤稿后的记录数，可能仍含待复核记录 |
| `supported_documents` | 标签有自动规则支持、非撤稿且无需复核的记录数 |

同一主题的论文数、专利数、政策数之和等于 `documents`。关于三种统计范围的区别和实际例子，见[结果说明](RESULTS.md#三种数量有什么区别)。

## 哪些记录经过处理或还需要检查

| 字段 | 含义 |
| --- | --- |
| `needs_review_documents` | 这个主题下仍需要复核的记录数 |
| `retracted_documents` | 带撤稿标记的记录数；`documents` 减去这一列等于 `countable_documents` |
| `text_cleaned_documents` | 做过题名或正文清理的记录数 |
| `semantic_label_changes` | 相对最初分类，研究主题发生调整的记录数；仅更换编号不算调整 |

这些状态可能重叠。例如，一条记录既可能清理过文本，也可能仍待复核，所以不能把这些列相加当成新的总数。

## 其他结果文件

| 文件 | 内容 |
| --- | --- |
| [SUMMARY.json](../results/SUMMARY.json) | 全局数量和各类处理状态的汇总 |
| [quarantine_dictionary.csv](../results/quarantine_dictionary.csv) | 因质量问题单独处理的记录：非研究正文、题名摘要不足、模板干扰、文本不可用 |
| [status_counts.csv](../results/status_counts.csv) | 沿用标签、调整标签、待复核等决定状态的数量 |
| [source_counts.csv](../results/source_counts.csv) | 全部输入按论文、专利和政策划分的数量 |
| [review_reason_counts.csv](../results/review_reason_counts.csv) | 各种待复核原因及数量 |
| [label_crosswalk.csv](../provenance/original_audit/label_crosswalk.csv) | 旧标签与当前类别编号的对应关系 |

质量隔离文件中的 `Q.*` 编号表示问题类型，不算额外的研究主题。

## 如果需要读取每篇记录的标签

逐文档数据没有包含在本仓库中。如果另行取得原项目的数据，最重要的字段是：

| 字段 | 含义 |
| --- | --- |
| `row_id` | 跨来源唯一的全局行号，用它关联同一条记录 |
| `doc_id`、`source` | 来源中的文献编号和来源类型；不同来源的 `doc_id` 可能相同 |
| `category_id`、`category_name` | 当前主题编号和名称；质量隔离记录为空 |
| `needs_review`、`review_reason` | 是否待复核，以及待复核原因 |
| `quarantined`、`quarantine_reason` | 是否因质量问题单独处理，以及原因 |
| `eligible_for_counts` | 是否计入“可统计记录数” |
| `eligible_for_supported_analysis` | 是否计入“自动规则支持数” |

更完整的逐文档字段定义保存在[原始字段文档](original/DATA_DICTIONARY.md)。其中的路径指向原完整项目；本仓库的输入位置和运行方式以[使用说明](REPRODUCING.md)为准。
