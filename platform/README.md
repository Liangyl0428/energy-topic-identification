# 三模块业务交付与联调资料

本目录保存 P0/P1/P2 业务手册、接口、预览及关键词分类的紧凑交付。模块实现分别位于三个独立仓库。

- [业务与决策手册](docs/P2业务主题与决策使用手册.md)、[开发接口](docs/P2接口与复现说明.md)、[指标字典](docs/数据与指标字典.md)
- [P2 业务预览](preview/index.html)、[P2 接口包](assets/p2/platform_data.json)
- [最新 72 主题浏览](assets/keyword_dictionary_semantic_review_r2/关键词主题浏览.html)、[使用与接入说明](assets/keyword_dictionary_semantic_review_r2/使用与接入说明.html)、[审核限制](assets/keyword_dictionary_semantic_review_r2/REVIEW.json)
- [K500 审阅预览](preview/nmf500_multilabel.html)、[K500 验收结论](acceptance/nmf500_multilabel_20261019/ACCEPTANCE.json)
- [完整逐篇导出的外部文件清单](EXTERNAL_FILES.json)

P2 是 9 类业务、51 个题名检索主题和 122 个对象卡。最新关键词版为 72 个 KWD 主题；没有按它重算热点、趋势或成熟度。F、RBK500、P2、KWD 编号不能互换。语义审核尚未完成，不能把程序校验等同专家验收。

HTML 文件内嵌展示数据，下载后可以直接打开。全量论文归属和主题关系分片不进入 Git，原交付数据保持不变；先按外部清单恢复并校验后，才可查询全部成员。各子目录原有 RELEASE、VALIDATION 和 provenance 文件记录原计算快照，不代表此次打包重新计算过结果。

复现跨模块构建时，把三个仓库放在同一级，执行主题识别仓库中的 `python tools/assemble_platform.py --repos-dir .. --output /path/to/project/final`。它生成新的组合目录，拒绝覆盖已有目录。原文档中 `final/...` 命令均在这个组合布局使用；大型原始数据、模型、元数据库及中间矩阵仍需通过运行配置提供。详见仓库的接入文档。
