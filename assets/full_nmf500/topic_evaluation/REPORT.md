# 主题识别效果：全量与历史方法统一口径对比

全量论文共同有效集合：4,812,128 篇。全量几何指标逐条计算；轮廓系数是明确标注的抽样诊断，不是抽样训练。

## 全量共同论文结果

cohort,space,method,documents,active_topics,calinski_harabasz,davies_bouldin,mean_cosine_to_own_center,nearest_center_cosine_median,within_squared_distance_mean,largest_topic_share,effective_topics,size_gini
full_papers_common,bge_m3_1024,full_nmf500_current,4812128,500,1465.0122137005087,7.764365462768554,0.6968102940875688,0.9584542787864909,0.5132741793010704,0.014142391889825042,401.5145801417668,0.35544458501519505
full_papers_common,bge_m3_1024,legacy_486_parent,4812128,486,2164.9399670511934,6.700314807606019,0.7167440180573197,0.9566844061731318,0.4853450971513349,0.009865074245739099,363.3803646236299,0.3783095305805795
full_papers_common,bge_m3_1024,legacy_500_raw,4812128,500,2138.9876921265386,6.59568484152348,0.7177079117538114,0.956080848475257,0.4839117580749686,0.0056920763537462015,377.5711310300664,0.36350150203818354
full_papers_common,bge_m3_1024,legacy_750_final,4812128,744,1462.5874654785803,6.300528717944872,0.7187481805093392,0.9556032186575688,0.48231993042342725,0.008045089407430558,430.33181511917593,0.5431534901564483
full_papers_common,bge_m3_1024,legacy_990_merged,4812128,990,1215.4802615066646,6.518281135121581,0.7251401581425518,0.9564582929527496,0.47305869055233035,0.003742834770812414,729.809782410689,0.3884968512386986
full_papers_common,bge_m3_1024,legacy_1000_raw,4812128,1000,1206.5995241403034,6.517029715036182,0.7253105409374194,0.9565185770773079,0.472800367157083,0.003742834770812414,739.1516047633058,0.38556469279287686
full_papers_common,legacy_minilm_pca64,full_nmf500_current,4812128,500,4090.5682484896256,6.315445276408684,0.5461302542279265,0.8546014094930223,0.6887024427199797,0.014142391889825042,401.5145801417668,0.35544458501519505
full_papers_common,legacy_minilm_pca64,legacy_486_parent,4812128,486,9467.019644614407,3.4556453997556478,0.70403094814801,0.8183367177482779,0.5019137650752847,0.009865074245739099,363.3803646236299,0.3783095305805795
full_papers_common,legacy_minilm_pca64,legacy_500_raw,4812128,500,9492.308630925223,3.3230984504769054,0.7093438059256018,0.8165201834620899,0.49428273981645043,0.0056920763537462015,377.5711310300664,0.36350150203818354
full_papers_common,legacy_minilm_pca64,legacy_750_final,4812128,744,6339.83219749238,3.8583081301033366,0.7083821094397191,0.8602576254394481,0.4956285890894711,0.008045089407430558,430.33181511917593,0.5431534901564483
full_papers_common,legacy_minilm_pca64,legacy_990_merged,4812128,990,5413.6954304545725,3.299451789812854,0.7302797894284115,0.8375641528988222,0.4642344363011166,0.003742834770812414,729.809782410689,0.3884968512386986
full_papers_common,legacy_minilm_pca64,legacy_1000_raw,4812128,1000,5377.611785133746,3.29610015913193,0.7308337664475566,0.8377195856685221,0.4634092780530387,0.003742834770812414,739.1516047633058,0.38556469279287686

## 阅读口径

CH、同簇余弦与轮廓系数越高通常越好，DBI越低通常越好；不同K、簇形状会影响指标，不能凭单一指标宣布语义最优。有效主题数、最大簇占比和Gini用于检查集中程度，不是越均匀越准确。

coverage.csv保留各方法未分类情况；geometry.csv为同文献同空间几何指标；silhouette.csv含随机种子和抽样ID哈希；agreement.csv是ARI/NMI一致性而非准确率。COHORTS.json记录各比较的共同样本量和ID哈希，INPUTS.json记录输入文件哈希。

历史验证集合共 50 个方法/版本；严格全方法交集仅 1,189/12,000 篇，因此主比较采用本次全量模型与每个历史方法的成对共同文献，不能横向混排不同成对子集。旧样本v020/v021作为历史结果名称保留，与本次重新发布的Git v0.2.0不是同一模型。

## 局限

- All-year full training includes historical validation documents; retrospective diagnostics only.
- BGE and legacy PCA are separate robustness views. Legacy clusters were optimized in the legacy space.
- Matched-pair validation populations differ; do not rank absolute scores across pairs.
- Strict all-method intersection is strongly selected by noise exclusions; secondary only.
- ARI/NMI measure agreement, not correctness; cluster IDs do not require manual matching.
- No expert gold labels: no accuracy/F1 claim and no patent/policy semantic precision claim.
- 几何指标不等同于语义解释性；关键词 NPMI 的独立口径见下。
- No new model refits or model-seed stability experiments in this comparison.

## 关键词一致性与多样性

keyword_coherence.csv 在相同历史12,000篇参考文献、相同二值OpenAlex关键词上计算每个方法与本次模型的成对比较。每簇按文档频次选前10词，报告文档共现NPMI（宏平均和按簇文档数加权）及去重主题词/词槽比。缺少至少2个词的簇不计入NPMI，并报告有效簇数。此指标不是全量480万篇NPMI，也不是独立验证；使用OpenAlex词表可能有利于关键词方法。
