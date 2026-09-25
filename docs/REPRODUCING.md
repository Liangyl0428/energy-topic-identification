# 运行与复现

## 目录查询和结果核验

在仓库根目录运行 `python3 tools/catalog.py --search 光伏` 查询名称或编号。它是已有主题目录的文字检索，不是语义分类器。查询结果可通过 `--output work/pv.csv` 导出。

`python3 tools/validate_release.py` 对仓库内的静态结果进行独立核验，不重新推断逐文档标签或语义正确性。原 Excel 原样保留；其各工作表均为汇总，未包含 500 多万条逐文档标签。

## 完整研究流程

`pipelines/` 是原项目布局的精简源码存档。阶段脚本通过自身位置计算 `ROOT`，其原 `jjjj/...` 引用对应本仓库的 `pipelines/jjjj/...`。原实现仍含本地运行时搜索路径、历史输入路径及设备设置；完整重跑前需配置这些输入，不能把代码存档当作开箱即用的训练包。建议在独立副本中运行，防止覆盖冻结规则或已完成结果。

主要输入包括：

- 500 类阶段的 `data/corpus/part-*.parquet` 和 `data/INPUT_MANIFEST.json`，以及语料准备时读取的原来源数据库。
- `models/multilingual_minilm/` 编码器、分段文档向量、PCA 投影、`reduced.npy`、词频缓存及 vectorizer。
- 初始 500/486 类标签和目录、1000 类候选模型与标签、语义合并及重合审计结果。
- 精细分类的逐文档正式标签、摘要、清理文本及输入清单；750 类转换读取这些正式决定。

这些大体积输入不在本仓库中。部分源脚本使用 CUDAExecutionProvider 并要求 GPU；依赖包清单不能代替匹配的 CUDA、模型文件和缓存。`provenance/configs/` 保留已有运行配置，`provenance/original_audit/INPUT_REFERENCES.json` 保留当前 750 类转换的输入指纹。

原阶段顺序及入口：

1. 500 类阶段：语料 `prepare.py` → 模型下载/池化准备 → `encode.py` → `cluster.py` → 主题审阅与合并导出。
2. 1000 类候选：`train.py` → `export_compare.py`；复用同一语料和向量，全局重新聚类。
3. 1000 类语义合并与重合审计：读取样本、记录审阅决定、应用映射；这包含研究者判断，不能由脚本执行替代。
4. 精细分类：`prepare.py` → `prepare_models.py` → `complete_retrieval.py` → `run_all.py` → `finalize.py` → 抽样审阅和防护修订 → `validate_inputs.py` → `validate_output.py` → `build_delivery.py`。
5. 750 类平级输出：`build_flat.py` → `validate_flat.py` → `build_delivery.py`。

原规则中的相似度及证据等级是启发式条件，不是概率或经过金标准验证的准确率。历史快照中“无需复核”和“沿用底稿”也不能等同于逐篇人工验收。

`docs/original/` 保存原说明和校验报告，其中相对路径、绝对路径及数据清单指向原完整运行目录，用作溯源；本仓库直接可访问的结果以根 README 中的链接为准。
