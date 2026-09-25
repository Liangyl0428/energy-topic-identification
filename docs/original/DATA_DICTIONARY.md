# 文献类别与统计字段

`results/assignments/`的259个分片与原语料行序对应；全局主键是`row_id`，并非`doc_id`。不同来源可能有相同文献编号。

| 字段 | 含义 |
|---|---|
| row_id | 0至5,119,003，全局行号，也是NPY数组下标 |
| doc_id / source / date | 原文献ID、来源、日期，逐条不变 |
| title | 保留已完成清理的题名；原题名可用read_flat读取 |
| category_index | 当前类别的0至749整数索引；质量隔离为-1 |
| category_id / category_name | 单一当前类别编号和名称；质量隔离时均为空 |
| baseline_category_id / baseline_category_name | 最初底稿类别，以本版统一编号表示；原无研究类别时为空 |
| baseline_review_status | 保留底稿类别的审阅状态 |
| assignment_status | 当前决定状态，中文解释见results/status_counts.csv |
| label_origin | 自动题名规则及语义支持、沿用底稿未新验收、质量隔离三种来源 |
| label_changed | 相对最初底稿标签是否变化，包含进入质量隔离；不将本次换号算作变化 |
| semantic_label_changed | 相对最初底稿的研究主题调整，不含质量隔离 |
| quarantined / quarantine_code / quarantine_reason | 是否质量隔离、Q.*状态编号、隔离原因；不是研究类别 |
| quality_status / initial_quality_status / quality_flags | 当前文本质量、原自动决定时的质量状态和处理标记 |
| text_cleaned | 是否曾做文本清理，完整副本见results/text_corrections/ |
| retracted | 原撤稿标记，保留但排除于两个分析口径 |
| needs_review / review_reason / review_priority | 待复核标记、原因、优先级；1最优先，0不进入本轮待复核清单 |
| priority_cleanup | 是否来自此前优先清理的宽泛、混杂类别 |
| eligible_for_counts | 有当前研究类别且非撤稿，可作粗统计；不表示标签已通过语义验收 |
| eligible_for_supported_analysis | 当前研究标签获既有自动规则支持且非撤稿，不含待复核记录 |
| rule_id | 既有自动规则编号，用于审计；不是本版类别编号 |
| text_evidence_level | 3为题名提供对象与任务证据；2为题名对象加正文任务；0为无充分或其他状态；不是准确率 |
| semantic_support_cosine | 原候选中心的余弦相似度，启发式支持，不是概率 |
| semantic_support_cluster1000 / raw_cluster1000 | 1000版的支持簇和原候选簇编号，仅作证据，不是当前类别 |
| routing_body_characters | 既有判别实际使用的正文字符数，不代表逐篇全文精读 |
| clean_text_nearest1000 | 清理后重新编码的最近候选簇，仅作检索证据 |
| decision_action | 既有自动决定是否保持、撤回、统一标签或作编辑文本质量修正 |

`category_dictionary.csv`只有750个实际使用的类别。`documents`是直接归类记录数；`countable_documents`排除撤稿；`supported_documents`是获自动规则支持且非撤稿的记录数；`needs_review_documents`保留待复核数量；`paper_documents`、`patent_documents`、`policy_documents`之和等于该类记录数。其余列分别记录撤稿、清理文本和相对底稿研究标签调整数量。

`quarantine_dictionary.csv`独立统计4种质量状态。Q.*不是额外研究类别，相关记录在`final_labels.npy`中统一为-1，具体原因见逐条Parquet。

NPY数组都按`row_id`对齐：`final_labels.npy`保留当前类别；`analysis_count_labels.npy`只在`eligible_for_counts`为真时保留类别索引；`analysis_supported_labels.npy`只在`eligible_for_supported_analysis`为真时保留类别索引，其余为-1。读取字典时必须使用本目录的`category_dictionary.csv`。

`pending_review/`、`label_changes/`、`quality_quarantine/`与正式标签使用相同字段，分别为对应布尔条件筛选出的记录。它们可能相互交叉，不能直接把记录数相加。

历史候选可能包含无记录或已统一名称的条目，因此未将候选当作额外当前标签。原候选、初稿决定和旧编号在此前正式导出中按`row_id`保存；路径和哈希见`audit/INPUT_REFERENCES.json`。`audit/label_crosswalk.csv`明确区分实际类别、质量隔离和未使用候选。
