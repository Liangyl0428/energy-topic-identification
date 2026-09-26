# NMF 模型选择灵敏度与指标消融

复用已运行的 K=400/450/500/550/600、seed29、80%抽样实验，不重复训练。
本脚本检验 450–550 候选区间内选模偏好与六项指标留一，不是 TF-IDF/编码器表示消融。
500 是结合“约500”的业务偏好所得，不是各项指标一致支持的唯一最优值。
0.05 实际并列容差是在看到网格结果后记录的选择规则，未预注册；不能解释为统计显著性。
无容差、原惩罚权重时选择450；容差0.05时选择500。

500的抽样余弦轮廓系数为负（约-0.0866），最近簇心余弦约0.955，
说明关键词 NMF 类别在 BGE 空间仍有较大重叠，不能据此声称得到500个清晰分离的语义簇。
seed29验证ARI约0.734；80%训练样本验证ARI约0.603，后者达到30次迭代上限，
同时受样本变化和未充分收敛影响，不能将变化全部归因于采样。

## 选择结果

| kind                      | omitted_metric             |   penalty |   practical_tie_tolerance |   selected_k |
|:--------------------------|:---------------------------|----------:|--------------------------:|-------------:|
| preference_sensitivity    |                            |      0    |                      0    |          450 |
| preference_sensitivity    |                            |      0    |                      0.01 |          450 |
| preference_sensitivity    |                            |      0    |                      0.02 |          450 |
| preference_sensitivity    |                            |      0    |                      0.05 |          450 |
| preference_sensitivity    |                            |      0    |                      0.1  |          450 |
| preference_sensitivity    |                            |      0.05 |                      0    |          450 |
| preference_sensitivity    |                            |      0.05 |                      0.01 |          450 |
| preference_sensitivity    |                            |      0.05 |                      0.02 |          450 |
| preference_sensitivity    |                            |      0.05 |                      0.05 |          450 |
| preference_sensitivity    |                            |      0.05 |                      0.1  |          450 |
| preference_sensitivity    |                            |      0.15 |                      0    |          450 |
| preference_sensitivity    |                            |      0.15 |                      0.01 |          450 |
| preference_sensitivity    |                            |      0.15 |                      0.02 |          500 |
| preference_sensitivity    |                            |      0.15 |                      0.05 |          500 |
| preference_sensitivity    |                            |      0.15 |                      0.1  |          500 |
| preference_sensitivity    |                            |      0.3  |                      0    |          500 |
| preference_sensitivity    |                            |      0.3  |                      0.01 |          500 |
| preference_sensitivity    |                            |      0.3  |                      0.02 |          500 |
| preference_sensitivity    |                            |      0.3  |                      0.05 |          500 |
| preference_sensitivity    |                            |      0.3  |                      0.1  |          500 |
| selection_metric_ablation | sampled_cosine_silhouette  |      0.15 |                      0.05 |          500 |
| selection_metric_ablation | simplified_silhouette_mean |      0.15 |                      0.05 |          500 |
| selection_metric_ablation | davies_bouldin             |      0.15 |                      0.05 |          450 |
| selection_metric_ablation | nearest_center_cosine_mean |      0.15 |                      0.05 |          450 |
| selection_metric_ablation | empty_topic_fraction       |      0.15 |                      0.05 |          500 |
| selection_metric_ablation | keyword_embedding_ari      |      0.15 |                      0.05 |          500 |

K网格使用拟合时的训练W标签评估。交付下游改用所有切分统一 model.transform，
标签改变1735篇训练论文；重建中心后专利646条、政策139条Top1改变。
这是推断方式对照，不是重新训练或泛化准确率。当前生效目录见 ../current_topic_catalog.csv，
该目录与热点/TRL仓库一致；历史网格目录仅用于记录选择过程。
跨来源余弦的拒绝阈值、来源删除实验见热点仓库 assets/nmf500/experiments。
