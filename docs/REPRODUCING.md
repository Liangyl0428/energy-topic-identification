# 复现与运行

三个仓库放在同一工作区。CPU依赖见requirements-full-nmf.txt；编码另需Python3.10、ONNX Runtime CUDA、tokenizers、BGE-M3权重及匹配的CUDA运行库。

## 外部运行资产

- jjjj/bertopic500_all_sources_20260925/data/corpus/part-*.parquet：冻结全来源记录。
- aaaa/openalex_keywords_nmf/verified_sources.json及指向的论文CSV。
- aaaa/bge_m3/models/bge-m3/：模型和tokenizer；_runtime、_core为编码运行时搜索目录。
- analyze/data/independent_corpus.duckdb：热点所需论文元数据。
- energy-technology-trl-crl/work/nmf500/context/：已核验对象上下文及embedding。

## 执行

在共享工作区根目录：

    .venv-hotspots/bin/python energy-topic-identification/pipelines/full_nmf/run.py

按prepare、encode、train、finalize、两个下游build及publish_local完成基础处理。缓存和大文件在work/full_nmf500_20260926，有哈希及完成标记。不要在同目录并发重复启动。

只读查看：

    .venv-hotspots/bin/python energy-topic-identification/pipelines/full_nmf/status.py

在本仓库根目录检查：

    python -m pytest tests/test_keyword_nmf.py tests/test_full_nmf.py tests/test_full_delivery.py -q
    python tools/check_current_release.py

完整模型selected_nmf.joblib、components.npy、vocabulary.csv、topic_centroids.npy与逐条标签保留在工作目录。加载NMF需将pipelines/full_nmf加入Python模块路径，导入fast_nmf.GpuMiniBatchNMF。Git提供源码、参数记录与结果摘要，不包含完整训练权重、全量文献或向量。
