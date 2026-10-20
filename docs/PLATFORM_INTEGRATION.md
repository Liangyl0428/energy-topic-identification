# 平台接入与版本边界

三个仓库分别承担分类、研究信号、对象成熟度。请将它们并列克隆，保持本次对应提交的版本组合。

| 仓库 | 应读取的当前业务接口 |
|---|---|
| energy-topic-identification | `assets/full_nmf500/p2/business_taxonomy.json`、`f_topic_bridge.json`；关键词版另见该仓库的 `platform/assets/keyword_dictionary_semantic_review_r2/` |
| energy-topic-hotspots | `assets/full_nmf500/p2/business_insights.json`，按 `business_topic_id` 与 P2 主题连接 |
| energy-technology-trl-crl | `assets/full_nmf500/p2/case_decision_cards.json`，按 `case_id` 识别对象，`business_links` 保留候选标记 |

F500、RBK500、P2 和 KWD 是不同的成员集合。KWD 第二轮虽是最新分类交付，但没有配套重算趋势、专利、政策和成熟度。P2 可以展示业务解释及趋势，不能声称使用 KWD 成员。当前没有全库语义验收或行业成熟度普查。

## 联合预览与重建

共享文档、预览、接口包和构建脚本归主题识别仓库 `platform/` 管理，避免在三仓库复制多个版本。

```bash
git clone https://github.com/Liangyl0428/energy-topic-identification.git
git clone https://github.com/Liangyl0428/energy-topic-hotspots.git
git clone https://github.com/Liangyl0428/energy-technology-trl-crl.git
python energy-topic-identification/tools/assemble_platform.py --repos-dir . --output /tmp/energy-platform/final
```

生成后打开 `final/preview/index.html` 或 `final/assets/keyword_dictionary_semantic_review_r2/关键词主题浏览.html`。GitHub 文件页只展示源码，HTML 需下载后打开。组装只复制文件，不执行分类、不改变等级，不覆盖已有目录。

原始数据不随 Git 分发。全量重算还需要 `config/runtime_paths.json` 中的冻结语料、关键词观测、元数据库、模型及工作中间件；可设置 `ENERGY_DATA_ROOT` 等变量。关键词/K500 发布脚本保留 `数据根/final` 的组合输出约定，运行前应准备新的数据根/输出布局，不能把现有冻结交付当作临时输出目录。

完整逐篇分类分片保留在现有本地 final 数据交付中；按 `platform/EXTERNAL_FILES.json` 恢复同路径文件并校验 SHA256。紧凑包不宣称包含完整文献列表。已存的验证报告、路径与源代码指纹描述当时的计算快照；本次仓库验证由持续集成和新的 Git 清单负责。

## 业务展示顺序

主题页显示：研究对象、能源业务关联、纳入边界、已观察信号、需要验证的问题、证据和候选对象。成熟度页显示同一配置与场景的双轴结果、证据日期及补证项；未知保留 null。论文增长不等于研究人数增长或商业成功。

业务定义和使用手册：

- [业务与决策使用手册](https://github.com/Liangyl0428/energy-topic-identification/blob/main/platform/docs/P2业务主题与决策使用手册.md)
- [接口与复现说明](https://github.com/Liangyl0428/energy-topic-identification/blob/main/platform/docs/P2接口与复现说明.md)
- [数据与指标字典](https://github.com/Liangyl0428/energy-topic-identification/blob/main/platform/docs/数据与指标字典.md)
